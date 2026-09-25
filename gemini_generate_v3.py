#!/usr/bin/env python3
"""gemini_generate_v3.py — Aggressive Tab Management + Edge WMR Pipeline

ARCHITECTURE:
  Chrome (logged-in profile) → Gemini image generation (multiple tabs)
  Edge   (no login, fresh)   → Watermark removal (background thread)

TAB MANAGEMENT:
  1. Job from queue → dispatch to idle tab → upload + prompt + send
  2. Don't wait — immediately dispatch next job to next idle tab
  3. Round-robin poll all generating tabs
  4. Download from whichever tab finishes first
  5. Queue downloaded image for Edge WMR (background)
  6. Tab becomes idle → dispatch next job

DOWNLOAD FOLDERS:
  generated/
    tab_0/   ← Tab 0 downloads here
    tab_1/   ← Tab 1 downloads here
    ...
  wmr_clean/
    tab_0/   ← Edge WMR output for tab 0
    tab_1/   ← Edge WMR output for tab 1
    ...
"""

import argparse
import base64
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
import gemini_login as gl

# ═══════════════════════════════════════════════════════════════════════
# EMBEDDED DATA (set by caller / notebook before exec)
# ═══════════════════════════════════════════════════════════════════════
EMBEDDED_COOKIES_B64            = globals().get('EMBEDDED_COOKIES_B64')
EMBEDDED_IMAGE_B64              = globals().get('EMBEDDED_IMAGE_B64')
EMBEDDED_IMAGE_EXT              = globals().get('EMBEDDED_IMAGE_EXT')
EMBEDDED_MODEL_IMAGE_B64        = globals().get('EMBEDDED_MODEL_IMAGE_B64')
EMBEDDED_MODEL_IMAGE_EXT        = globals().get('EMBEDDED_MODEL_IMAGE_EXT')
EMBEDDED_HOLOGRAM_IMAGE_B64     = globals().get('EMBEDDED_HOLOGRAM_IMAGE_B64')
EMBEDDED_HOLOGRAM_IMAGE_EXT     = globals().get('EMBEDDED_HOLOGRAM_IMAGE_EXT')
EMBEDDED_BATCH_B64              = globals().get('EMBEDDED_BATCH_B64')
EMBEDDED_IMAGE_REMOTE           = globals().get('EMBEDDED_IMAGE_REMOTE')
EMBEDDED_MODEL_IMAGE_REMOTE     = globals().get('EMBEDDED_MODEL_IMAGE_REMOTE')
EMBEDDED_CHROME_PROFILE_REMOTE  = globals().get('EMBEDDED_CHROME_PROFILE_REMOTE')

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════
GEMINI_URL = 'https://gemini.google.com/app'
WMR_URL    = 'https://app.gemini-logo-remover.workers.dev/gemini'

LIMIT_PHRASES = [
    "you've reached your image-generation limit",
    'reached your image-generation limit',
    'image-generation limit',
    "can't generate more images for you today",
    'come back tomorrow',
    "you've reached your limit",
    'reached your daily limit',
    'rate limit',
    'too many requests',
]
REFUSAL_PHRASES = [
    "can't create images of",
    'cannot create images of',
    "i'm not able to create that image",
    "i'm unable to create that image",
    "i can't create this image",
]
FALLBACK_MODELS = ['3.7 Flash', '3.5 Flash-Lite']

# ═══════════════════════════════════════════════════════════════════════
# SELENIUM GLOBALS (set in main())
# ═══════════════════════════════════════════════════════════════════════
By = None
Keys = None
ActionChains = None

_MODEL_TRIGGER_SELECTOR = (
    "button[aria-label*='model' i], "
    "button[class*='model-switcher' i], "
    "button[data-test-id*='model' i], "
    "bard-mode-switcher button, "
    "button[class*='mode-switcher' i]"
)

_PERSISTENT_DRIVER  = globals().get('_PERSISTENT_DRIVER')
_PERSISTENT_VNC_URL = globals().get('_PERSISTENT_VNC_URL')


# ═══════════════════════════════════════════════════════════════════════
#  UI HELPERS — Gemini web automation
# ═══════════════════════════════════════════════════════════════════════

def check_limit_or_refusal(drv):
    try:
        body = drv.find_element(By.TAG_NAME, 'body').text.lower()
    except Exception:
        return None
    for p in REFUSAL_PHRASES:
        if p in body:
            return 'refusal'
    for p in LIMIT_PHRASES:
        if p in body:
            return 'limit'
    return None


def open_gemini_tab(drv, url=GEMINI_URL, wait_sec=1.0):
    try:
        before = set(drv.window_handles)
        drv.execute_cdp_cmd('Target.createTarget', {'url': url})
        new_handle = None
        deadline = time.time() + wait_sec
        while time.time() < deadline:
            diff = set(drv.window_handles) - before
            if diff:
                new_handle = next(iter(diff))
                break
            time.sleep(0.03)
        if not new_handle:
            handles = drv.window_handles
            if len(handles) > len(before):
                new_handle = handles[-1]
        if not new_handle:
            return False
        drv.switch_to.window(new_handle)
        time.sleep(wait_sec)
        return True
    except Exception:
        return False


def close_other_tabs(drv, keep_handle):
    try:
        for h in list(drv.window_handles):
            if h != keep_handle:
                try:
                    drv.switch_to.window(h)
                    drv.close()
                except Exception:
                    pass
        drv.switch_to.window(keep_handle)
    except Exception:
        pass


def start_new_chat(drv):
    for sel in [
        'a[aria-label="New chat"]',
        'button[aria-label="New chat"]',
        'div[aria-label="New chat"]',
        '[data-test-id="new-chat-button"]',
    ]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    drv.execute_script('arguments[0].click();', el)
                    time.sleep(1.0)
                    return True
        except Exception:
            continue
    return False


def click_plus_button(drv):
    for sel in [
        'button[aria-label="Upload and tools"]',
        'button[aria-haspopup="menu"][aria-label*="Upload"]',
        'button[jslog*="300142"]',
    ]:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script('arguments[0].click();', btn)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue
    try:
        result = drv.execute_script('''
            var btns=document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                var b=btns[i];
                if(b.offsetParent!==null){
                    var lbl=(b.getAttribute('aria-label')||'').toLowerCase();
                    if(lbl.indexOf('upload')!==-1||lbl.indexOf('tools')!==-1){
                        b.click();return 'OK';
                    }
                    var icon=b.querySelector('mat-icon[fonticon="plus"],mat-icon[data-mat-icon-name="plus"]');
                    if(icon){b.click();return 'OK';}
                }
            } return 'NO';
        ''')
        if result == 'OK':
            time.sleep(0.4)
            return True
    except Exception:
        pass
    return False


def click_menu_item(drv, texts):
    texts_l = [t.lower() for t in texts]
    try:
        candidates = drv.find_elements(By.CSS_SELECTOR,
            "button, [role='menuitem'], [role='menuitemcheckbox']")
        for el in candidates:
            try:
                if not el.is_displayed():
                    continue
                label = (el.text or el.get_attribute('aria-label') or '').strip().lower()
                if label and any(t in label for t in texts_l):
                    drv.execute_script('arguments[0].click();', el)
                    time.sleep(0.5)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def click_create_image(drv):
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR,
                "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button"):
            if btn.is_displayed() and 'Create image' in btn.text:
                drv.execute_script('arguments[0].click();', btn)
                time.sleep(0.35)
                return True
    except Exception:
        pass
    try:
        for icon in drv.find_elements(By.CSS_SELECTOR,
                "mat-icon[data-mat-icon-name='image_create'],mat-icon[fonticon='image_create']"):
            if not icon.is_displayed():
                continue
            btn = drv.execute_script(
                "var e=arguments[0]; while(e&&e.tagName!=='BUTTON') e=e.parentElement; return e;", icon)
            if btn and btn.is_displayed():
                drv.execute_script('arguments[0].click();', btn)
                time.sleep(0.35)
                return True
    except Exception:
        pass
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[jslog*='271906']"):
            if btn.is_displayed():
                drv.execute_script('arguments[0].click();', btn)
                time.sleep(0.35)
                return True
    except Exception:
        pass
    return click_menu_item(drv, ['create image', 'create images'])


