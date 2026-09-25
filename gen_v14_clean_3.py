import json
import uuid

v11 = json.load(open('v11_syms.json', 'r', encoding='utf-8'))
v13 = json.load(open('v13_syms.json', 'r', encoding='utf-8'))

out_lines = []
def add(s):
    out_lines.append(s)

add('''# ==============================================================================
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
import psycopg2
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException
from bullmq import Worker, Queue
import heapq

import subprocess
import re
import shutil
import pickle
import base64
import io
import socket
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyvirtualdisplay import Display
try:
    from IPython.display import HTML, display as ipy_display
except:
    pass

import db
import credits
import fashion_studio

# ------------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ------------------------------------------------------------------------------
GEMINI_WORKERS = 4
WMR_WORKERS = 4
WMR_TABS_PER_PROFILE = 2
BULLMQ_CONCURRENCY = 8
GENERATION_TIMEOUT_S = 300
DOWNLOAD_TIMEOUT_S = 60
TOTAL_JOB_TIMEOUT_S = GENERATION_TIMEOUT_S + DOWNLOAD_TIMEOUT_S
DOWNLOAD_START_WINDOW_S = 30

SCREEN_W = 1280
SCREEN_H = 1024
VNC_PORT = 5900
NOVNC_PORT = 6080
CHROME_PROFILE_DIR = Path("/content/queue_worker_bundle/queue_worker_state/chrome_profile")
WMR_PROFILES_BASE = Path("/content/queue_worker_bundle/queue_worker_state/wmr_chrome_profiles")
DOWNLOAD_MIN_SIZE = 1024
DOWNLOAD_STABLE_CHECKS = 3
COOKIES_FILE = Path("/content/queue_worker_bundle/queue_worker_state/cookies.pkl")
SHORT_WAIT = 5
MAX_VERIFICATION_ATTEMPTS = 3
MAX_NEW_CHAT_RETRIES = 3
GEMINI_APP_URL = "https://gemini.google.com/app"
REFS_CACHE_DIR = Path("/content/queue_worker_bundle/queue_worker_state/refs")
QUEUE_NAME = "generations"
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"
SCREENSHOT_FOLDER = Path("/content/queue_worker_bundle/queue_worker_state/screenshots")

STATE_DIR = Path("/content/queue_worker_bundle/queue_worker_state")
CHROME_DL_BASE = Path("/content/downloads/chrome")
CHROME_STAGING_BASE = Path("/content/downloads/chrome_staging")
WMR_STAGING_BASE = Path("/content/downloads/wmr_staging")
WMR_DL_BASE = Path("/content/downloads/wmr")
FINAL_OUTPUT_BASE = Path("/content/downloads/final_output")

# Globals
main_loop = None
gemini_pool = None
wmr_pool = None
job_contexts = {}
download_registry = {}
GEMINI_BROKER = None
WMR_BROKER = None
chrome_driver = None

def log(msg):
    print(msg, flush=True)

def resolve_future_once(loop, future, result, is_exception=False):
    if future is None:
        return False

    if loop is None:
        return False

    if loop.is_closed():
        return False

    def _resolve():
        if future.done():
            return

        if is_exception:
            future.set_exception(result)
        else:
            future.set_result(result)

    try:
        loop.call_soon_threadsafe(_resolve)
        return True
    except RuntimeError:
        return False

class JobState:
    QUEUED = "QUEUED"
    GEMINI_ASSIGNED = "GEMINI_ASSIGNED"
    UPLOADING = "UPLOADING"
    GENERATING = "GENERATING"
    GEMINI_DOWNLOAD_CLICKED = "GEMINI_DOWNLOAD_CLICKED"
    GEMINI_DOWNLOAD_STARTED = "GEMINI_DOWNLOAD_STARTED"
    GEMINI_RESOURCE_RELEASED = "GEMINI_RESOURCE_RELEASED"
    RAW_DOWNLOADING = "RAW_DOWNLOADING"
    RAW_READY = "RAW_READY"
    WMR_QUEUED = "WMR_QUEUED"
    WMR_ASSIGNED = "WMR_ASSIGNED"
    WMR_PROCESSING = "WMR_PROCESSING"
    WMR_DOWNLOAD_CLICKED = "WMR_DOWNLOAD_CLICKED"
    WMR_DOWNLOAD_STARTED = "WMR_DOWNLOAD_STARTED"
    WMR_RESOURCE_RELEASED = "WMR_RESOURCE_RELEASED"
    CLEAN_DOWNLOADING = "CLEAN_DOWNLOADING"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    R2_UPLOADING = "R2_UPLOADING"
    R2_READY = "R2_READY"
    DB_FINALIZING = "DB_FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobContext:
    def __init__(self, job_data, future):
        self.job_data = job_data
        self.job_id = job_data.get("id", str(uuid.uuid4()))
        self.generation_id = job_data.get("generation_id", self.job_id)
        self.prompt = job_data.get("prompt", "")
        self.refs = job_data.get("refs", [])
        self.user_id = job_data.get("user_id", "anonymous")
        self.retry_count = job_data.get("retry_count", 0)
        
        self.future = future
        self.state = JobState.QUEUED
        
        self.assigned_tid = None
        self.assigned_wmr_tab = None
        self.gemini_download_guid = None
        self.wmr_download_guid = None
        
        self.raw_path = None
        self.clean_path = None
        self.webp_path = None
        self.r2_png_url = None
        self.r2_webp_url = None
        
        self.error_message = None
        self.created_at = time.time()
        self.updated_at = time.time()

    def transition(self, new_state):
        self.state = new_state
        self.updated_at = time.time()
        res = f"[{self.assigned_tid}]" if self.assigned_tid is not None else ""
        if self.assigned_wmr_tab:
            res = f"[{self.assigned_wmr_tab}]"
        log(f"[JOB {self.job_id}]{res} {self.state}")

class FirstFreeBroker:
    def __init__(self):
        self.seq = 0
        self.lock = threading.Lock()
        self.free_q = []
        self.in_q = set()

    def release(self, resource_id):
        with self.lock:
            if resource_id not in self.in_q:
                self.seq += 1
                heapq.heappush(self.free_q, (self.seq, resource_id))
                self.in_q.add(resource_id)

    def acquire(self):
        with self.lock:
            if not self.free_q:
                return None
            seq, resource_id = heapq.heappop(self.free_q)
            self.in_q.remove(resource_id)
            return resource_id

    def remove(self, resource_id):
        with self.lock:
            if resource_id in self.in_q:
                self.free_q = [x for x in self.free_q if x[1] != resource_id]
                heapq.heapify(self.free_q)
                self.in_q.remove(resource_id)
''')

