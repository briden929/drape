import argparse
import base64
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
import gemini_login as gl
EMBEDDED_COOKIES_B64 = globals().get('EMBEDDED_COOKIES_B64')
EMBEDDED_IMAGE_B64 = globals().get('EMBEDDED_IMAGE_B64')
EMBEDDED_IMAGE_EXT = globals().get('EMBEDDED_IMAGE_EXT')
EMBEDDED_MODEL_IMAGE_B64 = globals().get('EMBEDDED_MODEL_IMAGE_B64')
EMBEDDED_MODEL_IMAGE_EXT = globals().get('EMBEDDED_MODEL_IMAGE_EXT')
EMBEDDED_HOLOGRAM_IMAGE_B64 = globals().get('EMBEDDED_HOLOGRAM_IMAGE_B64')
EMBEDDED_HOLOGRAM_IMAGE_EXT = globals().get('EMBEDDED_HOLOGRAM_IMAGE_EXT')
EMBEDDED_BATCH_B64 = globals().get('EMBEDDED_BATCH_B64')
EMBEDDED_IMAGE_REMOTE = globals().get('EMBEDDED_IMAGE_REMOTE')
EMBEDDED_MODEL_IMAGE_REMOTE = globals().get('EMBEDDED_MODEL_IMAGE_REMOTE')
EMBEDDED_CHROME_PROFILE_REMOTE = globals().get('EMBEDDED_CHROME_PROFILE_REMOTE')
LIMIT_PHRASES = ["you've reached your image-generation limit", 'reached your image-generation limit', 'image-generation limit', "can't generate more images for you today", 'come back tomorrow', "you've reached your limit", 'reached your daily limit', 'rate limit', 'too many requests']
REFUSAL_PHRASES = ["can't create images of", 'cannot create images of', "i'm not able to create that image", "i'm unable to create that image", "i can't create this image"]
FALLBACK_MODELS = ['3.7 Flash', '3.5 Flash-Lite']

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
By = None
Keys = None
ActionChains = None
GEMINI_URL = 'https://gemini.google.com/app'
WMR_URL = 'https://app.gemini-logo-remover.workers.dev/gemini'

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
    for sel in ['a[aria-label="New chat"]', 'button[aria-label="New chat"]', 'div[aria-label="New chat"]', '[data-test-id="new-chat-button"]']:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    drv.execute_script('arguments[0].click();', el)
                    time.sleep(1.0)
                    return True
        except Exception:
            continue
    return False
_PERSISTENT_DRIVER = globals().get('_PERSISTENT_DRIVER')
_PERSISTENT_VNC_URL = globals().get('_PERSISTENT_VNC_URL')

def click_plus_button(drv):
    for sel in ['button[aria-label="Upload and tools"]', 'button[aria-haspopup="menu"][aria-label*="Upload"]', 'button[jslog*="300142"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script('arguments[0].click();', btn)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue
    try:
        result = drv.execute_script('\n            var btns=document.querySelectorAll(\'button\');\n            for(var i=0;i<btns.length;i++){\n                var b=btns[i];\n                if(b.offsetParent!==null){\n                    var lbl=(b.getAttribute(\'aria-label\')||\'\').toLowerCase();\n                    if(lbl.indexOf(\'upload\')!==-1||lbl.indexOf(\'tools\')!==-1){\n                        b.click();return \'OK\';\n                    }\n                    var icon=b.querySelector(\'mat-icon[fonticon="plus"],mat-icon[data-mat-icon-name="plus"]\');\n                    if(icon){b.click();return \'OK\';}\n                }\n            } return \'NO\';\n        ')
        if result == 'OK':
            time.sleep(0.4)
            return True
    except Exception:
        pass
    return False

def click_menu_item(drv, texts):
    texts_l = [t.lower() for t in texts]
    try:
        candidates = drv.find_elements(By.CSS_SELECTOR, "button, [role='menuitem'], [role='menuitemcheckbox']")
        for el in candidates:
            try:
                if not el.is_displayed():
                    continue
                label = (el.text or el.get_attribute('aria-label') or '').strip().lower()
                if label and any((t in label for t in texts_l)):
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
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button"):
            if btn.is_displayed() and 'Create image' in btn.text:
                drv.execute_script('arguments[0].click();', btn)
                time.sleep(0.35)
                return True
    except Exception:
        pass
    try:
        for icon in drv.find_elements(By.CSS_SELECTOR, "mat-icon[data-mat-icon-name='image_create'],mat-icon[fonticon='image_create']"):
            if not icon.is_displayed():
                continue
            btn = drv.execute_script("var e=arguments[0]; while(e&&e.tagName!=='BUTTON') e=e.parentElement; return e;", icon)
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
        if drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder='Describe your image']"):
            return True
        for c in drv.find_elements(By.CSS_SELECTOR, "button[aria-label='Deselect Images'],span.gds-body-s"):
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
            status.update(message=f"Already in 'Create image' mode. {tag}".strip())
        return True
    for attempt in range(attempts):
        if status:
            status.update(message=f"Opening the '+' tools menu for 'Create image'... {tag}".strip())
        if not click_plus_button(drv):
            time.sleep(0.5)
            continue
        if status:
            status.update(message=f"Clicking 'Create image'... {tag}".strip())
        if not click_create_image(drv):
            try:
                drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            except Exception:
                pass
            time.sleep(0.5)
            continue
        if wait_for_image_mode(drv, timeout=4.0):
            if status:
                status.update(message=f"Switched to 'Create image' mode. {tag}".strip())
            return True
        if status:
            status.update(message=f"'Create image' didn't confirm — retrying... {tag}".strip())
        try:
            drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except Exception:
            pass
        time.sleep(0.5)
    if status:
        status.update(message=f"Could not switch to 'Create image' mode after {attempts} attempts. {tag}".strip())
    return False
_MODEL_TRIGGER_SELECTOR = "button[aria-label*='model' i], button[class*='model-switcher' i], button[data-test-id*='model' i], bard-mode-switcher button, button[class*='mode-switcher' i]"

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
                status.update(message="Could not find Gemini's model switcher — continuing with the default model.")
                return False
            clicked = False
            for cand in drv.find_elements(By.CSS_SELECTOR, "[role='menuitem'], [role='menuitemradio'], button"):
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
                status.update(message=f"Selected the Gemini model matching '{model_query}'.")
                return True
        except Exception as e:
            status.update(message=f'Gemini model selection attempt failed ({e}), retrying...')
        try:
            drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except Exception:
            pass
        time.sleep(0.4)
    status.update(message=f"No Gemini model matched '{model_query}' after {attempts} attempts — continuing with the default model.")
    return False