def _in_image_mode(drv):
    try:
        if drv.find_elements(By.CSS_SELECTOR,
                "div.ql-editor[data-placeholder='Describe your image']"):
            return True
        for c in drv.find_elements(By.CSS_SELECTOR,
                "button[aria-label='Deselect Images'],span.gds-body-s"):
            if c.is_displayed() and 'Images' in c.text:
                return True
    except Exception:
        pass
    return False


def wait_for_image_mode(drv, timeout=4.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _in_image_mode(drv):
            return True
        time.sleep(0.15)
    return False


def activate_create_image_mode(drv, status=None, tag='', attempts=3):
    if _in_image_mode(drv):
        if status:
            status.update(message=f"STEP_ACTIVATE_IMAGE_MODE: Already active. {tag}".strip())
        return True
    for attempt in range(attempts):
        if status:
            status.update(message=f"STEP_ACTIVATE_IMAGE_MODE: Opening tools menu... {tag}".strip())
        if not click_plus_button(drv):
            time.sleep(0.5)
            continue
        if not click_create_image(drv):
            try:
                drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            except Exception:
                pass
            time.sleep(0.5)
            continue
        if wait_for_image_mode(drv, timeout=4.0):
            if status:
                status.update(message=f"STEP_ACTIVATE_IMAGE_MODE: Switched OK. {tag}".strip())
            return True
        try:
            drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _current_model_label(drv):
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, _MODEL_TRIGGER_SELECTOR):
            if btn.is_displayed():
                return (btn.text or btn.get_attribute('aria-label') or '').strip().lower()
    except Exception:
        pass
    return ''


def select_gemini_model(drv, model_query, status, attempts=3):
    q = model_query.strip().lower()
    if q in _current_model_label(drv):
        return True
    for attempt in range(attempts):
        try:
            opened = False
            for btn in drv.find_elements(By.CSS_SELECTOR, _MODEL_TRIGGER_SELECTOR):
                try:
                    if btn.is_displayed():
                        drv.execute_script('arguments[0].click();', btn)
                        time.sleep(0.4)
                        opened = True
                        break
                except Exception:
                    continue
            if not opened:
                status.update(message="STEP_SELECT_MODEL: Switcher not found — using default.")
                return False
            clicked = False
            for cand in drv.find_elements(By.CSS_SELECTOR,
                    "[role='menuitem'], [role='menuitemradio'], button"):
                try:
                    if not cand.is_displayed():
                        continue
                    label = (cand.text or cand.get_attribute('aria-label') or '').strip().lower()
                    if label and q in label:
                        drv.execute_script('arguments[0].click();', cand)
                        time.sleep(0.4)
                        clicked = True
                        break
                except Exception:
                    continue
            if clicked and q in _current_model_label(drv):
                status.update(message=f"STEP_SELECT_MODEL: Selected '{model_query}'.")
                return True
        except Exception as e:
            status.update(message=f'STEP_SELECT_MODEL: attempt failed ({e}), retrying...')
        try:
            drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except Exception:
            pass
        time.sleep(0.4)
    status.update(message=f"STEP_SELECT_MODEL: No match for '{model_query}' — using default.")
    return False