defined_by_me = {
    'log', 'resolve_future_once', 'JobState', 'JobContext', 'FirstFreeBroker',
    'GeminiWorker', 'GeminiWorkerPool', 'WmrDriverThread', 'WmrWorkerPool',
    '_run_wmr_logic', 'poll_active_downloads', '_finalize_job',
    'process_job_pipeline', 'process_bullmq_job', 'startup_preflight', 'main',
    
    'update_redis_queue_stats_loop', 'print_pipeline_status', 'central_scheduler_loop',
    'startup_sequence', 'run_ast_validation', 'run_startup_self_test', 'preflight_validate_runtime',
    '_make_tab_state', 'WmrWorker', '_finalize_and_clean_job', '_enqueue_wmr', 'poll_wmr_workers',
    'record_dead_letter', 'fetch_generation',
    '_get_pool', '_mark_used', '_checkout', 'db_connection', '_PooledBorrow', 'db_borrow',
    'credits_settle_look', 'credits_refund_look', 'fs_configured', '_r2_client',
    'fashion_tryon_prompt', 'download_remote_image', 'push_generation', 'upload_to_r2'

}

for name in v11.keys():
    if name not in defined_by_me:
        add(v11[name])
        defined_by_me.add(name)
        
for name in v13.keys():
    if name not in defined_by_me:
        add(v13[name])
        defined_by_me.add(name)

