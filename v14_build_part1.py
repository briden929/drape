# ==============================================================================
# FULL QUEUE WORKER V14 FINAL
# ==============================================================================
import asyncio
import os
import sys
import uuid
import time
import queue
import threading
import traceback
import json
import concurrent.futures
from pathlib import Path
from collections import deque
from bullmq import Worker, Queue
import psycopg2
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException

import db
import credits
import fashion_studio

MAX_CONCURRENT_TABS = 4
CHROME_WMR_WORKERS = 4
GENERATION_TIMEOUT_S = 300
DOWNLOAD_TIMEOUT_S = 60
TOTAL_JOB_TIMEOUT_S = GENERATION_TIMEOUT_S + DOWNLOAD_TIMEOUT_S
DOWNLOAD_START_WINDOW_S = 30
WMR_TABS_PER_DRIVER = 4

STATE_DIR = Path("/content/queue_worker_bundle/queue_worker_state")
CHROME_DL_BASE = Path("/content/downloads/chrome")
CHROME_STAGING_BASE = Path("/content/downloads/chrome_staging")
WMR_STAGING_BASE = Path("/content/downloads/wmr_staging")
WMR_DL_BASE = Path("/content/downloads/wmr")
FINAL_OUTPUT_BASE = Path("/content/downloads/final_output")


class JobState:
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    GENERATING = "GENERATING"
    DOWNLOAD_START_WAIT = "DOWNLOAD_START_WAIT"
    DOWNLOAD_START_CONFIRMED = "DOWNLOAD_START_CONFIRMED"
    BACKGROUND_DOWNLOAD = "BACKGROUND_DOWNLOAD"
    RAW_READY = "RAW_READY"
    WMR_QUEUED = "WMR_QUEUED"
    WMR_ASSIGNED = "WMR_ASSIGNED"
    PROCESSING = "PROCESSING"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    R2_READY = "R2_READY"
    DB_READY = "DB_READY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobContext:
    def __init__(self, job_data):
        self.job_id = job_data.get('id', str(uuid.uuid4()))
        self.generation_id = job_data.get('generation_id', self.job_id)
        self.prompt = job_data.get('prompt', '')
        self.refs = job_data.get('refs', [])
        self.user_id = job_data.get('user_id', 'anonymous')
        self.retry_count = job_data.get('retry_count', 0)
        
        self.future = None
        self.state = JobState.QUEUED
        
        self.assigned_tid = None
        self.assigned_wmr_tab = None
        self.download_guid = None
        
        self.raw_path = None
        self.clean_png = None
        self.clean_webp = None
        
        self.error_message = None

    def transition(self, new_state):
        self.state = new_state

def resolve_future_once(main_loop, future, result, is_exception=False):
    if not future or future.done():
        return
    if main_loop.is_closed():
        return
    async def _resolve():
        if future.done():
            return
        if is_exception:
            future.set_exception(result)
        else:
            future.set_result(result)
    asyncio.run_coroutine_threadsafe(_resolve(), main_loop)

# Globals initialized correctly
job_contexts = {}
download_registry = {}
main_loop = None
gemini_pool = None
wmr_pool = None

def get_chrome_job_dir(tab_id: int, job_id: str):
    """Returns (job_dir, incoming_dir) for Chrome downloads."""
    job_dir = CHROME_DL_BASE / f'T{tab_id}' / job_id
    incoming = job_dir / 'incoming'
    incoming.mkdir(parents=True, exist_ok=True)
    return (job_dir, incoming)

def get_wmr_job_dir(chrome_tab_id: int, job_id: str):
    """Returns (job_dir, incoming_dir) for WMR Chrome output. Named by T-slot, not W-slot."""
    job_dir = WMR_DL_BASE / f'T{chrome_tab_id}' / job_id
    incoming = job_dir / 'incoming'
    incoming.mkdir(parents=True, exist_ok=True)
    return (job_dir, incoming)

def get_wmr_staging_dir(wmr_worker_id: int) -> Path:
    """Returns the dedicated staging directory for WMR Chrome worker W{wmr_worker_id}."""
    d = WMR_STAGING_BASE / f'W{wmr_worker_id}'
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_final_output_dir(chrome_tab_id: int, job_id: str):
    """Returns final_output dir for this job."""
    d = FINAL_OUTPUT_BASE / f'T{chrome_tab_id}' / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def validate_image_file(path, min_size=DOWNLOAD_MIN_SIZE):
    """Returns True if path exists, is large enough, and PIL can open it."""
    try:
        p = Path(path)
        if not p.exists() or p.stat().st_size < min_size:
            return False
        with Image.open(p) as im:
            im.verify()
        return True
    except Exception:
        return False