def handle_consent(drv):
    try:
        for bsel in ["button[data-test-id='upload-image-agree-button']", "//button[.//span[contains(text(),'Agree')]]", "//span[text()='Agree']/ancestor::button"]:
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
    for xp in ["//span[contains(text(),'Upload files')]/ancestor::button", "//div[contains(text(),'Upload files')]/ancestor::button"]:
        try:
            for btn in drv.find_elements(By.XPATH, xp):
                if btn.is_displayed():
                    drv.execute_script('arguments[0].click();', btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    try:
        result = drv.execute_script("\n            var btns=document.querySelectorAll('button');\n            for(var i=0;i<btns.length;i++){\n                if(btns[i].offsetParent!==null &&\n                   btns[i].textContent.toLowerCase().indexOf('upload files')!==-1){\n                    btns[i].click();return 'OK';\n                }\n            } return 'NO';\n        ")
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
        drv.execute_script('\n            document.querySelectorAll(\'input[type="file"]\').forEach(function(el){\n                el.style.cssText=\'display:block!important;opacity:1!important;\'\n                    +\'position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;\';\n            });\n        ')
    except Exception:
        pass
    time.sleep(0.1)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def wait_for_attachment_chip(drv, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, 'button[aria-label="close attachment"]'):
                if el.is_displayed():
                    return True
            for chip in drv.find_elements(By.CSS_SELECTOR, 'gem-media-attachment,uploader-file-preview'):
                if chip.is_displayed():
                    return True
            for w in drv.find_elements(By.CSS_SELECTOR, '.attachment-preview-wrapper,uploader-file-preview-container'):
                if w.is_displayed():
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

def jsdrop_single(drv, image_path):
    try:
        abs_path = os.path.abspath(image_path)
        if os.path.getsize(abs_path) > 10000000:
            return False
        with open(abs_path, 'rb') as f:
            b64_data = base64.b64encode(f.read()).decode('ascii')
        ext = os.path.splitext(abs_path)[1].lower()
        mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}.get(ext, 'image/jpeg')
        fname = os.path.basename(abs_path)
        result = drv.execute_script('\n            var b64=arguments[0],mime=arguments[1],fname=arguments[2];\n            var binary=atob(b64);var arr=new Uint8Array(binary.length);\n            for(var i=0;i<binary.length;i++) arr[i]=binary.charCodeAt(i);\n            var blob=new Blob([arr],{type:mime});\n            var file=new File([blob],fname,{type:mime,lastModified:Date.now()});\n            var dt=new DataTransfer();dt.items.add(file);\n            var sels=[\'rich-textarea\',\'.ql-editor\',\'div[contenteditable="true"]\',\'.input-area-container\'];\n            for(var s=0;s<sels.length;s++){\n                var targets=document.querySelectorAll(sels[s]);\n                for(var t=0;t<targets.length;t++){\n                    var el=targets[t];if(el.offsetParent===null) continue;\n                    el.dispatchEvent(new DragEvent(\'dragenter\',{dataTransfer:dt,bubbles:true}));\n                    el.dispatchEvent(new DragEvent(\'dragover\',{dataTransfer:dt,bubbles:true}));\n                    el.dispatchEvent(new DragEvent(\'drop\',{dataTransfer:dt,bubbles:true,cancelable:true}));\n                    return \'OK\';\n                }\n            } return \'NO\';\n        ', b64_data, mime, fname)
        time.sleep(0.3)
        handle_consent(drv)
        return result == 'OK'
    except Exception:
        return False

def save_debug_screenshot(drv, output_dir, tag):
    try:
        debug_dir = Path(output_dir) / 'debug'
        debug_dir.mkdir(parents=True, exist_ok=True)
        path = debug_dir / f'{tag}.png'
        drv.save_screenshot(str(path))
        return str(path)
    except Exception:
        return None

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
        status.update(message=f"Opening the '+' tools menu... (all {len(paths)} at once)")
        if not click_plus_button(drv):
            return False
        status.update(message="Clicking 'Upload files'...")
        if not click_upload_files_in_drawer(drv):
            try:
                drv.execute_script('\n                    var b=document.querySelector(\n                        \'button.hidden-local-file-image-selector-button,\'\n                        +\'button[data-test-id="hidden-local-image-upload-button"],\'\n                        +\'button[xapfileselectortrigger]\');\n                    if(b) b.click();\n                ')
                time.sleep(0.15)
            except Exception:
                pass
        handle_consent(drv)
        file_input = find_file_input(drv)
        if file_input is None:
            return False
        names = ', '.join((os.path.basename(p) for p in paths))
        status.update(message=f'Sending {len(paths)} files to the input: {names}')
        try:
            file_input.send_keys('\n'.join(paths))
        except Exception:
            return False
        handle_consent(drv)
        status.update(message='Waiting for Gemini to render the attached images...')
        if not wait_for_attachment_chip(drv, timeout=timeout):
            return False
        time.sleep(1.2 * len(paths))
        status.update(message=f'Uploaded {len(paths)} files together: {names}')
        return True
    except Exception:
        return False