add('''
gemini_driver_lock = threading.Lock()

class GeminiWorker:
    def __init__(self, tid: int):
        self.tid = tid
        self.state = 'IDLE'
        self.current_job_id = None
        self.window_handle = None

    def _ensure_tab(self):
        global chrome_driver
        if not check_chrome_driver_health(chrome_driver)['alive']:
            raise RuntimeError('Global chrome_driver is dead')
            
        with gemini_driver_lock:
            if self.window_handle:
                try:
                    if self.window_handle in chrome_driver.window_handles:
                        chrome_driver.switch_to.window(self.window_handle)
                        return chrome_driver
                except Exception:
                    pass
            log(f'[T{self.tid}] Creating new logical Gemini tab...')
            chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
            for h in chrome_driver.window_handles:
                chrome_driver.switch_to.window(h)
                if chrome_driver.current_url == 'about:blank' or chrome_driver.current_url.startswith('data:'):
                    self.window_handle = h
                    break
            if not self.window_handle:
                self.window_handle = chrome_driver.window_handles[-1]
            chrome_driver.switch_to.window(self.window_handle)
            return chrome_driver

    def process_job(self, ctx: JobContext):
        t = threading.Thread(target=self._process_job_thread, args=(ctx,), daemon=True)
        t.start()

    def _process_job_thread(self, ctx: JobContext):
        job_id = ctx.job_id
        future = ctx.future
        prefix = f'[T{self.tid}][{job_id}]'
        
        self.current_job_id = job_id
        
        try:
            drv = self._ensure_tab()
            
            job_dir, incoming_dir = get_chrome_job_dir(self.tid, job_id)
            staging_dir = Path(f'/content/downloads/chrome_staging/T{self.tid}')
            staging_dir.mkdir(parents=True, exist_ok=True)
            
            with gemini_driver_lock:
                drv.switch_to.window(self.window_handle)
                drv.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(staging_dir)})
                curr = drv.current_url
                if 'gemini.google.com/app' not in curr:
                    drv.get('https://gemini.google.com/app')
                    
            time.sleep(1)
            
            with gemini_driver_lock:
                drv.switch_to.window(self.window_handle)
                _ = drv.get_log('performance')
                log(f'{prefix} FRESH_BROWSER_READY')
                if not nb_check_image(drv, prefix):
                    raise Exception('COMPOSER_FAILED')
                log(f'{prefix} CLEAN_COMPOSER_VERIFIED')
                ensure_flash_mode(drv, self.tid, job_id)
                ensure_create_image_mode(drv, self.tid, job_id)
                
                refs = ctx.refs
                expected_refs = [p for p in refs if p]
                ref_paths = [str(Path(p).resolve()) for p in expected_refs]
                if ref_paths:
                    perform_robust_upload(drv, ref_paths, self.tid, job_id)
                    verified, actual = verify_attachment_count(drv, len(ref_paths), self.tid, job_id)
                    if not verified:
                        raise Exception(f'ATTACHMENT_MISMATCH: expected {len(ref_paths)}, got {actual}')
                        
                _inject_prompt_atomic(drv, ctx.prompt, self.tid, job_id)
                urls_before = snapshot_urls(drv)
                chat_urls = {u for u in urls_before if '/app/' in u}
                log(f'{prefix} SEND_REQUESTED')
                
                if not _click_send_button(drv, self.tid, job_id):
                    raise Exception('SEND_FAILED')
                log(f'{prefix} SEND_CLICKED')
                
                if not verify_generation_started(drv):
                    raise Exception('GEN_START_FAILED')
                    
            ctx.transition(JobState.GENERATING)
            
            t0 = time.time()
            image_detected = False
            while time.time() - t0 < GENERATION_TIMEOUT_S:
                with gemini_driver_lock:
                    drv.switch_to.window(self.window_handle)
                    status, new_src = nb_check_image(drv, urls_before, chat_urls)
                if status == 'SUCCESS':
                    image_detected = True
                    if new_src:
                        urls_before.add(new_src)
                    break
                time.sleep(1.0)
                
            if not image_detected:
                raise Exception('GENERATION_TIMEOUT')
                
            log(f'{prefix} IMAGE_DETECTED')
            
            files_before = set(staging_dir.iterdir()) if staging_dir.exists() else set()
            
            with gemini_driver_lock:
                drv.switch_to.window(self.window_handle)
                hover_ok = _hover_and_dl_single_click(drv, urls_before, chat_urls)
            
            log(f'{prefix} DOWNLOAD_CLICKED (hover_ok={hover_ok})')
            ctx.transition(JobState.GEMINI_DOWNLOAD_STARTED)
            
            dl_guid = None
            t1 = time.time()
            while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                with gemini_driver_lock:
                    drv.switch_to.window(self.window_handle)
                    for entry in drv.get_log('performance'):
                        try:
                            msg = json.loads(entry['message'])['message']
                            if msg['method'] == 'Browser.downloadWillBegin':
                                dl_guid = msg['params']['guid']
                                break
                        except:
                            pass
                if dl_guid:
                    break
                time.sleep(0.1)
                
            dl_confirmed_fs = False
            t2 = time.time()
            while time.time() - t2 < DOWNLOAD_START_WINDOW_S:
                if staging_dir.exists():
                    cur = set(staging_dir.iterdir())
                    new_files = cur - files_before
                    for nf in new_files:
                        if nf.name.endswith('.crdownload') or nf.name.endswith('.png') or nf.name.endswith('.jpg') or nf.name.endswith('.webp'):
                            dl_confirmed_fs = True
                            break
                if dl_confirmed_fs:
                    break
                time.sleep(0.1)
                
            if dl_confirmed_fs:
                log(f'{prefix} DOWNLOAD_START_EVENT guid={dl_guid}')
                ctx.gemini_download_guid = dl_guid or f'fs_fallback_{job_id}'
                ctx.transition(JobState.GEMINI_RESOURCE_RELEASED)
                
                download_registry[ctx.gemini_download_guid] = {
                    'ctx': ctx,
                    'type': 'GEMINI',
                    'staging_dir': staging_dir,
                    'files_before': files_before,
                    'started_at': time.time(),
                    'job_dir': job_dir,
                    'incoming_dir': incoming_dir
                }

                def _reg():
                    GEMINI_BROKER.release(self.tid)
                    self.current_job_id = None
                main_loop.call_soon_threadsafe(_reg)
            else:
                raise Exception('DOWNLOAD_START_FAILED')
                
        except Exception as e:
            log(f'{prefix} GEMINI_FAILED: {e}')
            ctx.error_message = f'Gemini failed: {e}'
            ctx.transition(JobState.FAILED)
            resolve_future_once(main_loop, future, None, is_exception=True)

            def _rel():
                GEMINI_BROKER.release(self.tid)
                self.current_job_id = None
            main_loop.call_soon_threadsafe(_rel)

class GeminiWorkerPool:
    def __init__(self, max_workers: int=GEMINI_WORKERS):
        self.max_workers = max_workers
        self.workers = {i: GeminiWorker(i) for i in range(max_workers)}

    def start_all(self):
        for i in range(self.max_workers):
            GEMINI_BROKER.release(i)
            
    def quit_all(self):
        pass

class WmrDriverThread(threading.Thread):
    def __init__(self, profile_id):
        super().__init__(daemon=True)
        self.profile_id = profile_id
        self.cmd_queue = queue.Queue()
        self.driver = None
        self.running = True
        self.wmr_tab_handles = {}

    def run(self):
        try:
            self.driver = create_wmr_chrome_driver(self.profile_id)
            log(f"[WMR-{self.profile_id}] Driver ready")
        except Exception as e:
            log(f"Failed to create driver for WMR profile {self.profile_id}: {e}")
            return
            
        while self.running:
            try:
                cmd = self.cmd_queue.get(timeout=1.0)
                if cmd is None:
                    break
                func, args, future = cmd
                try:
                    res = func(self.driver, self.wmr_tab_handles, *args)
                    if future and not future.done():
                        future.set_result(res)
                except Exception as e:
                    if future and not future.done():
                        future.set_exception(e)
            except queue.Empty:
                pass
        
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass

class WmrWorkerPool:
    def __init__(self, num_profiles):
        self.num_profiles = num_profiles
        self.threads = {}
        
    def start_all(self):
        for i in range(self.num_profiles):
            self.threads[i] = WmrDriverThread(i)
            self.threads[i].start()
            for t in range(WMR_TABS_PER_PROFILE):
                WMR_BROKER.release(f"W{i}-T{t}")
                
    def quit_all(self):
        for t in self.threads.values():
            t.running = False
            t.cmd_queue.put(None)

    async def execute_async(self, resource_id, func, *args):
        profile_id = int(resource_id.split('-')[0][1:])
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        cfut = concurrent.futures.Future()
        
        def _done(f):
            if loop.is_closed():
                return
            try:
                res = f.result()
                loop.call_soon_threadsafe(fut.set_result, res)
            except Exception as e:
                loop.call_soon_threadsafe(fut.set_exception, e)
                
        cfut.add_done_callback(_done)
        self.threads[profile_id].cmd_queue.put((func, args, cfut))
        return await fut

def _run_wmr_logic(driver, wmr_tab_handles, ctx: JobContext):
    resource_id = ctx.assigned_wmr_tab
    job_id = ctx.job_id
    prefix = f'[{resource_id}][{job_id}]'
    
    if not check_chrome_driver_health(driver)['alive']:
        raise RuntimeError(f'Driver for {resource_id} is dead')
        
    handle = wmr_tab_handles.get(resource_id)
    if handle:
        try:
            if handle in driver.window_handles:
                driver.switch_to.window(handle)
            else:
                handle = None
        except:
            handle = None
            
    if not handle:
        log(f'[{resource_id}] Creating new logical WMR tab...')
        driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
        for h in driver.window_handles:
            driver.switch_to.window(h)
            if driver.current_url == 'about:blank' or driver.current_url.startswith('data:'):
                wmr_tab_handles[resource_id] = h
                break
        if resource_id not in wmr_tab_handles:
            wmr_tab_handles[resource_id] = driver.window_handles[-1]
        driver.switch_to.window(wmr_tab_handles[resource_id])
    
    job_dir, incoming_dir = get_wmr_job_dir(0, job_id)
    profile_id = int(resource_id.split('-')[0][1:])
    staging_dir = Path(f'/content/downloads/wmr_staging/W{profile_id}')
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    driver.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(staging_dir)})
    
    if 'pixelcut.ai' not in driver.current_url:
        driver.get('https://www.pixelcut.ai/watermark-remover')
        
    time.sleep(1)
    
    inp = _wmr_find_file_input(driver)
    if not inp:
        raise Exception('WMR_FILE_INPUT_MISSING')
        
    inp.send_keys(str(ctx.raw_path))
    ctx.transition(JobState.WMR_PROCESSING)
    
    status = _wmr_check_status(driver)
    if status != 'SUCCESS':
        raise Exception(f'WMR_FAILED: {status}')
        
    files_before = set(staging_dir.iterdir()) if staging_dir.exists() else set()
    
    if not _wmr_click_download(driver):
        raise Exception('WMR_CLICK_DOWNLOAD_FAILED')
        
    ctx.transition(JobState.WMR_DOWNLOAD_CLICKED)
    
    dl_guid = None
    t1 = time.time()
    while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
        for entry in driver.get_log('performance'):
            try:
                msg = json.loads(entry['message'])['message']
                if msg['method'] == 'Browser.downloadWillBegin':
                    dl_guid = msg['params']['guid']
                    break
            except:
                pass
        if dl_guid:
            break
        time.sleep(0.1)
        
    dl_confirmed_fs = False
    t2 = time.time()
    while time.time() - t2 < DOWNLOAD_START_WINDOW_S:
        if staging_dir.exists():
            cur = set(staging_dir.iterdir())
            new_files = cur - files_before
            for nf in new_files:
                if nf.name.endswith('.crdownload') or nf.name.endswith('.png') or nf.name.endswith('.jpg') or nf.name.endswith('.webp'):
                    dl_confirmed_fs = True
                    break
        if dl_confirmed_fs:
            break
        time.sleep(0.1)
        
    if dl_confirmed_fs:
        ctx.wmr_download_guid = dl_guid or f'fs_fallback_{job_id}'
        ctx.transition(JobState.WMR_RESOURCE_RELEASED)
        
        download_registry[ctx.wmr_download_guid] = {
            'ctx': ctx,
            'type': 'WMR',
            'staging_dir': staging_dir,
            'files_before': files_before,
            'started_at': time.time(),
            'job_dir': job_dir,
            'incoming_dir': incoming_dir
        }
        
        def _reg():
            WMR_BROKER.release(resource_id)
        main_loop.call_soon_threadsafe(_reg)
    else:
        raise Exception('WMR_DOWNLOAD_START_FAILED')

async def poll_active_downloads():
    while True:
        try:
            completed_guids = []
            for guid, dinfo in list(download_registry.items()):
                ctx = dinfo['ctx']
                staging_dir = dinfo['staging_dir']
                files_before = dinfo['files_before']
                
                if not staging_dir.exists():
                    continue
                    
                cur = set(staging_dir.iterdir())
                new_files = cur - files_before
                
                crdownloads = [f for f in new_files if f.name.endswith('.crdownload')]
                if crdownloads:
                    continue
                    
                final_files = [f for f in new_files if f.name.endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                if not final_files:
                    if time.time() - dinfo['started_at'] > DOWNLOAD_TIMEOUT_S:
                        ctx.error_message = "Download timeout"
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                        completed_guids.append(guid)
                    continue
                    
                dl_file = final_files[0]
                
                sz1 = dl_file.stat().st_size
                await asyncio.sleep(0.5)
                sz2 = dl_file.stat().st_size
                if sz1 != sz2:
                    continue
                    
                if dinfo['type'] == 'GEMINI':
                    import shutil
                    raw_path = dinfo['job_dir'] / f"{ctx.job_id}_raw{dl_file.suffix}"
                    shutil.move(str(dl_file), str(raw_path))
                    ctx.raw_path = raw_path
                    try:
                        valid, msg = validate_image_file(str(raw_path), 512, 1024)
                        if not valid:
                            raise Exception(f"Invalid raw image: {msg}")
                        ctx.transition(JobState.RAW_READY)
                    except Exception as e:
                        ctx.error_message = str(e)
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                elif dinfo['type'] == 'WMR':
                    import shutil
                    clean_path = dinfo['job_dir'] / f"{ctx.job_id}_clean{dl_file.suffix}"
                    shutil.move(str(dl_file), str(clean_path))
                    ctx.clean_path = clean_path
                    try:
                        valid, msg = validate_image_file(str(clean_path), 512, 1024)
                        if not valid:
                            raise Exception(f"Invalid clean image: {msg}")
                        ctx.transition(JobState.CLEAN_READY)
                    except Exception as e:
                        ctx.error_message = str(e)
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                completed_guids.append(guid)
                
            for g in completed_guids:
                del download_registry[g]
        except Exception as e:
            traceback.print_exc()
        await asyncio.sleep(1.0)

def _finalize_job(ctx: JobContext):
    webp_path = convert_to_webp(str(ctx.clean_path))
    if not webp_path:
        raise Exception("WebP conversion failed")
    ctx.webp_path = Path(webp_path)
    ctx.transition(JobState.WEBP_READY)
    
    png_url, webp_url = upload_to_r2(str(ctx.clean_path), str(ctx.webp_path), ctx.job_id)
    if not png_url:
        raise Exception("R2 Upload failed")
    ctx.r2_png_url = png_url
    ctx.r2_webp_url = webp_url
    ctx.transition(JobState.R2_READY)
    
    db_success = False
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET output_url = %s, webp_url = %s, status = 'completed', updated_at = NOW() WHERE id = %s",
                           (ctx.r2_png_url, ctx.r2_webp_url, ctx.generation_id))
        db_success = True
    except Exception as e:
        log(f"DB Error: {e}")
        time.sleep(1)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET output_url = %s, webp_url = %s, status = 'completed', updated_at = NOW() WHERE id = %s",
                           (ctx.r2_png_url, ctx.r2_webp_url, ctx.generation_id))
        db_success = True
        
    ctx.transition(JobState.DB_READY)
    
    try:
        credits.settle(ctx.user_id, ctx.generation_id)
    except Exception as e:
        log(f"Credits settle warning: {e}")
        
    final_dir = get_final_output_dir(0, ctx.job_id)
    import shutil
    shutil.copy(str(ctx.clean_path), str(final_dir / f"{ctx.job_id}_final.png"))

async def process_job_pipeline(ctx: JobContext):
    ctx.transition(JobState.QUEUED)
    while True:
        tid = GEMINI_BROKER.acquire()
        if tid is not None:
            ctx.assigned_tid = tid
            break
        await asyncio.sleep(0.5)
        
    ctx.transition(JobState.GEMINI_ASSIGNED)
    gemini_pool.workers[ctx.assigned_tid].process_job(ctx)
    
    while ctx.state not in (JobState.RAW_READY, JobState.FAILED):
        await asyncio.sleep(0.5)
        
    if ctx.state == JobState.FAILED:
        return
        
    ctx.transition(JobState.WMR_QUEUED)
    while True:
        wid = WMR_BROKER.acquire()
        if wid is not None:
            ctx.assigned_wmr_tab = wid
            break
        await asyncio.sleep(0.5)
        
    ctx.transition(JobState.WMR_ASSIGNED)
    
    await wmr_pool.execute_async(ctx.assigned_wmr_tab, _run_wmr_logic, ctx)
    
    while ctx.state not in (JobState.CLEAN_READY, JobState.FAILED):
        await asyncio.sleep(0.5)
        
    if ctx.state == JobState.FAILED:
        return
        
    try:
        await asyncio.to_thread(_finalize_job, ctx)
        ctx.transition(JobState.COMPLETED)
        resolve_future_once(main_loop, ctx.future, ctx)
    except Exception as e:
        ctx.error_message = str(e)
        ctx.transition(JobState.FAILED)
        resolve_future_once(main_loop, ctx.future, None, is_exception=True)

async def process_bullmq_job(job):
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    
    ctx = JobContext(job.data, fut)
    job_contexts[ctx.job_id] = ctx
    
    asyncio.create_task(process_job_pipeline(ctx))
    
    try:
        res = await asyncio.wait_for(fut, timeout=TOTAL_JOB_TIMEOUT_S)
        return {"status": "success", "job_id": ctx.job_id}
    except asyncio.TimeoutError:
        ctx.error_message = "Global Job Timeout"
        ctx.transition(JobState.FAILED)
        raise Exception("Job timeout")
    except Exception as e:
        raise

def startup_preflight():
    global chrome_driver
    print("Checking directories...")
    for d in [STATE_DIR, CHROME_DL_BASE, CHROME_STAGING_BASE, WMR_STAGING_BASE, WMR_DL_BASE, FINAL_OUTPUT_BASE]:
        d.mkdir(parents=True, exist_ok=True)
        
    print("Checking Redis URL...")
    assert os.environ.get('REDIS_TUNNEL_URL'), "REDIS_TUNNEL_URL not set"
    
    print("Checking DB...")
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as e:
        print(f"Warning DB check failed: {e}")
            
    print("Checking Chrome Driver creation...")
    chrome_driver = create_persistent_chrome_driver()
    check_chrome_driver_health(chrome_driver)

async def main():
    global main_loop
    global gemini_pool
    global wmr_pool
    global GEMINI_BROKER
    global WMR_BROKER

    main_loop = asyncio.get_running_loop()

    log("[V14] Main asyncio loop acquired")
    
    print("===============================================================")
    print("STARTUP PREFLIGHT")
    startup_preflight()
    print("PREFLIGHT SUCCESSFUL")
    print("===============================================================")

    # ------------------------------------------------------------
    # INITIALIZE BROKERS
    # ------------------------------------------------------------
    GEMINI_BROKER = FirstFreeBroker()
    WMR_BROKER = FirstFreeBroker()

    # ------------------------------------------------------------
    # INITIALIZE GEMINI POOL
    # ------------------------------------------------------------
    gemini_pool = GeminiWorkerPool(GEMINI_WORKERS)
    gemini_pool.start_all()

    # ------------------------------------------------------------
    # INITIALIZE WMR POOL
    # ------------------------------------------------------------
    wmr_pool = WmrWorkerPool(WMR_WORKERS)
    wmr_pool.start_all()

    # ------------------------------------------------------------
    # START BACKGROUND TASKS
    # ------------------------------------------------------------
    download_task = asyncio.create_task(
        poll_active_downloads(),
        name="v14-download-monitor"
    )

    # ------------------------------------------------------------
    # BULLMQ WORKER
    # ------------------------------------------------------------
    redis_url = os.environ.get('REDIS_TUNNEL_URL')
    
    worker = Worker(
        QUEUE_NAME,
        process_bullmq_job,
        {
            "connection": redis_url,
            "prefix": "vastralook:",
            "concurrency": BULLMQ_CONCURRENCY,
        },
    )

    log(
        f"[V14] READY | "
        f"Gemini={GEMINI_WORKERS} | "
        f"WMR={WMR_WORKERS}x{WMR_TABS_PER_PROFILE} | "
        f"BullMQ={BULLMQ_CONCURRENCY}"
    )

    try:
        # Keep the current asyncio loop alive.
        await asyncio.Event().wait()

    except asyncio.CancelledError:
        log("[V14] Main task cancelled")

    finally:
        log("[V14] Shutdown started")

        for task in (download_task,):
            task.cancel()

        await asyncio.gather(
            download_task,
            return_exceptions=True,
        )

        try:
            await worker.close()
        except Exception as e:
            log(f"[V14] BullMQ shutdown warning: {e}")

        try:
            if gemini_pool:
                gemini_pool.quit_all()
        except Exception as e:
            log(f"[V14] Gemini shutdown warning: {e}")

        try:
            if wmr_pool:
                wmr_pool.quit_all()
        except Exception as e:
            log(f"[V14] WMR shutdown warning: {e}")

        log("[V14] Shutdown complete")

def is_running_in_notebook():
    try:
        from IPython import get_ipython
        return get_ipython() is not None
    except Exception:
        return False

def run_worker():
    if is_running_in_notebook():
        raise RuntimeError(
            "V14 is running inside Jupyter/Colab. "
            "Use: await main()"
        )

    asyncio.run(main())

if __name__ == "__main__":
    run_worker()
''')

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as f:
    f.write("\n".join(out_lines))