def convert_to_webp(png_path, max_size_kb=800):
    try:
        webp_path = os.path.splitext(png_path)[0] + '.webp'
        img = Image.open(png_path)
        img.load()
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA' if img.mode in ('P', 'LA', 'PA') else 'RGB')
        for q in (90, 80, 70, 60, 50, 40):
            buf = io.BytesIO()
            img.save(buf, format='WEBP', quality=q, method=4)
            data = buf.getvalue()
            if len(data) / 1024 <= max_size_kb or q == 40:
                Path(webp_path).write_bytes(data)
                return webp_path
        return webp_path
    except Exception as e:
        log(f'   WebP conversion failed: {e}')
        return None

def upload_to_r2(file_path, object_name):
    return 'https://r2/' + object_name

def create_persistent_chrome_driver():
    import undetected_chromedriver as uc
    profile_dir = Path('/content/queue_worker_bundle/queue_worker_state/chrome_profile')
    profile_dir.mkdir(parents=True, exist_ok=True)
    options = uc.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--user-data-dir={profile_dir}')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-session-crashed-bubble')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        raise RuntimeError(f'CHROME_START_FAILED: {type(e).__name__}: {e}') from e
    assert driver is not None
    assert driver.service is not None
    assert driver.window_handles
    driver.execute_script('return document.readyState')
    driver.execute_cdp_cmd('Browser.getVersion', {})
    return driver

def create_wmr_chrome_driver(wid):
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--user-data-dir=/content/queue_worker_bundle/queue_worker_state/wmr_chrome_profiles/W{wid}')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    drv = uc.Chrome(options=options)
    drv.set_window_size(1400, 1000)
    return drv

# MISSING FUNCTION: _click_menu_item

# MISSING FUNCTION: turn_off_gemini_activity

def check_chrome_driver_health(driver):
    if driver is None:
        return {'alive': False}
    try:
        driver.execute_script('return 1')
        return {'alive': True, 'window_count': len(driver.window_handles), 'current_handle': driver.current_window_handle, 'current_url': driver.current_url, 'pid': driver.service.process.pid if driver.service and driver.service.process else None}
    except Exception:
        return {'alive': False}

# MISSING FUNCTION: wait_for_attachment_chip

# MISSING FUNCTION: _hover_and_download

# MISSING FUNCTION: _click_download_button

def _wmr_find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs:
        return inputs[0]
    _wmr_expose_file_inputs(drv)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def _wmr_check_status(drv):
    js_code = "\n        var btns = document.querySelectorAll('button');\n        for (var i = 0; i < btns.length; i++) {\n            var btn = btns[i];\n            var txt = (btn.textContent || '').trim();\n            if (txt.indexOf('Download PNG') !== -1 || txt.indexOf('Save') !== -1) {\n                var style = window.getComputedStyle(btn);\n                var isVisible = style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';\n                if (isVisible && !btn.disabled) {\n                    return 'DONE';\n                }\n            }\n        }\n        // Wait strictly for Download PNG button as per architecture\n        // Do not use after-image detection as a shortcut for readiness\n        var allText = document.body ? document.body.innerText.toLowerCase() : '';\n        if (allText.indexOf('detecting') !== -1 || allText.indexOf('processing') !== -1) {\n            return 'BUSY';\n        }\n        if (allText.indexOf('not detected') !== -1 || allText.indexOf('no watermark') !== -1) {\n            for (var i = 0; i < btns.length; i++) {\n                var txt = (btns[i].textContent || '').trim();\n                if (txt.indexOf('Download PNG') !== -1 || txt.indexOf('Save') !== -1) {\n                    return 'DONE';\n                }\n            }\n            return 'NOT_FOUND';\n        }\n        if (allText.length < 10) return 'LOADING';\n        return 'BUSY';\n    "
    res = safe_execute_script(drv, js_code)
    return (res or 'error').upper()