def _attach_one_image(drv, image_path, status, index, total, timeout=30):
    image_path = str(Path(image_path).resolve())
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'image not found: {image_path}')
    tag = f'({index}/{total})' if total > 1 else ''
    status.update(message=f"Opening the '+' tools menu... {tag}".strip())
    if not click_plus_button(drv):
        raise RuntimeError(f"could not open the '+' tools menu {tag}".strip())
    status.update(message=f"Clicking 'Upload files'... {tag}".strip())
    if not click_upload_files_in_drawer(drv):
        try:
            drv.execute_script('\n                var b=document.querySelector(\n                    \'button.hidden-local-file-image-selector-button,\'\n                    +\'button[data-test-id="hidden-local-image-upload-button"],\'\n                    +\'button[xapfileselectortrigger]\');\n                if(b) b.click();\n            ')
            time.sleep(0.15)
        except Exception:
            pass
    handle_consent(drv)
    status.update(message=f'Sending the file to the input: {os.path.basename(image_path)} {tag}'.strip())
    sent_via = None
    file_input = find_file_input(drv)
    if file_input is not None:
        try:
            file_input.send_keys(image_path)
            sent_via = 'input'
        except Exception:
            pass
    if sent_via is None:
        status.update(message="send_keys didn't take — trying drag-drop simulation...")
        if jsdrop_single(drv, image_path):
            sent_via = 'jsdrop'
    if sent_via is None:
        raise RuntimeError("could not attach the file via the file input or drag-drop — Gemini's upload UI may have changed; check the debug screenshot.")
    handle_consent(drv)
    input_confirmed = False
    if sent_via == 'input':
        status.update(message='Confirming the file attached to the input...')
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                count = drv.execute_script('return arguments[0].files ? arguments[0].files.length : 0;', file_input)
                if count and count > 0:
                    input_confirmed = True
                    break
            except Exception:
                pass
            time.sleep(0.3)
    status.update(message='Waiting for Gemini to render the attached image...')
    if not wait_for_attachment_chip(drv, timeout=timeout):
        if not input_confirmed:
            raise RuntimeError("could not confirm the image attached — neither the file input nor Gemini's own attachment chip ever showed it; check the debug screenshot.")
        time.sleep(3)
    status.update(message=f'Uploaded {os.path.basename(image_path)} {tag}'.strip())
    return True

def get_editor(drv):
    for sel in ["div.ql-editor[data-placeholder='Describe your image']", "div.ql-editor[contenteditable='true']", "div[contenteditable='true']"]:
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
            content = drv.execute_script("return (arguments[0].textContent||'').trim();", editor) or ''
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
        drv.execute_script("document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);")
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
        raise RuntimeError('could not find the Gemini prompt box')
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
                ActionChains(drv).key_down(Keys.SHIFT).send_keys(Keys.RETURN).key_up(Keys.SHIFT).perform()
                time.sleep(0.03)
        time.sleep(0.3)
        if _verify_editor_content(drv, editor, text, timeout=6.0):
            return True
    except Exception:
        pass
    raise RuntimeError('found the Gemini prompt box but could not verify the prompt was typed into it — neither instant JS insertion nor chunked send_keys ever verified; check the debug screenshot.')

def click_send(drv):
    try:
        result = drv.execute_script('\n            var icons=document.querySelectorAll(\n                \'mat-icon[fonticon="arrow_upward"],mat-icon[data-mat-icon-name="arrow_upward"]\');\n            for(var i=0;i<icons.length;i++){\n                var b=icons[i].closest(\'button\');\n                if(b&&!b.disabled&&b.offsetParent!==null){b.click();return \'OK_UP\';}\n            }\n            var sendIcons=document.querySelectorAll(\n                \'mat-icon[fonticon="send"],mat-icon[data-mat-icon-name="send"]\');\n            for(var i=0;i<sendIcons.length;i++){\n                var b=sendIcons[i].closest(\'button\');\n                if(b&&!b.disabled&&b.offsetParent!==null){b.click();return \'OK_SEND\';}\n            }\n            var btns=document.querySelectorAll(\n                \'button[aria-label="Send message"],button[data-test-id="send-button"]\');\n            for(var i=0;i<btns.length;i++){\n                if(!btns[i].disabled&&btns[i].offsetParent!==null){btns[i].click();return \'OK_ARIA\';}\n            }\n            return \'NO\';\n        ')
        if result and result.startswith('OK'):
            return True
    except Exception:
        pass
    for sel in ["button[aria-label='Send message']", "button[data-test-id='send-button']", "button[aria-label*='Send']"]:
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
        return set(drv.execute_script('return Array.from(document.querySelectorAll(\'img[src^="blob:"],img[src*="googleusercontent"]\')).map(i=>i.src).filter(s=>s&&s.length>10);') or [])
    except Exception:
        return set()

def check_new_image(drv, urls_before):
    try:
        new_srcs = drv.execute_script('\n            var srcs=[];\n            var imgs=document.querySelectorAll(\n                \'img[src^="blob:https://gemini.google.com"]\');\n            for (var i=imgs.length-1;i>=0;i--){\n                var img=imgs[i]; if(!img.offsetParent) continue;\n                var src=img.getAttribute(\'src\')||\'\';\n                var tid=img.getAttribute(\'data-test-id\')||\'\';\n                if (tid.includes(\'uploaded-img\')) continue;\n                if (src.length>10) srcs.push(src);\n            } return srcs;\n        ') or []
        for src in new_srcs:
            if src not in urls_before:
                return src
    except Exception:
        pass
    return None

def check_new_image_lenient(drv, urls_before):
    try:
        new_srcs = drv.execute_script('\n            var srcs=[];\n            var imgs=document.querySelectorAll(\n                \'img[src^="blob:https://gemini.google.com"]\');\n            for (var i=imgs.length-1;i>=0;i--){\n                var img=imgs[i]; if(!img.offsetParent) continue;\n                var src=img.getAttribute(\'src\')||\'\';\n                if (src.length>10) srcs.push(src);\n            } return srcs;\n        ') or []
        for src in new_srcs:
            if src not in urls_before:
                return src
    except Exception:
        pass
    return None