def handle_consent(drv):
    try:
        for bsel in [
            "button[data-test-id='upload-image-agree-button']",
            "//button[.//span[contains(text(),'Agree')]]",
            "//span[text()='Agree']/ancestor::button",
        ]:
            try:
                by = By.XPATH if bsel.startswith('//') else By.CSS_SELECTOR
                btn = drv.find_element(by, bsel)
                if btn and btn.is_displayed():
                    drv.execute_script('arguments[0].click();', btn)
                    time.sleep(0.15)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def click_upload_files_in_drawer(drv):
    for sel in ["button[data-test-id='local-images-files-uploader-button']"]:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script('arguments[0].click();', btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    for xp in [
        "//span[contains(text(),'Upload files')]/ancestor::button",
        "//div[contains(text(),'Upload files')]/ancestor::button",
    ]:
        try:
            for btn in drv.find_elements(By.XPATH, xp):
                if btn.is_displayed():
                    drv.execute_script('arguments[0].click();', btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    try:
        result = drv.execute_script("""
            var btns=document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].offsetParent!==null &&
                   btns[i].textContent.toLowerCase().indexOf('upload files')!==-1){
                    btns[i].click();return 'OK';
                }
            } return 'NO';
        """)
        if result == 'OK':
            time.sleep(0.3)
            return True
    except Exception:
        pass
    return False


def find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs:
        return inputs[0]
    try:
        drv.execute_script('''
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;'
                    +'position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
            });
        ''')
    except Exception:
        pass
    time.sleep(0.1)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None


def wait_for_attachment_chip(drv, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR,
                    'button[aria-label="close attachment"]'):
                if el.is_displayed():
                    return True
            for chip in drv.find_elements(By.CSS_SELECTOR,
                    'gem-media-attachment,uploader-file-preview'):
                if chip.is_displayed():
                    return True
            for w in drv.find_elements(By.CSS_SELECTOR,
                    '.attachment-preview-wrapper,uploader-file-preview-container'):
                if w.is_displayed():
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def jsdrop_single(drv, image_path):
    try:
        abs_path = os.path.abspath(image_path)
        if os.path.getsize(abs_path) > 10_000_000:
            return False
        with open(abs_path, 'rb') as f:
            b64_data = base64.b64encode(f.read()).decode('ascii')
        ext = os.path.splitext(abs_path)[1].lower()
        mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.webp': 'image/webp'}.get(ext, 'image/jpeg')
        fname = os.path.basename(abs_path)
        result = drv.execute_script('''
            var b64=arguments[0],mime=arguments[1],fname=arguments[2];
            var binary=atob(b64);var arr=new Uint8Array(binary.length);
            for(var i=0;i<binary.length;i++) arr[i]=binary.charCodeAt(i);
            var blob=new Blob([arr],{type:mime});
            var file=new File([blob],fname,{type:mime,lastModified:Date.now()});
            var dt=new DataTransfer();dt.items.add(file);
            var sels=['rich-textarea','.ql-editor','div[contenteditable="true"]','.input-area-container'];
            for(var s=0;s<sels.length;s++){
                var targets=document.querySelectorAll(sels[s]);
                for(var t=0;t<targets.length;t++){
                    var el=targets[t];if(el.offsetParent===null) continue;
                    el.dispatchEvent(new DragEvent('dragenter',{dataTransfer:dt,bubbles:true}));
                    el.dispatchEvent(new DragEvent('dragover',{dataTransfer:dt,bubbles:true}));
                    el.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}));
                    return 'OK';
                }
            } return 'NO';
        ''', b64_data, mime, fname)
        time.sleep(0.3)
        handle_consent(drv)
        return result == 'OK'
    except Exception:
        return False


def upload_images(drv, image_paths, status, timeout=30):
    if len(image_paths) > 1 and _attach_images_together(drv, image_paths, status, timeout):
        return
    for i, image_path in enumerate(image_paths):
        _attach_one_image(drv, image_path, status, i + 1, len(image_paths), timeout)


def _attach_images_together(drv, image_paths, status, timeout=30):
    try:
        paths = [str(Path(p).resolve()) for p in image_paths]
        for p in paths:
            if not os.path.exists(p):
                return False
        status.update(message=f"STEP_UPLOAD_REFS: Batch-uploading {len(paths)} refs at once...")
        if not click_plus_button(drv):
            return False
        if not click_upload_files_in_drawer(drv):
            try:
                drv.execute_script('''
                    var b=document.querySelector(
                        'button.hidden-local-file-image-selector-button,'
                        +'button[data-test-id="hidden-local-image-upload-button"],'
                        +'button[xapfileselectortrigger]');
                    if(b) b.click();
                ''')
                time.sleep(0.15)
            except Exception:
                pass
        handle_consent(drv)
        file_input = find_file_input(drv)
        if file_input is None:
            return False
        names = ', '.join(os.path.basename(p) for p in paths)
        status.update(message=f'STEP_UPLOAD_REFS: Sending {len(paths)} files: {names}')
        try:
            file_input.send_keys('\n'.join(paths))
        except Exception:
            return False
        handle_consent(drv)
        if not wait_for_attachment_chip(drv, timeout=timeout):
            return False
        time.sleep(1.2 * len(paths))
        status.update(message=f'STEP_UPLOAD_REFS: {len(paths)} files attached OK')
        return True
    except Exception:
        return False


def _attach_one_image(drv, image_path, status, index, total, timeout=30):
    image_path = str(Path(image_path).resolve())
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'image not found: {image_path}')
    tag = f'({index}/{total})' if total > 1 else ''
    status.update(message=f"STEP_UPLOAD_REFS: Opening tools menu... {tag}".strip())
    if not click_plus_button(drv):
        raise RuntimeError(f"STEP_UPLOAD_REFS: could not open tools menu {tag}".strip())
    if not click_upload_files_in_drawer(drv):
        try:
            drv.execute_script('''
                var b=document.querySelector(
                    'button.hidden-local-file-image-selector-button,'
                    +'button[data-test-id="hidden-local-image-upload-button"],'
                    +'button[xapfileselectortrigger]');
                if(b) b.click();
            ''')
            time.sleep(0.15)
        except Exception:
            pass
    handle_consent(drv)
    sent_via = None
    file_input = find_file_input(drv)
    if file_input is not None:
        try:
            file_input.send_keys(image_path)
            sent_via = 'input'
        except Exception:
            pass
    if sent_via is None:
        if jsdrop_single(drv, image_path):
            sent_via = 'jsdrop'
    if sent_via is None:
        raise RuntimeError("STEP_UPLOAD_REFS: could not attach file")
    handle_consent(drv)
    if not wait_for_attachment_chip(drv, timeout=timeout):
        time.sleep(3)
    status.update(message=f'STEP_UPLOAD_REFS: Uploaded {os.path.basename(image_path)} {tag}'.strip())
    return True


def get_editor(drv):
    for sel in [
        "div.ql-editor[data-placeholder='Describe your image']",
        "div.ql-editor[contenteditable='true']",
        "div[contenteditable='true']",
    ]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return el
        except Exception:
            pass
    return None


def _strip_ws(text):
    return re.sub('\\s+', '', text)


def _verify_editor_content(drv, editor, expected_text, timeout=4.0):
    first40 = _strip_ws(expected_text[:80])[:40]
    min_len = int(len(_strip_ws(expected_text)) * 0.5)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            content = drv.execute_script(
                "return (arguments[0].textContent||'').trim();", editor) or ''
            content = _strip_ws(content)
            if len(content) >= min_len and first40 in content:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def _clear_editor(drv, editor):
    try:
        drv.execute_script('arguments[0].focus();', editor)
        drv.execute_script(
            "document.execCommand('selectAll',false,null);"
            "document.execCommand('delete',false,null);")
        time.sleep(0.05)
    except Exception:
        pass


def type_prompt(drv, text):
    editor = None
    deadline = time.time() + 10
    while time.time() < deadline:
        editor = get_editor(drv)
        if editor:
            break
        time.sleep(0.3)
    if not editor:
        raise RuntimeError('STEP_TYPE_PROMPT: could not find prompt box')
    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", editor)
    time.sleep(0.1)
    _clear_editor(drv, editor)
    try:
        drv.execute_script("document.execCommand('insertText',false,arguments[0]);", text)
        time.sleep(0.3)
        if _verify_editor_content(drv, editor, text, timeout=4.0):
            return True
    except Exception:
        pass
    _clear_editor(drv, editor)
    try:
        drv.execute_script('arguments[0].focus();', editor)
        chunk = 500
        lines = text.split('\n')
        for li, line in enumerate(lines):
            for i in range(0, len(line), chunk):
                editor.send_keys(line[i:i + chunk])
                time.sleep(0.03)
            if li != len(lines) - 1:
                ActionChains(drv).key_down(Keys.SHIFT).send_keys(
                    Keys.RETURN).key_up(Keys.SHIFT).perform()
                time.sleep(0.03)
        time.sleep(0.3)
        if _verify_editor_content(drv, editor, text, timeout=6.0):
            return True
    except Exception:
        pass
    raise RuntimeError('STEP_TYPE_PROMPT: could not verify prompt was typed')


def click_send(drv):
    try:
        result = drv.execute_script('''
            var icons=document.querySelectorAll(
                'mat-icon[fonticon="arrow_upward"],mat-icon[data-mat-icon-name="arrow_upward"]');
            for(var i=0;i<icons.length;i++){
                var b=icons[i].closest('button');
                if(b&&!b.disabled&&b.offsetParent!==null){b.click();return 'OK_UP';}
            }
            var sendIcons=document.querySelectorAll(
                'mat-icon[fonticon="send"],mat-icon[data-mat-icon-name="send"]');
            for(var i=0;i<sendIcons.length;i++){
                var b=sendIcons[i].closest('button');
                if(b&&!b.disabled&&b.offsetParent!==null){b.click();return 'OK_SEND';}
            }
            var btns=document.querySelectorAll(
                'button[aria-label="Send message"],button[data-test-id="send-button"]');
            for(var i=0;i<btns.length;i++){
                if(!btns[i].disabled&&btns[i].offsetParent!==null){btns[i].click();return 'OK_ARIA';}
            }
            return 'NO';
        ''')
        if result and result.startswith('OK'):
            return True
    except Exception:
        pass
    for sel in [
        "button[aria-label='Send message']",
        "button[data-test-id='send-button']",
        "button[aria-label*='Send']",
    ]:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script('arguments[0].click();', btn)
                    return True
        except Exception:
            continue
    return False


def snapshot_urls(drv):
    try:
        return set(drv.execute_script(
            'return Array.from(document.querySelectorAll('
            '\'img[src^="blob:"],img[src*="googleusercontent"]\'))'
            '.map(i=>i.src).filter(s=>s&&s.length>10);') or [])
    except Exception:
        return set()


def check_new_image(drv, urls_before):
    try:
        new_srcs = drv.execute_script('''
            var srcs=[];
            var imgs=document.querySelectorAll(
                'img[src^="blob:https://gemini.google.com"]');
            for (var i=imgs.length-1;i>=0;i--){
                var img=imgs[i]; if(!img.offsetParent) continue;
                var src=img.getAttribute('src')||'';
                var tid=img.getAttribute('data-test-id')||'';
                if (tid.includes('uploaded-img')) continue;
                if (src.length>10) srcs.push(src);
            } return srcs;
        ''') or []
        for src in new_srcs:
            if src not in urls_before:
                return src
    except Exception:
        pass
    return None


def check_new_image_lenient(drv, urls_before):
    try:
        new_srcs = drv.execute_script('''
            var srcs=[];
            var imgs=document.querySelectorAll(
                'img[src^="blob:https://gemini.google.com"]');
            for (var i=imgs.length-1;i>=0;i--){
                var img=imgs[i]; if(!img.offsetParent) continue;
                var src=img.getAttribute('src')||'';
                if (src.length>10) srcs.push(src);
            } return srcs;
        ''') or []
        for src in new_srcs:
            if src not in urls_before:
                return src
    except Exception:
        pass
    return None


def set_download_behavior(drv, download_dir):
    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': os.path.abspath(download_dir)})
        return True
    except Exception:
        return False


def _direct_fetch_image(drv, save_path, urls_before):
    try:
        blob = drv.execute_script('''
            var imgs=document.querySelectorAll(
                'single-image img,generated-image img,'
                'img[src^="blob:https://gemini.google.com"]');
            for (var i=imgs.length-1;i>=0;i--){
                var s=imgs[i].getAttribute('src');
                if (s && s.startsWith('blob:https://gemini.google.com')) return s;
            } return null;
        ''')
        if not blob or blob in urls_before:
            return False
        result = drv.execute_cdp_cmd('Runtime.evaluate', {
            'expression': (
                f"fetch('{blob}').then(r=>r.blob()).then(b=>new Promise(resolve=>"
                "{const fr=new FileReader();fr.onloadend=()=>resolve(fr.result.split(',')[1]);"
                "fr.readAsDataURL(b);}));"
            ),
            'awaitPromise': True, 'returnByValue': True,
        })
        if result and 'result' in result and 'value' in result['result']:
            data = base64.b64decode(result['result']['value'])
            if len(data) > 5000:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                Path(save_path).write_bytes(data)
                return True
    except Exception:
        pass
    return False


def _click_download_button(drv):
    selectors = [
        ('css', "button[data-test-id='download-generated-image-button']"),
        ('css', "button[aria-label='Download']"),
        ('css', "button[aria-label='Download image']"),
        ('css', "button[aria-label*='Download']"),
        ('xpath', "//button[contains(@aria-label,'Download')]"),
        ('xpath', "//mat-icon[contains(@fonticon,'download')]/ancestor::button"),
    ]
    for by_type, sel in selectors:
        try:
            by = By.XPATH if by_type == 'xpath' else By.CSS_SELECTOR
            for btn in reversed(drv.find_elements(by, sel)):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(0.1)
                    drv.execute_script('arguments[0].click();', btn)
                    return True
        except Exception:
            continue
    return False


def _hover_and_download(drv, urls_before):
    try:
        drv.execute_script('window.scrollTo(0,document.body.scrollHeight);')
        time.sleep(0.4)
    except Exception:
        pass
    for sel in ('single-image img', 'generated-image img',
                "img[src^='blob:https://gemini.google.com']"):
        try:
            imgs = list(reversed(drv.find_elements(By.CSS_SELECTOR, sel)))
        except Exception:
            continue
        for img in imgs:
            try:
                src = img.get_attribute('src') or ''
                tid = img.get_attribute('data-test-id') or ''
                if 'uploaded-img' in tid or tid == 'image-preview':
                    continue
                if src in urls_before or len(src) < 10 or not img.is_displayed():
                    continue
                drv.execute_script(
                    "arguments[0].scrollIntoView({block:'center',behavior:'smooth'});", img)
                time.sleep(0.4)
                try:
                    ActionChains(drv).move_to_element(img).perform()
                    time.sleep(0.5)
                    if _click_download_button(drv):
                        return True
                except Exception:
                    pass
                try:
                    drv.execute_script("""
                        var el=arguments[0];
                        ['mouseenter','mouseover','mousemove'].forEach(function(evt){
                            el.dispatchEvent(new MouseEvent(evt,{bubbles:true,cancelable:true,
                                view:window,
                                clientX:el.getBoundingClientRect().left+el.offsetWidth/2,
                                clientY:el.getBoundingClientRect().top+el.offsetHeight/2}));
                        });
                    """, img)
                    time.sleep(0.5)
                    if _click_download_button(drv):
                        return True
                except Exception:
                    pass
            except Exception:
                continue
    return False


def _wait_for_download(dl_dir, files_before, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            cur = set(os.listdir(dl_dir))
            new_files = {
                f for f in cur - files_before
                if not f.endswith(('.crdownload', '.tmp', '.part'))
                and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
            }
            if new_files:
                fname = sorted(new_files,
                    key=lambda f: os.path.getmtime(os.path.join(dl_dir, f)),
                    reverse=True)[0]
                fpath = os.path.join(dl_dir, fname)
                if os.path.getsize(fpath) > 5000:
                    return fpath
        except Exception:
            pass
        time.sleep(0.4)
    return None


def download_image(drv, save_path, urls_before, download_dir, retries=3):
    if _direct_fetch_image(drv, save_path, urls_before):
        return True
    os.makedirs(download_dir, exist_ok=True)
    for _ in range(retries):
        try:
            files_before_dl = set(os.listdir(download_dir))
            drv.execute_script('window.scrollTo(0,document.body.scrollHeight);')
            time.sleep(0.3)
            hover_ok = _hover_and_download(drv, urls_before)
            fpath = _wait_for_download(download_dir,
                files_before_dl, timeout=30 if hover_ok else 8)
            if fpath:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                try:
                    Path(fpath).rename(save_path)
                except Exception:
                    Path(save_path).write_bytes(Path(fpath).read_bytes())
                if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return _direct_fetch_image(drv, save_path, urls_before)


def save_debug_screenshot(drv, output_dir, tag):
    try:
        debug_dir = Path(output_dir) / 'debug'
        debug_dir.mkdir(parents=True, exist_ok=True)
        path = debug_dir / f'{tag}.png'
        drv.save_screenshot(str(path))
        return str(path)
    except Exception:
        return None


def convert_to_webp(png_path, max_size_kb=400, min_quality=20, downscale_floor=0.5):
    try:
        from PIL import Image
    except ImportError:
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'Pillow'],
                timeout=60, capture_output=True)
            from PIL import Image
        except Exception:
            return None
    import io as _io
    try:
        webp_path = os.path.splitext(png_path)[0] + '.webp'
        img = Image.open(png_path)
        img.load()
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA' if img.mode in ('P', 'LA', 'PA') else 'RGB')
        orig_w, orig_h = img.size

        def encode(working, quality):
            buf = _io.BytesIO()
            working.save(buf, format='WEBP', quality=quality, method=4)
            return buf.getvalue()

        scale = 1.0
        while scale >= downscale_floor:
            working = img if scale >= 0.999 else img.resize(
                (max(64, int(orig_w * scale)), max(64, int(orig_h * scale))),
                Image.Resampling.LANCZOS)
            if len(encode(working, min_quality)) / 1024 > max_size_kb:
                scale -= 0.1
                continue
            low, high, best_q = min_quality, 95, min_quality
            while low <= high:
                mid = (low + high) // 2
                if len(encode(working, mid)) / 1024 <= max_size_kb:
                    best_q = mid
                    low = mid + 1
                else:
                    high = mid - 1
            Path(webp_path).write_bytes(encode(working, best_q))
            return webp_path
        working = img.resize(
            (max(64, int(orig_w * downscale_floor)),
             max(64, int(orig_h * downscale_floor))),
            Image.Resampling.LANCZOS)
        Path(webp_path).write_bytes(encode(working, min_quality))
        return webp_path
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
#  EDGE BROWSER — WATERMARK REMOVAL (runs in background thread)
# ═══════════════════════════════════════════════════════════════════════