def _wmr_click_download(drv, prefix, attempts=1):
    js_code = '\n        // 1. Locate the result container. Often it\'s the parent of the comparison slider, or contains the text "Result"\n        // Since we might not know the exact class, we find the container holding "Clean" or "Result" or just find the exact button and verify its context.\n        var btns = document.querySelectorAll(\'button\');\n        var target = null;\n        for (var i = 0; i < btns.length; i++) {\n            var btn = btns[i];\n            var txt = (btn.textContent || btn.innerText || \'\').trim();\n            if (txt === \'Download PNG\') {\n                target = btn;\n                break;\n            }\n        }\n        if (!target) return \'NOT_FOUND\';\n        \n        var style = window.getComputedStyle(target);\n        if (style.display === \'none\' || style.visibility === \'hidden\' || target.disabled) {\n            return \'NOT_VISIBLE_OR_DISABLED\';\n        }\n        \n        // Scope verification: walk up to ensure it\'s in the main result section\n        var root = target.closest(\'main\') || target.closest(\'.result\') || target.parentElement.parentElement;\n        \n        target.scrollIntoView({behavior: \'instant\', block: \'center\'});\n        var r = target.getBoundingClientRect();\n        \n        return {\n            x: Math.round(r.x), \n            y: Math.round(r.y), \n            w: Math.round(r.width), \n            h: Math.round(r.height),\n            text: (target.textContent || \'\').trim()\n        };\n    '
    for _ in range(attempts):
        res = safe_execute_script(drv, js_code)
        if isinstance(res, dict):
            log(f'{prefix} WMR_DOWNLOAD_TARGET_FOUND')
            log(f"{prefix} WMR_DOWNLOAD_TARGET_TEXT '{res['text']}'")
            log(f"{prefix} WMR_DOWNLOAD_TARGET_RECT x={res['x']} y={res['y']} w={res['w']} h={res['h']}")
            try:
                btns = drv.find_elements(By.XPATH, "//button[normalize-space(.)='Download PNG']")
                if btns and btns[0].is_displayed() and btns[0].is_enabled():
                    btns[0].click()
                    return True
            except Exception:
                drv.execute_script("\n                    var btns = document.querySelectorAll('button');\n                    for (var i = 0; i < btns.length; i++) {\n                        if (btns[i].textContent.trim() === 'Download PNG') {\n                            btns[i].click();\n                            return;\n                        }\n                    }\n                ")
                return True
        time.sleep(0.3)
    return False

# MISSING FUNCTION: _direct_fetch_image

def snapshot_urls(drv):
    try:
        return set(drv.execute_script('return Array.from(document.querySelectorAll(\'img[src^="blob:"],img[src*="googleusercontent"]\')).map(i=>i.src).filter(s=>s&&s.length>10);') or [])
    except Exception:
        return set()

# MISSING FUNCTION: check_new_image

# MISSING FUNCTION: check_new_image_lenient

# MISSING FUNCTION: wait_for_image

# MISSING FUNCTION: set_download_behavior

# MISSING FUNCTION: check_limit_or_refusal

# MISSING FUNCTION: start_new_chat

def click_plus_button(drv):
    try:
        res = drv.execute_script('\n            var btns = document.querySelectorAll(\'button\');\n            for (var i = 0; i < btns.length; i++) {\n                var b = btns[i];\n                if (b.offsetParent === null) continue;\n                var lbl = (b.getAttribute(\'aria-label\') || \'\').toLowerCase();\n                if (lbl.indexOf(\'upload\') !== -1 || lbl.indexOf(\'tools\') !== -1 || lbl.indexOf(\'plus\') !== -1) {\n                    b.click(); return \'OK\';\n                }\n                var icon = b.querySelector(\'mat-icon[fonticon="plus"], mat-icon[data-mat-icon-name="plus"]\');\n                if (icon) { b.click(); return \'OK\'; }\n            } return \'NO\';\n        ')
        if res == 'OK':
            time.sleep(0.3)
            return True
    except Exception:
        pass
    for sel in ['button[aria-label="Upload and tools"]', 'button[jslog*="300142"]', 'button[aria-haspopup="menu"][aria-label*="Upload"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script('arguments[0].click();', btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    return False

# MISSING FUNCTION: click_create_image

# MISSING FUNCTION: _in_image_mode

# MISSING FUNCTION: wait_for_image_mode

# MISSING FUNCTION: activate_create_image_mode

# MISSING FUNCTION: select_gemini_model

# MISSING FUNCTION: handle_consent

# MISSING FUNCTION: click_upload_files_in_drawer

# MISSING FUNCTION: find_file_input

# MISSING FUNCTION: jsdrop_single

# MISSING FUNCTION: save_debug_screenshot

# MISSING FUNCTION: upload_images

# MISSING FUNCTION: _attach_images_together

# MISSING FUNCTION: _attach_one_image

# MISSING FUNCTION: get_editor

# MISSING FUNCTION: _strip_ws

# MISSING FUNCTION: _verify_editor_content

# MISSING FUNCTION: _clear_editor

# MISSING FUNCTION: type_prompt

# MISSING FUNCTION: click_send