def wait_for_image(drv, urls_before, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        src = check_new_image(drv, urls_before)
        if src:
            return src
        time.sleep(1.0)
    return None

def set_download_behavior(drv, download_dir):
    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': os.path.abspath(download_dir)})
        return True
    except Exception:
        return False

def _direct_fetch_image(drv, save_path, urls_before):
    try:
        blob = drv.execute_script('\n            var imgs=document.querySelectorAll(\n                \'single-image img,generated-image img,\'\n                \'img[src^="blob:https://gemini.google.com"]\');\n            for (var i=imgs.length-1;i>=0;i--){\n                var s=imgs[i].getAttribute(\'src\');\n                if (s && s.startsWith(\'blob:https://gemini.google.com\')) return s;\n            } return null;\n        ')
        if not blob or blob in urls_before:
            return False
        result = drv.execute_cdp_cmd('Runtime.evaluate', {'expression': f"fetch('{blob}').then(r=>r.blob()).then(b=>new Promise(resolve=>{{const fr=new FileReader();fr.onloadend=()=>resolve(fr.result.split(',')[1]);fr.readAsDataURL(b);}}));", 'awaitPromise': True, 'returnByValue': True})
        if result and 'result' in result and ('value' in result['result']):
            data = base64.b64decode(result['result']['value'])
            if len(data) > 5000:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                Path(save_path).write_bytes(data)
                return True
    except Exception:
        pass
    return False

def _click_download_button(drv):
    selectors = [('css', "button[data-test-id='download-generated-image-button']"), ('css', "button[aria-label='Download']"), ('css', "button[aria-label='Download image']"), ('css', "button[aria-label*='Download']"), ('xpath', "//button[contains(@aria-label,'Download')]"), ('xpath', "//mat-icon[contains(@fonticon,'download')]/ancestor::button")]
    for by_type, sel in selectors:
        try:
            by = By.XPATH if by_type == 'xpath' else By.CSS_SELECTOR
            for btn in reversed(drv.find_elements(by, sel)):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
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
    for sel in ('single-image img', 'generated-image img', "img[src^='blob:https://gemini.google.com']"):
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
                if src in urls_before or len(src) < 10 or (not img.is_displayed()):
                    continue
                drv.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'smooth'});", img)
                time.sleep(0.4)
                try:
                    ActionChains(drv).move_to_element(img).perform()
                    time.sleep(0.5)
                    if _click_download_button(drv):
                        return True
                except Exception:
                    pass
                try:
                    drv.execute_script("\n                        var el=arguments[0];\n                        ['mouseenter','mouseover','mousemove'].forEach(function(evt){\n                            el.dispatchEvent(new MouseEvent(evt,{bubbles:true,cancelable:true,view:window,\n                                clientX:el.getBoundingClientRect().left+el.offsetWidth/2,\n                                clientY:el.getBoundingClientRect().top+el.offsetHeight/2}));\n                        });\n                    ", img)
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
            new_files = {f for f in cur - files_before if not f.endswith(('.crdownload', '.tmp', '.part')) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))}
            if new_files:
                fname = sorted(new_files, key=lambda f: os.path.getmtime(os.path.join(dl_dir, f)), reverse=True)[0]
                fpath = os.path.join(dl_dir, fname)
                if os.path.getsize(fpath) > 5000:
                    return fpath
        except Exception:
            pass
        time.sleep(0.4)
    return None

def _wmr_find_file_input(drv):
    try:
        inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if inputs:
            return inputs[0]
    except Exception:
        pass
    try:
        drv.execute_script('\n            document.querySelectorAll(\'input[type="file"]\').forEach(function(el){\n                el.style.cssText=\'display:block!important;opacity:1!important;\'\n                    +\'position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;\';\n                el.removeAttribute(\'hidden\');\n                el.removeAttribute(\'disabled\');\n            });\n        ')
    except Exception:
        pass
    time.sleep(0.3)
    try:
        inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
        return inputs[0] if inputs else None
    except Exception:
        return None

def _wmr_check_status(drv):
    try:
        result = drv.execute_script("\n            function findDownloadBtn() {\n                var btn = document.querySelector('button.bg-success');\n                if (btn && !btn.disabled) {\n                    var style = window.getComputedStyle(btn);\n                    if (style.display !== 'none' && style.visibility !== 'hidden') return btn;\n                }\n                var spans = document.querySelectorAll('span');\n                for (var i = 0; i < spans.length; i++) {\n                    if ((spans[i].textContent || '').trim() === 'Download PNG') {\n                        var b = spans[i].closest('button');\n                        if (b && !b.disabled) return b;\n                    }\n                }\n                return null;\n            }\n            if (findDownloadBtn()) return 'DONE';\n            var allText = document.body ? document.body.innerText.toLowerCase() : '';\n            if (allText.indexOf('detecting') !== -1 || allText.indexOf('processing') !== -1) return 'BUSY';\n            if (allText.indexOf('not detected') !== -1 || allText.indexOf('no watermark') !== -1) {\n                return findDownloadBtn() ? 'DONE' : 'NOT_FOUND';\n            }\n            if (allText.length < 10) return 'LOADING';\n            return 'BUSY';\n        ")
        return (result or 'error').lower()
    except Exception:
        return 'error'

def _wmr_click_download(drv):
    try:
        result = drv.execute_script("\n            var btn = document.querySelector('button.bg-success');\n            if (btn && !btn.disabled) { btn.scrollIntoView({block:'center'}); btn.click(); return 'OK'; }\n            var spans = document.querySelectorAll('span');\n            for (var i = 0; i < spans.length; i++) {\n                if ((spans[i].textContent || '').trim() === 'Download PNG') {\n                    var b = spans[i].closest('button');\n                    if (b && !b.disabled) { b.scrollIntoView({block:'center'}); b.click(); return 'OK'; }\n                }\n            }\n            return null;\n        ")
        return result == 'OK'
    except Exception:
        return False

def convert_to_webp(png_path, max_size_kb=400, min_quality=20, downscale_floor=0.5):
    try:
        from PIL import Image
    except ImportError:
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'Pillow'], timeout=60, capture_output=True)
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
            working = img if scale >= 0.999 else img.resize((max(64, int(orig_w * scale)), max(64, int(orig_h * scale))), Image.Resampling.LANCZOS)
            if len(encode(working, min_quality)) / 1024 > max_size_kb:
                scale -= 0.1
                continue
            low, high, best_q = (min_quality, 95, min_quality)
            while low <= high:
                mid = (low + high) // 2
                if len(encode(working, mid)) / 1024 <= max_size_kb:
                    best_q = mid
                    low = mid + 1
                else:
                    high = mid - 1
            Path(webp_path).write_bytes(encode(working, best_q))
            return webp_path
        working = img.resize((max(64, int(orig_w * downscale_floor)), max(64, int(orig_h * downscale_floor))), Image.Resampling.LANCZOS)
        Path(webp_path).write_bytes(encode(working, min_quality))
        return webp_path
    except Exception:
        return None