def find_edge():
    """Find Microsoft Edge binary on the system."""
    candidates = [
        '/usr/bin/microsoft-edge-stable',
        '/usr/bin/microsoft-edge',
        '/opt/microsoft/msedge/msedge',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    for name in ('microsoft-edge-stable', 'microsoft-edge', 'msedge'):
        found = shutil.which(name)
        if found:
            return found
    return None


def make_edge_driver(edge_bin, download_dir, screen_w=1280, screen_h=900):
    """Create Edge WebDriver — fresh profile, NO login needed."""
    from selenium import webdriver as _wd
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from webdriver_manager.microsoft import EdgeChromiumDriverManager

    opts = EdgeOptions()
    opts.binary_location = edge_bin
    opts.add_argument(f'--window-size={screen_w},{screen_h}')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--headless=new')   # Edge WMR needs no visible window
    opts.add_experimental_option('prefs', {
        'download.default_directory': os.path.abspath(download_dir),
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
    })
    svc = EdgeService(EdgeChromiumDriverManager().install())
    d = _wd.Edge(service=svc, options=opts)
    d.set_page_load_timeout(60)
    d.implicitly_wait(3)
    return d


def _edge_find_file_input(drv):
    """Find file input on the WMR page (Edge)."""
    try:
        inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if inputs:
            return inputs[0]
    except Exception:
        pass
    try:
        drv.execute_script('''
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;'
                    +'position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                el.removeAttribute('hidden');
                el.removeAttribute('disabled');
            });
        ''')
    except Exception:
        pass
    time.sleep(0.3)
    try:
        inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
        return inputs[0] if inputs else None
    except Exception:
        return None


def _edge_check_wmr_status(drv):
    """Check watermark removal status on the WMR page (Edge)."""
    try:
        result = drv.execute_script("""
            function findDownloadBtn() {
                var btn = document.querySelector('button.bg-success');
                if (btn && !btn.disabled) {
                    var style = window.getComputedStyle(btn);
                    if (style.display !== 'none' && style.visibility !== 'hidden') return btn;
                }
                var spans = document.querySelectorAll('span');
                for (var i = 0; i < spans.length; i++) {
                    if ((spans[i].textContent || '').trim() === 'Download PNG') {
                        var b = spans[i].closest('button');
                        if (b && !b.disabled) return b;
                    }
                }
                return null;
            }
            if (findDownloadBtn()) return 'DONE';
            var allText = document.body ? document.body.innerText.toLowerCase() : '';
            if (allText.indexOf('detecting') !== -1 || allText.indexOf('processing') !== -1)
                return 'BUSY';
            if (allText.indexOf('not detected') !== -1 || allText.indexOf('no watermark') !== -1)
                return findDownloadBtn() ? 'DONE' : 'NOT_FOUND';
            if (allText.length < 10) return 'LOADING';
            return 'BUSY';
        """)
        return (result or 'error').lower()
    except Exception:
        return 'error'


def _edge_click_download(drv):
    """Click download button on WMR page (Edge)."""
    try:
        result = drv.execute_script("""
            var btn = document.querySelector('button.bg-success');
            if (btn && !btn.disabled) {
                btn.scrollIntoView({block:'center'}); btn.click(); return 'OK';
            }
            var spans = document.querySelectorAll('span');
            for (var i = 0; i < spans.length; i++) {
                if ((spans[i].textContent || '').trim() === 'Download PNG') {
                    var b = spans[i].closest('button');
                    if (b && !b.disabled) {
                        b.scrollIntoView({block:'center'}); b.click(); return 'OK';
                    }
                }
            }
            return null;
        """)
        return result == 'OK'
    except Exception:
        return False


def _edge_process_single(edge_drv, image_path, wmr_dl_dir, timeout=60):
    """Process one image through Edge WMR. Returns True if watermark removed."""
    try:
        edge_drv.get(WMR_URL)
        time.sleep(1.5)
        set_download_behavior(edge_drv, wmr_dl_dir)

        file_input = _edge_find_file_input(edge_drv)
        if not file_input:
            time.sleep(0.5)
            file_input = _edge_find_file_input(edge_drv)
        if not file_input:
            return False

        file_input.send_keys(os.path.abspath(image_path))

        deadline = time.time() + timeout
        outcome = 'error'
        while time.time() < deadline:
            outcome = _edge_check_wmr_status(edge_drv)
            if outcome in ('done', 'not_found', 'error'):
                break
            time.sleep(1.0)

        if outcome != 'done':
            return False

        files_before = set(os.listdir(wmr_dl_dir)) if os.path.exists(wmr_dl_dir) else set()
        if not _edge_click_download(edge_drv):
            return False

        fpath = _wait_for_download(wmr_dl_dir, files_before, timeout=20)
        if not fpath:
            return False

        # Replace original with cleaned version
        try:
            Path(fpath).rename(image_path)
        except Exception:
            Path(image_path).write_bytes(Path(fpath).read_bytes())
        return True
    except Exception:
        return False


# --- Edge WMR Background Thread ---
_EDGE_WMR_QUEUE  = None
_EDGE_WMR_THREAD = None
_EDGE_WMR_LOCK   = threading.Lock()


def _edge_wmr_worker_loop(edge_bin, wmr_base_dir, work_queue):
    """Background thread: runs Edge for watermark removal independently."""
    edge_drv = None
    try:
        while True:
            item = work_queue.get()
            try:
                if item is None:   # shutdown sentinel
                    return

                idx, image_path, set_combo = item
                # Per-tab WMR download folder
                wmr_dl_dir = os.path.join(wmr_base_dir, f'edge_wmr_tab_{idx}')
                os.makedirs(wmr_dl_dir, exist_ok=True)

                # Lazy-init Edge driver
                if edge_drv is None:
                    try:
                        edge_drv = make_edge_driver(edge_bin, wmr_dl_dir)
                        print(f'[EDGE_WMR] Edge browser launched for watermark removal', flush=True)
                    except Exception as e:
                        print(f'[EDGE_WMR] Edge launch failed: {e}', flush=True)
                        edge_drv = None

                ok = False
                if edge_drv is not None:
                    for _attempt in range(2):
                        try:
                            set_download_behavior(edge_drv, wmr_dl_dir)
                            if _edge_process_single(edge_drv, image_path, wmr_dl_dir):
                                ok = True
                                break
                        except Exception:
                            pass

                # Convert to WebP regardless of WMR success
                webp_path = convert_to_webp(image_path)
                if ok:
                    set_combo(idx, phase='done',
                        message='STEP_COMPLETE: Generated + watermark removed',
                        output=os.path.basename(image_path),
                        output_webp=os.path.basename(webp_path) if webp_path else None)
                else:
                    set_combo(idx, phase='done',
                        message='STEP_COMPLETE: Generated (WMR skipped)',
                        output=os.path.basename(image_path),
                        output_webp=os.path.basename(webp_path) if webp_path else None)
            finally:
                work_queue.task_done()
    finally:
        try:
            if edge_drv:
                edge_drv.quit()
        except Exception:
            pass


def start_edge_wmr_worker(edge_bin, wmr_base_dir, status):
    """Start the background Edge WMR thread."""
    global _EDGE_WMR_QUEUE, _EDGE_WMR_THREAD
    with _EDGE_WMR_LOCK:
        if _EDGE_WMR_THREAD is not None:
            return
        if not edge_bin:
            status.update(message='STEP_LAUNCH_EDGE_WMR: Edge not found — WMR disabled')
            return
        os.makedirs(wmr_base_dir, exist_ok=True)
        _EDGE_WMR_QUEUE = queue.Queue()
        _EDGE_WMR_THREAD = threading.Thread(
            target=_edge_wmr_worker_loop,
            args=(edge_bin, wmr_base_dir, _EDGE_WMR_QUEUE),
            daemon=True)
        _EDGE_WMR_THREAD.start()
        status.update(message='STEP_LAUNCH_EDGE_WMR: Edge WMR worker started in background')


def enqueue_edge_wmr(idx, image_path, set_combo):
    """Queue an image for Edge watermark removal (non-blocking)."""
    if _EDGE_WMR_QUEUE is not None:
        _EDGE_WMR_QUEUE.put((idx, image_path, set_combo))


def stop_edge_wmr_worker(wait_s=240):
    """Shutdown the Edge WMR background thread."""
    global _EDGE_WMR_QUEUE, _EDGE_WMR_THREAD
    with _EDGE_WMR_LOCK:
        thread, q = _EDGE_WMR_THREAD, _EDGE_WMR_QUEUE
        _EDGE_WMR_THREAD = None
        _EDGE_WMR_QUEUE = None
    if thread is None:
        return
    try:
        q.put(None)   # shutdown sentinel
        thread.join(timeout=wait_s)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
#  TAB SLOT — represents one Chrome tab for Gemini generation
# ═══════════════════════════════════════════════════════════════════════

class TabSlot:
    """One Chrome tab running Gemini image generation."""
    IDLE        = 'idle'
    SETUP       = 'setup'
    UPLOADING   = 'uploading'
    GENERATING  = 'generating'
    DOWNLOADING = 'downloading'
    ERROR       = 'error'

    def __init__(self, index, handle, download_dir):
        self.index = index
        self.handle = handle
        self.download_dir = download_dir   # per-tab: generated/tab_0/
        self.state = self.IDLE
        self.combo = None
        self.urls_before = set()
        self.started = 0.0
        self.model = None
        self.fresh = True
        self.checks = 0

    def __repr__(self):
        return f'<Tab {self.index} state={self.state} combo={self.combo}>'


# ═══════════════════════════════════════════════════════════════════════
#  AGGRESSIVE BATCH GENERATION — round-robin tab management
# ═══════════════════════════════════════════════════════════════════════

def _dispatch_job_to_tab(drv, tab, combo, image_path, model_image_path,
                         args, status, states):
    """Set up a Gemini tab and send a generation job. NON-BLOCKING after send."""
    idx = combo['idx']
    target_model = args.gemini_model

    def set_combo(idx_, **kw):
        for s in states:
            if s['idx'] == idx_:
                s.update(kw)
        # Don't call sync() here — caller will sync after dispatch

    try:
        drv.switch_to.window(tab.handle)
        click_menu_item(drv, ['dismiss'])

        set_combo(idx, phase='setup',
            message=f'STEP_TAB{tab.index}_SETUP: Preparing new chat...')

        if not tab.fresh:
            start_new_chat(drv)
            time.sleep(1.0)
        tab.fresh = False

        if target_model:
            select_gemini_model(drv, target_model, status)
            tab.model = target_model
        combo['_model'] = tab.model

        # Switch to Create Image mode
        set_combo(idx, phase='setup',
            message=f'STEP_TAB{tab.index}_ACTIVATE_IMAGE_MODE')
        if not activate_create_image_mode(drv, status, tag=f'(tab{tab.index} look{idx})'):
            raise RuntimeError("could not switch to 'Create image' mode")

        # Upload reference images
        upload_paths = [image_path]
        if combo.get('hologram_path'):
            upload_paths.append(combo['hologram_path'])
        if model_image_path:
            upload_paths.append(model_image_path)

        set_combo(idx, phase='uploading',
            message=f'STEP_TAB{tab.index}_UPLOAD_REFS: Uploading {len(upload_paths)} ref(s)...')
        upload_images(drv, upload_paths, status)

        # Type prompt
        set_combo(idx, phase='prompting',
            message=f'STEP_TAB{tab.index}_TYPE_PROMPT')
        type_prompt(drv, combo['prompt'])

        # Snapshot URLs before sending
        tab.urls_before = snapshot_urls(drv)

        # Send!
        set_combo(idx, phase='sending',
            message=f'STEP_TAB{tab.index}_SEND_PROMPT')
        if not click_send(drv):
            raise RuntimeError('could not click send')

        # Tab is now GENERATING — don't wait, return immediately
        tab.combo = combo
        tab.started = time.time()
        tab.state = TabSlot.GENERATING
        tab.checks = 0
        set_combo(idx, phase='generating',
            message=f'STEP_TAB{tab.index}_WAIT_GENERATION: Gemini is generating...')
        return True

    except Exception as e:
        set_combo(idx, phase='error',
            message=f'STEP_TAB{tab.index}_ERROR: {str(e)[:200]}')
        tab.state = TabSlot.IDLE
        tab.combo = None
        return False


def run_batch_generation(drv, status, args, combos, image_path,
                         model_image_path, chrome_bin=None):
    """
    AGGRESSIVE ROUND-ROBIN TAB MANAGEMENT

    Flow:
      1. DISPATCH: Fill all idle tabs with pending jobs (don't wait)
      2. GROW: Open more tabs if queue has more jobs
      3. POLL: Check each generating tab — download if ready
      4. When downloaded → tab goes IDLE → immediately dispatch next
      5. Downloaded images go to Edge WMR in background thread
    """
    tab_cap = max(1, int(getattr(args, 'max_tabs', 6) or 6))

    # Find Edge for WMR
    edge_bin = find_edge()

    # Per-tab download directories for Chrome (Gemini generation)
    gen_base = os.path.join(args.output_dir, 'generated')
    for i in range(tab_cap):
        os.makedirs(os.path.join(gen_base, f'tab_{i}'), exist_ok=True)

    # Edge WMR output directory
    wmr_base = os.path.join(args.output_dir, 'wmr_clean')
    os.makedirs(wmr_base, exist_ok=True)

    # Start Edge WMR background worker
    start_edge_wmr_worker(edge_bin, wmr_base, status)

    # Initialize states for tracking
    states = [{
        'idx': c['idx'],
        'label': c.get('label') or f"look {c['idx'] + 1}",
        'phase': 'queued',
        'message': '',
        'output': None,
    } for c in combos]
    accepting = {'open': True}

    def sync(msg=None):
        done = sum(1 for s in states if s['phase'] == 'done')
        errs = sum(1 for s in states if s['phase'] == 'error')
        active_n = sum(1 for t in tabs if t.state == TabSlot.GENERATING)
        status.update(
            phase='generating', accepting=accepting['open'],
            message=msg or (
                f'STEP_ROUNDROBIN_POLL: {len(tabs)} tabs active, '
                f'{active_n} generating, {done} done, {errs} failed, '
                f'{len(job_queue)} queued'),
            combos=[dict(s) for s in states])

    def set_combo(idx, **kw):
        for s in states:
            if s['idx'] == idx:
                s.update(kw)
        sync()

    job_queue = list(combos)
    outputs = []
    parked = []
    limited_models = set()
    limit_cycles = 0

    # --- Create initial tab (current window) ---
    tab0_dl = os.path.join(gen_base, 'tab_0')
    set_download_behavior(drv, tab0_dl)
    tabs = [TabSlot(
        index=0,
        handle=drv.current_window_handle,
        download_dir=tab0_dl)]

    def grow_tabs():
        """Open more Chrome tabs if jobs are waiting."""
        while (len(job_queue) + sum(1 for t in tabs if t.combo)) > len(tabs) \
                and len(tabs) < tab_cap:
            drv.switch_to.window(tabs[0].handle)
            if not open_gemini_tab(drv, GEMINI_URL):
                break
            new_idx = len(tabs)
            new_dl = os.path.join(gen_base, f'tab_{new_idx}')
            os.makedirs(new_dl, exist_ok=True)
            set_download_behavior(drv, new_dl)
            tabs.append(TabSlot(
                index=new_idx,
                handle=drv.current_window_handle,
                download_dir=new_dl))
            time.sleep(0.8)

    def ingest_inbox():
        """Check for dynamically-added jobs from the inbox directory."""
        inbox_dir = os.path.join(args.output_dir, 'inbox')
        added = 0
        try:
            names = sorted(os.listdir(inbox_dir))
        except OSError:
            return 0
        for name in names:
            if not (name.startswith('combo-') and name.endswith('.json')):
                continue
            jpath = os.path.join(inbox_dir, name)
            try:
                with open(jpath) as f:
                    spec = json.load(f)
            except Exception:
                continue
            holo = spec.get('hologram')
            hpath = os.path.join(inbox_dir, holo) if holo else None
            if holo and not os.path.isfile(hpath):
                continue
            try:
                os.remove(jpath)
            except OSError:
                pass
            idx = int(spec.get('idx', -1))
            if idx < 0 or any(c['idx'] == idx for c in combos):
                continue
            combo = {
                'idx': idx,
                'label': spec.get('label') or f'look {idx + 1}',
                'prompt': spec.get('prompt') or (combos[0]['prompt'] if combos else ''),
                'hologram_path': hpath,
            }
            combos.append(combo)
            states.append({
                'idx': idx, 'label': combo['label'],
                'phase': 'queued', 'message': '', 'output': None})
            job_queue.append(combo)
            added += 1
        if added:
            sync(f'{added} new look(s) joined the live batch.')
        return added

    # --- MAIN AGGRESSIVE LOOP ---
    sync(f'STEP_DISPATCH_NEXT_JOB: Opening {min(len(combos), tab_cap)} tabs...')
    grow_tabs()

    while True:
        ingest_inbox()
        grow_tabs()

        # ═════════════════════════════════════════════════════════════
        # PHASE 1: DISPATCH — fill every idle tab with a pending job
        # ═════════════════════════════════════════════════════════════
        for tab in tabs:
            if tab.state == TabSlot.IDLE and job_queue:
                combo = job_queue.pop(0)
                sync(f'STEP_DISPATCH_NEXT_JOB: Dispatching look {combo["idx"]} '
                     f'to Tab {tab.index}')
                _dispatch_job_to_tab(drv, tab, combo, image_path,
                    model_image_path, args, status, states)
                # DON'T BREAK — dispatch to ALL idle tabs immediately!

        # ═════════════════════════════════════════════════════════════
        # PHASE 2: POLL — check each generating tab (round-robin)
        # ═════════════════════════════════════════════════════════════
        active_tabs = [t for t in tabs if t.state == TabSlot.GENERATING]
        for tab in active_tabs:
            combo = tab.combo
            if combo is None:
                continue
            idx = combo['idx']
            try:
                drv.switch_to.window(tab.handle)
                timed_out = time.time() - tab.started > args.generation_timeout

                # Check for generated image
                if timed_out:
                    src = check_new_image_lenient(drv, tab.urls_before)
                else:
                    src = check_new_image(drv, tab.urls_before)

                if src:
                    # ══════ IMAGE READY — DOWNLOAD IMMEDIATELY ══════
                    set_combo(idx, phase='downloading',
                        message=f'STEP_TAB{tab.index}_DOWNLOAD_IMAGE: '
                                f'Image ready! Downloading...')

                    save_path = os.path.join(tab.download_dir,
                        f'combo-{idx:02d}.png')
                    set_download_behavior(drv, tab.download_dir)

                    if download_image(drv, save_path, tab.urls_before,
                                      tab.download_dir):
                        outputs.append(save_path)
                        set_combo(idx, phase='edge_wmr_queued',
                            message=f'STEP_TAB{tab.index}_QUEUE_EDGE_WMR: '
                                    f'Downloaded → queued for Edge WMR')
                        # Queue for Edge watermark removal (background)
                        enqueue_edge_wmr(idx, save_path, set_combo)
                    else:
                        set_combo(idx, phase='error',
                            message=f'STEP_TAB{tab.index}_ERROR: '
                                    f'Generated but download failed')

                    # Tab is FREE — ready for next job
                    tab.state = TabSlot.IDLE
                    tab.combo = None
                    tab.checks = 0

                    # IMMEDIATELY dispatch next job to this tab
                    if job_queue:
                        next_combo = job_queue.pop(0)
                        sync(f'STEP_DISPATCH_NEXT_JOB: Tab {tab.index} free → '
                             f'dispatching look {next_combo["idx"]}')
                        _dispatch_job_to_tab(drv, tab, next_combo, image_path,
                            model_image_path, args, status, states)
                    continue

                if timed_out and not src:
                    # Timeout with no image
                    shot = save_debug_screenshot(drv, args.output_dir,
                        f'look-{idx:02d}-timeout')
                    set_combo(idx, phase='error',
                        message=f'STEP_TAB{tab.index}_TIMEOUT: '
                                f'No image within {args.generation_timeout}s',
                        debug_screenshot=os.path.basename(shot) if shot else None)
                    tab.state = TabSlot.IDLE
                    tab.combo = None
                    continue

                # Not ready yet — check for limit/refusal every 3 polls
                tab.checks += 1
                if tab.checks % 3 == 0:
                    verdict = check_limit_or_refusal(drv)
                    if verdict == 'refusal':
                        set_combo(idx, phase='error',
                            message=f'STEP_TAB{tab.index}_REFUSED: '
                                    f'Gemini declined this prompt')
                        tab.state = TabSlot.IDLE
                        tab.combo = None
                    elif verdict == 'limit':
                        limited_models.add(combo.get('_model') or '__default__')
                        nxt = next(
                            (m for m in FALLBACK_MODELS if m not in limited_models),
                            None)
                        combo['_attempts'] = combo.get('_attempts', 0) + 1
                        tab.state = TabSlot.IDLE
                        tab.combo = None
                        if nxt and combo['_attempts'] < 4:
                            set_combo(idx, phase='setup',
                                message=f'STEP_TAB{tab.index}_FALLBACK: '
                                        f'Limit hit → retrying on {nxt}...')
                            _dispatch_job_to_tab(drv, tab, combo, image_path,
                                model_image_path, args, status, states)
                        else:
                            set_combo(idx, phase='limit_parked',
                                message=f'STEP_TAB{tab.index}_LIMIT_PARKED: '
                                        f'All models limited — parked for auto-resume')
                            parked.append(combo)

            except Exception as e:
                set_combo(idx, phase='error',
                    message=f'STEP_TAB{tab.index}_ERROR: Lost control: '
                            f'{str(e)[:200]}')
                tab.state = TabSlot.IDLE
                tab.combo = None

        # ═════════════════════════════════════════════════════════════
        # PHASE 3: EXIT CHECK
        # ═════════════════════════════════════════════════════════════
        active = [t for t in tabs if t.state != TabSlot.IDLE]
        if not active and not job_queue:
            if ingest_inbox():
                continue
            # Handle parked jobs (limit waits)
            if parked and limit_cycles < int(
                    getattr(args, 'max_limit_cycles', 3) or 3):
                limit_cycles += 1
                resume_at = time.time() + int(
                    getattr(args, 'limit_wait', 3600) or 3600)
                while time.time() < resume_at:
                    mins = int((resume_at - time.time()) / 60) + 1
                    status.update(
                        phase='limit_wait', accepting=True,
                        resume_at=resume_at,
                        message=f"STEP_LIMIT_WAIT: Gemini limit reached — "
                                f"resuming in ~{mins} min",
                        combos=[dict(s) for s in states])
                    time.sleep(15)
                    ingest_inbox()
                limited_models.clear()
                status.update(resume_at=None)
                for c in parked:
                    c['_attempts'] = 0
                    job_queue.append(c)
                    set_combo(c['idx'], phase='queued',
                        message='Resuming after limit reset...')
                parked.clear()
                continue
            if parked:
                for c in parked:
                    set_combo(c['idx'], phase='error',
                        message="STEP_LIMIT_EXHAUSTED: Limit didn't lift")
                parked.clear()
            accepting['open'] = False
            status.update(accepting=False)
            break

        time.sleep(1.0)

    # Wait for Edge WMR to finish all queued items
    status.update(message='STEP_WAIT_EDGE_WMR: Waiting for Edge watermark removal...')
    stop_edge_wmr_worker()

    done_states = [s for s in states if s['phase'] == 'done']
    ok = len(done_states)
    if ok == 0:
        status.update(
            phase='error', finished=True, accepting=False,
            error=f'All {len(states)} shots failed',
            combos=[dict(s) for s in states])
        return None

    status.update(
        phase='done', finished=True, accepting=False,
        message=f'STEP_COMPLETE: {ok}/{len(states)} shots generated.',
        output_image=os.path.join(
            gen_base, f"tab_0/{done_states[0]['output']}"
            if done_states[0].get('output') else ''),
        combos=[dict(s) for s in states])
    return outputs


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    global By, Keys, ActionChains

    parser = argparse.ArgumentParser(
        description='Gemini Generate v3 — Aggressive Tab Mgmt + Edge WMR')
    parser.add_argument('--status-file', required=True)
    parser.add_argument('--output-dir', default='./gemini_generate_session')
    parser.add_argument('--cookies-file', default=None)
    parser.add_argument('--profile-dir', default=None,
        help='Persistent Chrome user-data-dir (logged-in profile)')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--login-timeout', type=int, default=900)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--image-path', default=None)
    parser.add_argument('--model-image-path', default=None)
    parser.add_argument('--hologram-image-path', default=None)
    parser.add_argument('--gemini-model', default='Flash')
    parser.add_argument('--generation-timeout', type=int, default=180)
    parser.add_argument('--max-tabs', type=int, default=6,
        help='Max parallel Chrome tabs for Gemini generation')
    parser.add_argument('--limit-wait', type=int, default=3600)
    parser.add_argument('--max-limit-cycles', type=int, default=3)
    parser.add_argument('--screen-width', type=int, default=1920)
    parser.add_argument('--screen-height', type=int, default=1080)
    parser.add_argument('--keep-alive', action='store_true')
    parser.add_argument('--watch-live', action='store_true')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    cookies_file = args.cookies_file or os.path.join(
        args.output_dir, 'google_cookies.pkl')

    if EMBEDDED_COOKIES_B64:
        Path(cookies_file).parent.mkdir(parents=True, exist_ok=True)
        Path(cookies_file).write_bytes(base64.b64decode(EMBEDDED_COOKIES_B64))

    profile_dir = args.profile_dir or os.path.join(
        args.output_dir, 'chrome_profile')
    profile_archive_out = os.path.join(args.output_dir, 'chrome_profile.zip')

    if EMBEDDED_CHROME_PROFILE_REMOTE:
        gl.restore_chrome_profile(profile_dir, EMBEDDED_CHROME_PROFILE_REMOTE)

    # Resolve image paths
    image_path = args.image_path
    if EMBEDDED_IMAGE_REMOTE and os.path.exists(EMBEDDED_IMAGE_REMOTE):
        image_path = EMBEDDED_IMAGE_REMOTE
    elif EMBEDDED_IMAGE_B64:
        image_path = os.path.join(
            args.output_dir, f"reference_image{EMBEDDED_IMAGE_EXT or '.png'}")
        Path(image_path).parent.mkdir(parents=True, exist_ok=True)
        Path(image_path).write_bytes(base64.b64decode(EMBEDDED_IMAGE_B64))

    model_image_path = args.model_image_path
    if EMBEDDED_MODEL_IMAGE_REMOTE and os.path.exists(EMBEDDED_MODEL_IMAGE_REMOTE):
        model_image_path = EMBEDDED_MODEL_IMAGE_REMOTE
    elif EMBEDDED_MODEL_IMAGE_B64:
        model_image_path = os.path.join(
            args.output_dir,
            f"model_image{EMBEDDED_MODEL_IMAGE_EXT or '.webp'}")
        Path(model_image_path).parent.mkdir(parents=True, exist_ok=True)
        Path(model_image_path).write_bytes(
            base64.b64decode(EMBEDDED_MODEL_IMAGE_B64))

    hologram_image_path = args.hologram_image_path
    if EMBEDDED_HOLOGRAM_IMAGE_B64:
        hologram_image_path = os.path.join(
            args.output_dir,
            f"hologram_image{EMBEDDED_HOLOGRAM_IMAGE_EXT or '.webp'}")
        Path(hologram_image_path).parent.mkdir(parents=True, exist_ok=True)
        Path(hologram_image_path).write_bytes(
            base64.b64decode(EMBEDDED_HOLOGRAM_IMAGE_B64))

    # Decode batch combos
    batch_combos = None
    if EMBEDDED_BATCH_B64:
        payload = json.loads(base64.b64decode(EMBEDDED_BATCH_B64))
        batch_combos = payload.get('combos') or None
        for c in batch_combos or []:
            if c.get('hologram_remote') and os.path.exists(c['hologram_remote']):
                c['hologram_path'] = c['hologram_remote']
            elif c.get('hologram_b64'):
                hp = os.path.join(
                    args.output_dir,
                    f"hologram_{int(c['idx']):02d}"
                    f"{c.get('hologram_ext') or '.webp'}")
                Path(hp).parent.mkdir(parents=True, exist_ok=True)
                Path(hp).write_bytes(base64.b64decode(c['hologram_b64']))
                c['hologram_path'] = hp

    status = gl.Status(args.status_file)
    headless = args.headless or gl.is_colab()
    mode = 'colab' if gl.is_colab() else (
        'local-headless' if args.headless else 'local')
    status.update(mode=mode,
        message=f"STEP_INIT: Starting in '{mode}' mode.")

    debug_screenshot_path = None
    global _PERSISTENT_DRIVER, _PERSISTENT_VNC_URL

    try:
        chrome_bin = gl.ensure_deps(status, headless)

        from selenium.webdriver.common.by import By as _By
        from selenium.webdriver.common.keys import Keys as _Keys
        from selenium.webdriver.common.action_chains import (
            ActionChains as _ActionChains)
        By = _By
        Keys = _Keys
        ActionChains = _ActionChains

        drv = _PERSISTENT_DRIVER
        reused_driver = False

        if drv is not None:
            status.update(phase='checking_session',
                message='STEP_VERIFY_CHROME_SESSION: Checking existing browser...')
            if gl.is_logged_in(drv):
                reused_driver = True
                if args.watch_live and headless and _PERSISTENT_VNC_URL:
                    status.update(vnc_url=_PERSISTENT_VNC_URL)
                status.update(phase='reusing_session',
                    message='STEP_VERIFY_CHROME_SESSION: '
                            'Already logged in — reusing Chrome profile')
            else:
                try:
                    drv.quit()
                except Exception:
                    pass
                drv = None
                _PERSISTENT_DRIVER = None

        if not reused_driver:
            if headless:
                vnc_url = gl.start_display_and_vnc(
                    status, args.screen_width, args.screen_height)
                _PERSISTENT_VNC_URL = vnc_url
                status.update(vnc_url=vnc_url,
                    message='STEP_LAUNCH_DISPLAY: Virtual display ready')
            status.update(phase='launching_browser',
                message=f'STEP_LAUNCH_CHROME: Starting Chrome ({chrome_bin})...')
            drv = gl.make_driver(chrome_bin, args.screen_width,
                args.screen_height, args.output_dir, profile_dir)

        have_logged_in_driver = reused_driver
        keep_driver_alive = False

        try:
            if not reused_driver:
                if not gl.handle_login(drv, status, cookies_file,
                        args.login_timeout, mark_finished=False,
                        profile_dir=profile_dir,
                        profile_archive_out=profile_archive_out):
                    return
                have_logged_in_driver = True

            status.update(phase='opening_gemini',
                message='STEP_OPEN_GEMINI: Opening Gemini...')
            if reused_driver:
                if open_gemini_tab(drv, GEMINI_URL):
                    close_other_tabs(drv, drv.current_window_handle)
                else:
                    drv.get(GEMINI_URL)
            else:
                drv.get(GEMINI_URL)
            time.sleep(2.5)
            click_menu_item(drv, ['dismiss'])
            set_download_behavior(drv, args.output_dir)

            if reused_driver:
                start_new_chat(drv)
                time.sleep(1.0)

            # ═══ BATCH MODE (aggressive tab management) ═══
            if batch_combos and image_path:
                run_batch_generation(drv, status, args, batch_combos,
                    image_path, model_image_path, chrome_bin)
                if bool(args.keep_alive):
                    status.update(message=status.data.get('message', '') +
                        ' (browser kept open for reuse)')
                return

            # ═══ SINGLE IMAGE MODE ═══
            if args.gemini_model:
                status.update(phase='selecting_model',
                    message=f"STEP_SELECT_MODEL: Trying '{args.gemini_model}'...")
                select_gemini_model(drv, args.gemini_model, status)

            prompt = args.prompt
            if image_path:
                status.update(phase='switching_mode',
                    message='STEP_ACTIVATE_IMAGE_MODE')
                if not activate_create_image_mode(drv, status):
                    raise RuntimeError(
                        "could not switch to 'Create image' mode")
                upload_paths = [image_path]
                if hologram_image_path:
                    upload_paths.append(hologram_image_path)
                if model_image_path:
                    upload_paths.append(model_image_path)
                status.update(phase='uploading_image',
                    message=f'STEP_UPLOAD_REFS: Uploading '
                            f'{os.path.basename(image_path)}...')
                upload_images(drv, upload_paths, status)
            else:
                status.update(phase='switching_mode',
                    message='STEP_ACTIVATE_IMAGE_MODE')
                if not activate_create_image_mode(drv, status):
                    raise RuntimeError(
                        "could not switch to 'Create image' mode")

            status.update(phase='typing_prompt',
                message='STEP_TYPE_PROMPT')
            type_prompt(drv, prompt)

            urls_before = snapshot_urls(drv)
            status.update(phase='sending',
                message='STEP_SEND_PROMPT')
            if not click_send(drv):
                raise RuntimeError('could not click send')

            status.update(phase='generating',
                message=f'STEP_WAIT_GENERATION: Waiting up to '
                        f'{args.generation_timeout}s...')

            # Wait for image
            t0 = time.time()
            img_url = None
            while time.time() - t0 < args.generation_timeout:
                img_url = check_new_image(drv, urls_before)
                if img_url:
                    break
                time.sleep(1.0)
            if not img_url:
                raise RuntimeError('no image within generation timeout')

            status.update(phase='downloading_result',
                message='STEP_DOWNLOAD_IMAGE')
            safe_name = re.sub(
                r'[^\w\-]+', '_', args.prompt[:40]).strip('_') or 'gemini_output'
            save_path = os.path.join(
                args.output_dir, 'generated', f'{safe_name}.png')
            if not download_image(drv, save_path, urls_before, args.output_dir):
                raise RuntimeError('download failed')

            # Edge WMR for single image
            status.update(phase='removing_watermark',
                message='STEP_EDGE_WMR_PROCESS')
            edge_bin = find_edge()
            if edge_bin:
                wmr_dl = os.path.join(args.output_dir, 'wmr_single')
                os.makedirs(wmr_dl, exist_ok=True)
                try:
                    edge_drv = make_edge_driver(edge_bin, wmr_dl)
                    _edge_process_single(edge_drv, save_path, wmr_dl)
                    edge_drv.quit()
                except Exception:
                    pass

            webp_path = convert_to_webp(save_path)
            status.update(
                phase='done',
                message=f'STEP_COMPLETE: Saved to {save_path}',
                output_image=save_path,
                output_image_webp=webp_path,
                finished=True)
            if bool(args.keep_alive):
                status.update(message=status.data.get('message', '') +
                    ' (browser kept open)')

        except Exception:
            debug_screenshot_path = save_debug_screenshot(
                drv, args.output_dir, 'failure')
            raise
        finally:
            keep_driver_alive = have_logged_in_driver and bool(args.keep_alive)
            if keep_driver_alive:
                _PERSISTENT_DRIVER = drv
            else:
                _PERSISTENT_DRIVER = None
                try:
                    drv.quit()
                except Exception:
                    pass

    except Exception as e:
        status.update(
            phase='error', message=str(e), error=str(e),
            debug_screenshot=debug_screenshot_path, finished=True)
        raise


if __name__ == '__main__':
    main()