def remove_watermark(drv, image_path, download_dir, status, timeout=60):
    gemini_handle = drv.current_window_handle
    try:
        if not open_gemini_tab(drv, WMR_URL, wait_sec=1.5):
            status.update(message='Could not open the watermark remover — keeping original image.')
            return False
        set_download_behavior(drv, download_dir)
        file_input = _wmr_find_file_input(drv)
        if not file_input:
            time.sleep(0.5)
            file_input = _wmr_find_file_input(drv)
        if not file_input:
            status.update(message='Watermark remover: no file input found — keeping original image.')
            return False
        file_input.send_keys(os.path.abspath(image_path))
        status.update(message='Removing Gemini watermark...')
        deadline = time.time() + timeout
        outcome = 'error'
        while time.time() < deadline:
            outcome = _wmr_check_status(drv)
            if outcome in ('done', 'not_found', 'error'):
                break
            time.sleep(1.0)
        if outcome == 'not_found':
            status.update(message='No watermark detected — keeping original image.')
            return False
        if outcome != 'done':
            status.update(message='Watermark removal timed out — keeping original image.')
            return False
        files_before = set(os.listdir(download_dir)) if os.path.exists(download_dir) else set()
        if not _wmr_click_download(drv):
            status.update(message='Watermark remover: could not click Download — keeping original image.')
            return False
        fpath = _wait_for_download(download_dir, files_before, timeout=20)
        if not fpath:
            status.update(message='Watermark remover: download never landed — keeping original image.')
            return False
        try:
            Path(fpath).rename(image_path)
        except Exception:
            Path(image_path).write_bytes(Path(fpath).read_bytes())
        status.update(message='Watermark removed.')
        return True
    except Exception as e:
        status.update(message=f'Watermark removal failed ({e}) — keeping original image.')
        return False
    finally:
        try:
            if drv.current_window_handle != gemini_handle:
                drv.close()
            drv.switch_to.window(gemini_handle)
        except Exception:
            pass
_WMR_QUEUE = None
_WMR_THREAD = None
_WMR_START_LOCK = threading.Lock()

def _remove_watermark_standalone(drv2, image_path, download_dir, timeout=60):
    try:
        drv2.get(WMR_URL)
        time.sleep(1.5)
        set_download_behavior(drv2, download_dir)
        file_input = _wmr_find_file_input(drv2)
        if not file_input:
            time.sleep(0.5)
            file_input = _wmr_find_file_input(drv2)
        if not file_input:
            return False
        file_input.send_keys(os.path.abspath(image_path))
        deadline = time.time() + timeout
        outcome = 'error'
        while time.time() < deadline:
            outcome = _wmr_check_status(drv2)
            if outcome in ('done', 'not_found', 'error'):
                break
            time.sleep(1.0)
        if outcome != 'done':
            return False
        files_before = set(os.listdir(download_dir)) if os.path.exists(download_dir) else set()
        if not _wmr_click_download(drv2):
            return False
        fpath = _wait_for_download(download_dir, files_before, timeout=20)
        if not fpath:
            return False
        try:
            Path(fpath).rename(image_path)
        except Exception:
            Path(image_path).write_bytes(Path(fpath).read_bytes())
        return True
    except Exception:
        return False

def _wmr_worker_loop(chrome_bin, wmr_download_dir, work_queue):
    drv2 = None
    try:
        while True:
            item = work_queue.get()
            try:
                if item is None:
                    return
                idx, image_path, set_combo = item
                if drv2 is None:
                    try:
                        drv2 = gl.make_driver(chrome_bin, 1280, 900, wmr_download_dir)
                    except Exception:
                        drv2 = None
                if drv2 is not None:
                    ok = False
                    for _attempt in range(2):
                        try:
                            if _remove_watermark_standalone(drv2, image_path, wmr_download_dir):
                                ok = True
                                break
                        except Exception:
                            pass
                    if not ok:
                        pass
                webp_path = convert_to_webp(image_path)
                set_combo(idx, phase='done', message='Done', output=os.path.basename(image_path), output_webp=os.path.basename(webp_path) if webp_path else None)
            finally:
                work_queue.task_done()
    finally:
        try:
            if drv2:
                drv2.quit()
        except Exception:
            pass

def start_watermark_worker(chrome_bin, download_dir, status):
    global _WMR_QUEUE, _WMR_THREAD
    with _WMR_START_LOCK:
        if _WMR_THREAD is not None:
            return
        wmr_download_dir = os.path.join(download_dir, '_wmr_downloads')
        os.makedirs(wmr_download_dir, exist_ok=True)
        _WMR_QUEUE = queue.Queue()
        _WMR_THREAD = threading.Thread(target=_wmr_worker_loop, args=(chrome_bin, wmr_download_dir, _WMR_QUEUE), daemon=True)
        _WMR_THREAD.start()

def enqueue_watermark_removal(idx, image_path, set_combo):
    if _WMR_QUEUE is not None:
        _WMR_QUEUE.put((idx, image_path, set_combo))

def stop_watermark_worker(wait_s=240):
    global _WMR_QUEUE, _WMR_THREAD
    with _WMR_START_LOCK:
        thread, q = (_WMR_THREAD, _WMR_QUEUE)
        _WMR_THREAD = None
        _WMR_QUEUE = None
    if thread is None:
        return
    try:
        q.put(None)
        thread.join(timeout=wait_s)
    except Exception:
        pass

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
            fpath = _wait_for_download(download_dir, files_before_dl, timeout=30 if hover_ok else 8)
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

def run_batch_generation(drv, status, args, combos, image_path, model_image_path, chrome_bin=None):
    tab_cap = max(1, int(getattr(args, 'max_tabs', 6) or 6))
    if chrome_bin:
        start_watermark_worker(chrome_bin, args.output_dir, status)
    gen_dir = os.path.join(args.output_dir, 'generated')
    inbox_dir = os.path.join(args.output_dir, 'inbox')
    os.makedirs(gen_dir, exist_ok=True)
    os.makedirs(inbox_dir, exist_ok=True)
    for d, prefix in ((gen_dir, 'combo-'), (inbox_dir, '')):
        for f in os.listdir(d):
            if f.startswith(prefix):
                try:
                    os.remove(os.path.join(d, f))
                except OSError:
                    pass
    states = [{'idx': c['idx'], 'label': c.get('label') or f"look {c['idx'] + 1}", 'phase': 'queued', 'message': '', 'output': None} for c in combos]
    accepting = {'open': True}

    def sync(msg=None):
        done = sum((1 for s in states if s['phase'] == 'done'))
        errs = sum((1 for s in states if s['phase'] == 'error'))
        status.update(phase='generating', accepting=accepting['open'], message=msg or f'Generating {len(states)} shots in {len(tabs)} tabs — {done} done, {errs} failed...', combos=[dict(s) for s in states])

    def set_combo(idx, **kw):
        for s in states:
            if s['idx'] == idx:
                s.update(kw)
        sync()
    queue = list(combos)
    outputs = []
    parked = []
    limited_models = set()
    limit_cycles = 0

    def ingest_inbox():
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
            if holo and (not os.path.isfile(hpath)):
                continue
            try:
                os.remove(jpath)
            except OSError:
                pass
            idx = int(spec.get('idx', -1))
            if idx < 0 or any((c['idx'] == idx for c in combos)):
                continue
            combo = {'idx': idx, 'label': spec.get('label') or f'look {idx + 1}', 'prompt': spec.get('prompt') or (combos[0]['prompt'] if combos else ''), 'hologram_path': hpath}
            combos.append(combo)
            states.append({'idx': idx, 'label': combo['label'], 'phase': 'queued', 'message': '', 'output': None})
            queue.append(combo)
            added += 1
        if added:
            sync(f'{added} new look(s) joined the live batch.')
        return added
    tabs = [{'handle': drv.current_window_handle, 'combo': None, 'urls_before': set(), 'started': 0.0, 'model': None, 'fresh': True}]

    def grow_tabs():
        while len(queue) + len([t for t in tabs if t['combo']]) > len(tabs) and len(tabs) < tab_cap:
            drv.switch_to.window(tabs[0]['handle'])
            if not open_gemini_tab(drv, GEMINI_URL):
                break
            tabs.append({'handle': drv.current_window_handle, 'combo': None, 'urls_before': set(), 'started': 0.0, 'model': None, 'fresh': True})
            time.sleep(0.8)
    sync(f'Opening Gemini tabs for {len(states)} shots...')
    grow_tabs()

    def setup_tab_job(tab, combo, model=None):
        idx = combo['idx']
        target_model = model or args.gemini_model
        try:
            drv.switch_to.window(tab['handle'])
            click_menu_item(drv, ['dismiss'])
            set_combo(idx, phase='preparing', message='Setting up the chat...')
            if not tab['fresh']:
                start_new_chat(drv)
                time.sleep(1.0)
            tab['fresh'] = False
            if target_model:
                select_gemini_model(drv, target_model, status)
                tab['model'] = target_model
            combo['_model'] = tab.get('model')
            if not activate_create_image_mode(drv, status, tag=f'(look {idx})'):
                raise RuntimeError("could not switch this tab into 'Create image' mode")
            image_paths = [image_path]
            if combo.get('hologram_path'):
                image_paths.append(combo['hologram_path'])
            if model_image_path:
                image_paths.append(model_image_path)
            upload_images(drv, image_paths, status)
            type_prompt(drv, combo['prompt'])
            tab['urls_before'] = snapshot_urls(drv)
            if not click_send(drv):
                raise RuntimeError('could not click send')
            tab['combo'] = combo
            tab['started'] = time.time()
            set_combo(idx, phase='generating', message='Gemini is generating...')
            return True
        except Exception as e:
            set_combo(idx, phase='error', message=str(e)[:200])
            return False
    while True:
        ingest_inbox()
        grow_tabs()
        for tab in tabs:
            if tab['combo'] is None and queue:
                combo = queue.pop(0)
                setup_tab_job(tab, combo)
                break
        active = [t for t in tabs if t['combo'] is not None]
        if not active and (not queue):
            if ingest_inbox():
                continue
            if parked and limit_cycles < int(getattr(args, 'max_limit_cycles', 3) or 3):
                limit_cycles += 1
                resume_at = time.time() + int(getattr(args, 'limit_wait', 3600) or 3600)
                while time.time() < resume_at:
                    mins = int((resume_at - time.time()) / 60) + 1
                    status.update(phase='limit_wait', accepting=True, resume_at=resume_at, message=f"Gemini's limit is reached — resuming automatically in ~{mins} min. Your looks are safe.", combos=[dict(s) for s in states])
                    time.sleep(15)
                    ingest_inbox()
                limited_models.clear()
                status.update(resume_at=None)
                for c in parked:
                    c['_attempts'] = 0
                    queue.append(c)
                    set_combo(c['idx'], phase='queued', message='Resuming after the limit reset...')
                parked.clear()
                continue
            if parked:
                for c in parked:
                    set_combo(c['idx'], phase='error', message="Gemini's limit didn't lift after several waits — try this look again later")
                parked.clear()
            accepting['open'] = False
            status.update(accepting=False)
            break
        for tab in active:
            combo = tab['combo']
            idx = combo['idx']
            try:
                drv.switch_to.window(tab['handle'])
                timed_out = time.time() - tab['started'] > args.generation_timeout
                if timed_out:
                    src = check_new_image_lenient(drv, tab['urls_before'])
                else:
                    src = check_new_image(drv, tab['urls_before'])
                if not src:
                    if timed_out:
                        shot = save_debug_screenshot(drv, args.output_dir, f'look-{idx:02d}-timeout')
                        set_combo(idx, phase='error', message=f'no image within {args.generation_timeout}s', debug_screenshot=os.path.basename(shot) if shot else None)
                        tab['combo'] = None
                        continue
                    tab['checks'] = tab.get('checks', 0) + 1
                    if tab['checks'] % 3 == 0:
                        verdict = check_limit_or_refusal(drv)
                        if verdict == 'refusal':
                            set_combo(idx, phase='error', message='Gemini declined this prompt for this look')
                            tab['combo'] = None
                        elif verdict == 'limit':
                            limited_models.add(combo.get('_model') or '__default__')
                            nxt = next((m for m in FALLBACK_MODELS if m not in limited_models), None)
                            combo['_attempts'] = combo.get('_attempts', 0) + 1
                            tab['combo'] = None
                            if nxt and combo['_attempts'] < 4:
                                set_combo(idx, phase='preparing', message=f'Limit on this model — retrying on {nxt}...')
                                setup_tab_job(tab, combo, model=nxt)
                            else:
                                set_combo(idx, phase='limit_parked', message="Gemini's limit is hit — parked for automatic resume")
                                parked.append(combo)
                    continue
                set_combo(idx, phase='downloading', message='Downloading the image...')
                save_path = os.path.join(gen_dir, f'combo-{idx:02d}.png')
                set_download_behavior(drv, args.output_dir)
                if download_image(drv, save_path, tab['urls_before'], args.output_dir):
                    outputs.append(save_path)
                    set_combo(idx, phase='removing_watermark', message='Removing the watermark...')
                    enqueue_watermark_removal(idx, save_path, set_combo)
                else:
                    set_combo(idx, phase='error', message='generated but download failed')
                tab['combo'] = None
            except Exception as e:
                set_combo(idx, phase='error', message=f'lost control of this tab: {e}'[:200])
                tab['combo'] = None
        time.sleep(1.0)
    stop_watermark_worker()
    done_states = [s for s in states if s['phase'] == 'done']
    ok = len(done_states)
    if ok == 0:
        status.update(phase='error', finished=True, accepting=False, error=f'all {len(states)} shots failed', combos=[dict(s) for s in states])
        return None
    status.update(phase='done', finished=True, accepting=False, message=f'{ok}/{len(states)} shots generated.', output_image=os.path.join(gen_dir, done_states[0]['output']), combos=[dict(s) for s in states])
    return outputs

def main():
    global By, Keys, ActionChains
    parser = argparse.ArgumentParser(description='Gemini generate worker (login + image/prompt -> generated image)')
    parser.add_argument('--status-file', required=True)
    parser.add_argument('--output-dir', default='./gemini_generate_session')
    parser.add_argument('--cookies-file', default=None, help='Defaults to <output-dir>/google_cookies.pkl')
    parser.add_argument('--profile-dir', default=None, help="Persistent Chrome user-data-dir to reuse across runs. Defaults to <output-dir>/chrome_profile, which is a fresh empty profile whenever the caller uses a per-job --output-dir (queue_worker.py does exactly that) — Google's login risk check looks at device-trust signals that live in the profile directory, not just cookies, so a brand-new profile re-triggers a fresh 'verify it's you' challenge on every single job even with valid cookies. Pass a stable shared path here so one manual login trusts the device for every later job instead.")
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--login-timeout', type=int, default=900)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--image-path', default=None, help='Local image to upload as a reference. Omit for pure text-to-image (Create image mode).')
    parser.add_argument('--model-image-path', default=None, help='Optional second image (a real fashion-studio model reference photo) — attached alongside --image-path in the same chat turn.')
    parser.add_argument('--hologram-image-path', default=None, help='Optional pose/hologram reference for the selected style/package scene (MANNEQUIN_REF) — attached alongside --image-path in the same chat turn.')
    parser.add_argument('--gemini-model', default='Flash', help="Best-effort substring match against Gemini's own in-app model switcher (see select_gemini_model()). Defaults to 'Flash' — the reference pipeline (ECOM COMBO PHOTOSHOOT ORDER.ipynb) always pins every tab to Flash rather than leaving it to whatever model a reused/persistent profile happened to last have active. Never fails the job — pass an empty string to skip switching entirely.")
    parser.add_argument('--generation-timeout', type=int, default=180)
    parser.add_argument('--max-tabs', type=int, default=6, help='Batch mode only — how many parallel Gemini tabs to run at once. 6 matches the reference pipeline, proven on a Colab VM.')
    parser.add_argument('--limit-wait', type=int, default=3600, help="Batch mode — seconds to wait before auto-resuming looks parked by Gemini's generation limit (its caps reset on the hour scale).")
    parser.add_argument('--max-limit-cycles', type=int, default=3, help='Batch mode — how many limit-wait cycles to attempt before failing the still-parked looks (guards against hard daily caps).')
    parser.add_argument('--screen-width', type=int, default=1920)
    parser.add_argument('--screen-height', type=int, default=1080)
    parser.add_argument('--keep-alive', action='store_true', help="On success, leave the browser open (in this kernel's globals) instead of quitting it, so a later `colab exec` on the same Colab session can reuse it for the NEXT Generate without logging in again. If this run itself reused an existing persistent driver, omitting this flag ends the persistent session (quits the browser) once this job finishes.")
    parser.add_argument('--watch-live', action='store_true', help="Set up the Xvfb+noVNC remote-view pipeline even when reusing an already-logged-in persistent driver (normally skipped entirely on that fast path, since headless automation needs no display for a human to watch) — lets Developer mode show the browser live while a Generate that doesn't need a fresh login still runs.")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    cookies_file = args.cookies_file or os.path.join(args.output_dir, 'google_cookies.pkl')
    if EMBEDDED_COOKIES_B64:
        Path(cookies_file).parent.mkdir(parents=True, exist_ok=True)
        Path(cookies_file).write_bytes(base64.b64decode(EMBEDDED_COOKIES_B64))
    profile_dir = args.profile_dir or os.path.join(args.output_dir, 'chrome_profile')
    profile_archive_out = os.path.join(args.output_dir, 'chrome_profile.zip')
    if EMBEDDED_CHROME_PROFILE_REMOTE:
        gl.restore_chrome_profile(profile_dir, EMBEDDED_CHROME_PROFILE_REMOTE)
    image_path = args.image_path
    if EMBEDDED_IMAGE_REMOTE and os.path.exists(EMBEDDED_IMAGE_REMOTE):
        image_path = EMBEDDED_IMAGE_REMOTE
    elif EMBEDDED_IMAGE_B64:
        image_path = os.path.join(args.output_dir, f"reference_image{EMBEDDED_IMAGE_EXT or '.png'}")
        Path(image_path).parent.mkdir(parents=True, exist_ok=True)
        Path(image_path).write_bytes(base64.b64decode(EMBEDDED_IMAGE_B64))
    model_image_path = args.model_image_path
    if EMBEDDED_MODEL_IMAGE_REMOTE and os.path.exists(EMBEDDED_MODEL_IMAGE_REMOTE):
        model_image_path = EMBEDDED_MODEL_IMAGE_REMOTE
    elif EMBEDDED_MODEL_IMAGE_B64:
        model_image_path = os.path.join(args.output_dir, f"model_image{EMBEDDED_MODEL_IMAGE_EXT or '.webp'}")
        Path(model_image_path).parent.mkdir(parents=True, exist_ok=True)
        Path(model_image_path).write_bytes(base64.b64decode(EMBEDDED_MODEL_IMAGE_B64))
    hologram_image_path = args.hologram_image_path
    if EMBEDDED_HOLOGRAM_IMAGE_B64:
        hologram_image_path = os.path.join(args.output_dir, f"hologram_image{EMBEDDED_HOLOGRAM_IMAGE_EXT or '.webp'}")
        Path(hologram_image_path).parent.mkdir(parents=True, exist_ok=True)
        Path(hologram_image_path).write_bytes(base64.b64decode(EMBEDDED_HOLOGRAM_IMAGE_B64))
    batch_combos = None
    if EMBEDDED_BATCH_B64:
        payload = json.loads(base64.b64decode(EMBEDDED_BATCH_B64))
        batch_combos = payload.get('combos') or None
        for c in batch_combos or []:
            if c.get('hologram_remote') and os.path.exists(c['hologram_remote']):
                c['hologram_path'] = c['hologram_remote']
            elif c.get('hologram_b64'):
                hp = os.path.join(args.output_dir, f"hologram_{int(c['idx']):02d}{c.get('hologram_ext') or '.webp'}")
                Path(hp).parent.mkdir(parents=True, exist_ok=True)
                Path(hp).write_bytes(base64.b64decode(c['hologram_b64']))
                c['hologram_path'] = hp
    status = gl.Status(args.status_file)
    headless = args.headless or gl.is_colab()
    mode = 'colab' if gl.is_colab() else 'local-headless' if args.headless else 'local'
    status.update(mode=mode, message=f"Starting in '{mode}' mode.")
    debug_screenshot_path = None
    global _PERSISTENT_DRIVER, _PERSISTENT_VNC_URL
    try:
        chrome_bin = gl.ensure_deps(status, headless)
        from selenium.webdriver.common.by import By as _By
        from selenium.webdriver.common.keys import Keys as _Keys
        from selenium.webdriver.common.action_chains import ActionChains as _ActionChains
        By = _By
        Keys = _Keys
        ActionChains = _ActionChains
        drv = _PERSISTENT_DRIVER
        reused_driver = False
        if drv is not None:
            status.update(phase='checking_session', message='Checking existing browser session...')
            if gl.is_logged_in(drv):
                reused_driver = True
                if args.watch_live and headless and _PERSISTENT_VNC_URL:
                    status.update(vnc_url=_PERSISTENT_VNC_URL)
                status.update(phase='reusing_session', message='Reusing already-logged-in browser — no login/noVNC needed this time.')
            else:
                try:
                    drv.quit()
                except Exception:
                    pass
                drv = None
                _PERSISTENT_DRIVER = None
        if not reused_driver:
            if headless:
                vnc_url = gl.start_display_and_vnc(status, args.screen_width, args.screen_height)
                _PERSISTENT_VNC_URL = vnc_url
                status.update(vnc_url=vnc_url, message='Virtual display ready — open vnc_url to log in if needed.')
            status.update(phase='launching_browser', message=f'Launching Chrome ({chrome_bin})...')
            drv = gl.make_driver(chrome_bin, args.screen_width, args.screen_height, args.output_dir, profile_dir)
        have_logged_in_driver = reused_driver
        keep_driver_alive = False
        try:
            if not reused_driver:
                if not gl.handle_login(drv, status, cookies_file, args.login_timeout, mark_finished=False, profile_dir=profile_dir, profile_archive_out=profile_archive_out):
                    return
                have_logged_in_driver = True
            status.update(phase='opening_gemini', message='Opening Gemini...')
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
                status.update(message='Starting a new chat...')
                start_new_chat(drv)
                time.sleep(1.0)
            if batch_combos and image_path:
                run_batch_generation(drv, status, args, batch_combos, image_path, model_image_path, chrome_bin)
                if bool(args.keep_alive):
                    status.update(message=status.data.get('message', '') + ' (browser kept open for reuse)')
                return
            if args.gemini_model:
                status.update(phase='selecting_model', message=f"Trying to select Gemini model matching '{args.gemini_model}'...")
                select_gemini_model(drv, args.gemini_model, status)
            prompt = args.prompt
            if image_path:
                status.update(phase='switching_mode', message='Switching to Create image mode...')
                if not activate_create_image_mode(drv, status):
                    raise RuntimeError("could not switch Gemini into 'Create image' mode")
                image_paths = [image_path]
                if hologram_image_path:
                    image_paths.append(hologram_image_path)
                if model_image_path:
                    image_paths.append(model_image_path)
                status.update(phase='uploading_image', message=f'Uploading {os.path.basename(image_path)}...')
                upload_images(drv, image_paths, status)
            else:
                status.update(phase='switching_mode', message='Switching to Create image mode...')
                if not activate_create_image_mode(drv, status):
                    raise RuntimeError("could not switch Gemini into 'Create image' mode")
            status.update(phase='typing_prompt', message='Typing prompt...')
            type_prompt(drv, prompt)
            status.update(message='Prompt entered.')
            urls_before = snapshot_urls(drv)
            status.update(phase='sending', message='Sending prompt...')
            if not click_send(drv):
                raise RuntimeError('could not click send')
            status.update(phase='generating', message=f'Waiting for Gemini to generate the image (up to {args.generation_timeout}s)...')
            img_url = wait_for_image(drv, urls_before, timeout=args.generation_timeout)
            if not img_url:
                raise RuntimeError('no image appeared within the generation timeout')
            status.update(message='Gemini generated the image.')
            status.update(phase='downloading_result', message='Downloading generated image...')
            safe_name = re.sub('[^\\w\\-]+', '_', args.prompt[:40]).strip('_') or 'gemini_output'
            save_path = os.path.join(args.output_dir, 'generated', f'{safe_name}.png')
            if not download_image(drv, save_path, urls_before, args.output_dir):
                raise RuntimeError('image generated but could not be downloaded — neither the direct blob fetch nor a real click-through download ever produced a file; check the debug screenshot.')
            status.update(phase='removing_watermark', message='Removing Gemini watermark...')
            remove_watermark(drv, save_path, args.output_dir, status)
            webp_path = convert_to_webp(save_path)
            status.update(phase='done', message=f'Saved to {save_path}', output_image=save_path, output_image_webp=webp_path, finished=True)
            if bool(args.keep_alive):
                status.update(message=status.data.get('message', '') + ' (browser kept open for reuse)')
        except Exception:
            debug_screenshot_path = save_debug_screenshot(drv, args.output_dir, 'failure')
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
        status.update(phase='error', message=str(e), error=str(e), debug_screenshot=debug_screenshot_path, finished=True)
        raise
if __name__ == '__main__':
    main()