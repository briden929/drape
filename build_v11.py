import re

V10_PATH = r"C:\Users\PC\.gemini\antigravity\scratch\FULL_QUEUE_WORKER_V10_FINAL.py"
V11_PATH = r"C:\Users\PC\Downloads\FULL_QUEUE_WORKER_V11.py"

with open(V10_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# ============================================================================
# 1. REPLACE click_plus_button with V11 version
# ============================================================================
old_click_plus = '''def click_plus_button(drv):
    try:
        res = drv.execute_script("""
            var btns = document.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                var b = btns[i];
                if (b.offsetParent === null) continue;
                var lbl = (b.getAttribute('aria-label') || '').toLowerCase();
                if (lbl.indexOf('upload') !== -1 || lbl.indexOf('tools') !== -1 || lbl.indexOf('plus') !== -1) {
                    b.click(); return 'OK';
                }
                var icon = b.querySelector('mat-icon[fonticon="plus"], mat-icon[data-mat-icon-name="plus"]');
                if (icon) { b.click(); return 'OK'; }
            } return 'NO';
        """)
        if res == 'OK':
            time.sleep(0.3)
            return True
    except Exception:
        pass
    for sel in ['button[aria-label="Upload and tools"]', 'button[jslog*="300142"]',
                'button[aria-haspopup="menu"][aria-label*="Upload"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    return False'''

new_click_plus = r'''def _get_composer_root(drv, prefix=""):
    """Locate the Gemini image composer container."""
    try:
        editor = None
        for sel in [
            "div.ql-editor[data-placeholder='Describe your image']",
            "div.ql-editor[data-placeholder*='image']",
            "div.ql-editor[contenteditable='true']",
        ]:
            try:
                els = drv.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.is_displayed():
                        editor = el
                        break
                if editor: break
            except Exception: continue
        if not editor:
            try:
                for el in drv.find_elements(By.CSS_SELECTOR, "div[contenteditable='true']"):
                    if el.is_displayed(): editor = el; break
            except Exception: pass
        if not editor:
            log(f"{prefix} COMPOSER_EDITOR_NOT_FOUND")
            return None
        log(f"{prefix} COMPOSER_ANCHOR_FOUND")
        try:
            container = drv.execute_script("""
                var editor = arguments[0];
                var parent = editor.parentElement;
                var maxDepth = 15; var depth = 0;
                while (parent && depth < maxDepth) {
                    var rect = parent.getBoundingClientRect();
                    if (rect.width > 300 && rect.height > 100) {
                        var hasControls = parent.querySelectorAll('button, mat-icon, [role="toolbar"]').length > 0;
                        if (hasControls || parent.classList.contains('composer') || parent.getAttribute('data-testid') || parent.id) return parent;
                    }
                    parent = parent.parentElement; depth++;
                }
                return editor.parentElement;
            """, editor)
            if container and container.is_displayed():
                log(f"{prefix} COMPOSER_ROOT_FOUND"); return container
        except Exception: pass
        try:
            parent = editor.find_element(By.XPATH, "..")
            if parent.is_displayed():
                log(f"{prefix} COMPOSER_ROOT_FOUND (fallback)"); return parent
        except Exception: pass
        log(f"{prefix} COMPOSER_ROOT_NOT_FOUND"); return None
    except Exception as e:
        log(f"{prefix} COMPOSER_ROOT_ERROR: {e}"); return None


def _verify_element_ownership(drv, element, prefix=""):
    try:
        rect = drv.execute_script("""
            var r = arguments[0].getBoundingClientRect();
            return {x:r.x, y:r.y, width:r.width, height:r.height};
        """, element)
        if not rect or rect['width'] <= 0 or rect['height'] <= 0:
            log(f"{prefix} TARGET_RECT_INVALID"); return False
        cx = rect['x'] + rect['width'] / 2; cy = rect['y'] + rect['height'] / 2
        owned = drv.execute_script("""
            var el = document.elementFromPoint(arguments[0], arguments[1]);
            if (!el) return false;
            var target = arguments[2];
            var current = el; var maxIter = 20;
            while (current && maxIter--) { if (current === target) return true; current = current.parentElement; }
            return false;
        """, cx, cy, element)
        if owned:
            log(f"{prefix} TARGET_OWNERSHIP_VERIFIED x={rect['x']:.0f} y={rect['y']:.0f}"); return True
        log(f"{prefix} TARGET_NOT_OWNED x={rect['x']:.0f} y={rect['y']:.0f}"); return False
    except Exception as e:
        log(f"{prefix} TARGET_OWNERSHIP_ERROR: {e}"); return False


def _detect_wrong_sidebar_menu(drv, prefix=""):
    try:
        for label in ["Share conversation", "Pin", "Rename", "Delete"]:
            try:
                for el in drv.find_elements(By.XPATH, f"//*[contains(text(), '{label}')]"):
                    if el.is_displayed():
                        log(f"{prefix} WRONG_SIDEBAR_MENU_OPEN: '{label}'"); return True
            except Exception: continue
        return False
    except Exception: return False


def _press_esc(drv, prefix=""):
    try:
        drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.3); log(f"{prefix} ESC_SENT")
    except Exception: pass


def _reacquire_composer(drv, prefix=""):
    time.sleep(0.3); return _get_composer_root(drv, prefix)


def _safe_click_element(drv, element, prefix="", action_desc=""):
    try:
        if not element.is_displayed():
            log(f"{prefix} TARGET_NOT_VISIBLE ({action_desc})"); return False
        if not element.is_enabled():
            log(f"{prefix} TARGET_DISABLED ({action_desc})"); return False
        rect = drv.execute_script("""
            var r = arguments[0].getBoundingClientRect();
            return {x:r.x, y:r.y, width:r.width, height:r.height,
                    text:(arguments[0].innerText||'').trim().slice(0,40),
                    aria:arguments[0].getAttribute('aria-label')||''};
        """, element)
        if not rect or rect['width'] <= 0 or rect['height'] <= 0:
            log(f"{prefix} TARGET_RECT_INVALID ({action_desc})"); return False
        log(f"{prefix} TARGET_RECT x={rect['x']:.0f} y={rect['y']:.0f} w={rect['width']:.0f} h={rect['height']:.0f} text='{rect.get('text','')}' ({action_desc})")
        cx = rect['x'] + rect['width'] / 2; cy = rect['y'] + rect['height'] / 2
        try:
            owned = drv.execute_script("""
                var el = document.elementFromPoint(arguments[0], arguments[1]);
                if (!el) return false;
                var target = arguments[2]; var current = el; var maxIter = 20;
                while (current && maxIter--) { if (current === target) return true; current = current.parentElement; }
                return false;
            """, cx, cy, element)
            if not owned:
                log(f"{prefix} TARGET_OCCLUDED ({action_desc})")
                drv.execute_script("arguments[0].scrollIntoView({block:'center', behavior:'instant'});", element)
                time.sleep(0.2)
                rect2 = drv.execute_script("""
                    var r = arguments[0].getBoundingClientRect();
                    return {x:r.x, y:r.y, width:r.width, height:r.height};
                """, element)
                if rect2 and rect2['width'] > 0 and rect2['height'] > 0:
                    cx2 = rect2['x'] + rect2['width']/2; cy2 = rect2['y'] + rect2['height']/2
                    owned = drv.execute_script("""
                        var el = document.elementFromPoint(arguments[0], arguments[1]);
                        if (!el) return false;
                        var target = arguments[2]; var current = el; var maxIter = 20;
                        while (current && maxIter--) { if (current === target) return true; current = current.parentElement; }
                        return false;
                    """, cx2, cy2, element)
                    if not owned: log(f"{prefix} TARGET_STILL_OCCLUDED ({action_desc})"); return False
        except Exception: pass
        try:
            ActionChains(drv).move_to_element_with_offset(element, rect['width']/2, rect['height']/2).click().perform()
            log(f"{prefix} CLICKED via ActionChains ({action_desc})"); return True
        except Exception: pass
        try: element.click(); log(f"{prefix} CLICKED via element.click() ({action_desc})"); return True
        except Exception: pass
        try: drv.execute_script("arguments[0].click();", element)
            log(f"{prefix} CLICKED via JS click ({action_desc})"); return True
        except Exception: pass
        log(f"{prefix} CLICK_FAILED ({action_desc})"); return False
    except Exception as e:
        log(f"{prefix} SAFE_CLICK_ERROR ({action_desc}): {e}"); return False


def _log_target_rect(drv, element, prefix, action_desc):
    try:
        rect = drv.execute_script("""
            var r = arguments[0].getBoundingClientRect();
            return {x:r.x, y:r.y, width:r.width, height:r.height,
                    text:(arguments[0].innerText||'').trim().slice(0,50),
                    aria:arguments[0].getAttribute('aria-label')||''};
        """, element)
        if rect:
            log(f"{prefix} TARGET {action_desc}: x={rect['x']:.0f} y={rect['y']:.0f} w={rect['width']:.0f} h={rect['height']:.0f} text='{rect.get('text','')}' aria='{rect.get('aria','')}'")
        return rect
    except Exception: return None


def click_plus_button(drv, tid=0, job_id="") -> bool:
    """V11: Click + button using COMPOSER-SCOPED targeting only."""
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    composer_root = _get_composer_root(drv, prefix)
    if not composer_root: log(f"{prefix} COMPOSER_ROOT_NOT_FOUND"); return False
    if _detect_wrong_sidebar_menu(drv, prefix):
        log(f"{prefix} WRONG_TARGET_MENU_DETECTED — pressing ESC")
        _press_esc(drv, prefix); time.sleep(0.5)
        composer_root = _reacquire_composer(drv, prefix)
        if not composer_root: return False
    
    plus_selectors = ["button[aria-label='Upload and tools']", "button[aria-haspopup='menu'][aria-label*='Upload']", "button[jslog*='300142']"]
    plus_button = None
    for sel in plus_selectors:
        try:
            els = composer_root.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                if el.is_displayed() and el.is_enabled():
                    plus_button = el; log(f"{prefix} COMPOSER_PLUS_FOUND via {sel}"); break
            if plus_button: break
        except Exception: continue
    
    if not plus_button:
        try:
            res = composer_root.execute_script("""
                var icons = this.querySelectorAll('mat-icon[fonticon="plus"], mat-icon[data-mat-icon-name="plus"]');
                for (var i=0;i<icons.length;i++){var btn=icons[i].closest('button');if(btn&&btn.offsetParent!==null&&!btn.disabled)return btn;}
                return null;""")
            if res: plus_button = res; log(f"{prefix} COMPOSER_PLUS_FOUND via mat-icon plus")
        except Exception: pass
    
    if not plus_button:
        try:
            res = composer_root.execute_script("""
                var btns = this.querySelectorAll('button');
                for(var i=0;i<btns.length;i++){var b=btns[i];if(!b.offsetParent||b.disabled)continue;var svgs=b.querySelectorAll('svg[viewBox="0 0 24 24"] path[d*="M12 5v14M5 12h14"]');if(svgs.length>0)return b;}
                return null;""")
            if res: plus_button = res; log(f"{prefix} COMPOSER_PLUS_FOUND via SVG plus")
        except Exception: pass
    
    if not plus_button: log(f"{prefix} COMPOSER_PLUS_NOT_FOUND"); return False
    log(f"{prefix} COMPOSER_PLUS_FOUND")
    _log_target_rect(drv, plus_button, prefix, "PLUS")
    if not _verify_element_ownership(drv, plus_button, prefix):
        log(f"{prefix} PLUS_NOT_OWNED — aborting"); return False
    if _safe_click_element(drv, plus_button, prefix, "PLUS_BUTTON"):
        log(f"{prefix} COMPOSER_PLUS_CLICKED"); time.sleep(0.3); return True
    log(f"{prefix} COMPOSER_PLUS_CLICK_FAILED"); return False
'''

if old_click_plus in code:
    code = code.replace(old_click_plus, new_click_plus)
    print("✅ click_plus_button replaced")
else:
    print("⚠️ click_plus_button pattern not found")

# ============================================================================
# 2. REPLACE _click_send_button
# ============================================================================
old_send = code[code.find("def _click_send_button(drv):"):code.find("def verify_generation_started")]
new_send = r'''def _click_send_button(drv, tid=0, job_id="") -> bool:
    """V11: Click Send button scoped to composer_root."""
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    composer_root = _get_composer_root(drv, prefix)
    send_clicked = False
    send_selectors = ["mat-icon[fonticon='arrow_upward']", "mat-icon[data-mat-icon-name='arrow_upward']", "mat-icon[fonticon='send']", "button[aria-label='Send message']"]
    for sel in send_selectors:
        if send_clicked: break
        try:
            els = composer_root.find_elements(By.CSS_SELECTOR, sel) if composer_root else []
            for el in els:
                btn = el if el.tag_name == 'BUTTON' else el.find_element(By.XPATH, "./ancestor::button")
                if btn and btn.is_displayed() and btn.is_enabled():
                    _log_target_rect(drv, btn, prefix, "SEND")
                    if _verify_element_ownership(drv, btn, prefix):
                        if _safe_click_element(drv, btn, prefix, "SEND_BUTTON"):
                            log(f"{prefix} SEND_CLICKED"); send_clicked = True; break
        except Exception: continue
    if not send_clicked and composer_root is None:
        try:
            res = drv.execute_script("""
                var sels = ['mat-icon[fonticon="arrow_upward"]', 'mat-icon[data-mat-icon-name="arrow_upward"]', 'mat-icon[fonticon="send"]', 'button[aria-label="Send message"]'];
                for (var s=0;s<sels.length;s++){var els=document.querySelectorAll(sels[s]);for(var i=0;i<els.length;i++){var b=els[i].tagName==='BUTTON'?els[i]:els[i].closest('button');if(b&&!b.disabled&&b.offsetParent!==null){b.click();return 'OK';}}}return 'NO';
            """)
            if res == 'OK': log(f"{prefix} SEND_CLICKED (fallback)"); send_clicked = True
        except Exception: pass
    return send_clicked

'''
code = code.replace(old_send, new_send)
print("✅ _click_send_button replaced")

# ============================================================================
# 3. REPLACE perform_robust_upload
# ============================================================================
u_start = code.find("def perform_robust_upload(drv, paths, tid=0, job_id=\"\"):")
u_end = code.find("\ndef verify_attachment_count", u_start)
if u_start == -1 or u_end == -1:
    print("⚠️ perform_robust_upload not found")
else:
    new_upload = r'''def open_upload_drawer(drv, tid=0, job_id="") -> bool:
    """V11: Open upload/tools drawer with proper polling (up to 5s)."""
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    log(f"{prefix} UPLOAD_DRAWER_OPENING")
    if not click_plus_button(drv, tid, job_id):
        log(f"{prefix} PLUS_CLICK_FAILED — cannot open drawer"); return False
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            res = drv.execute_script("""
                var candidates = document.querySelectorAll('div[class*="drawer"], div[class*="toolbox"], div[class*="popover"], [role="menu"], [role="dialog"]');
                for (var i=0;i<candidates.length;i++){var el=candidates[i];if(el.offsetParent!==null){var r=el.getBoundingClientRect();if(r.width>50&&r.height>50)return true;}}
                return false;
            """)
            if res: log(f"{prefix} UPLOAD_DRAWER_OPENED"); return True
        except Exception: pass
        try:
            res = drv.execute_script("""
                var txt = document.body.innerText.toLowerCase();
                return txt.indexOf('upload files') !== -1 || txt.indexOf('upload from computer') !== -1;
            """)
            if res: log(f"{prefix} UPLOAD_DRAWER_OPENED (text detected)"); return True
        except Exception: pass
        time.sleep(0.2)
    log(f"{prefix} UPLOAD_DRAWER_NOT_VISIBLE"); return False


def click_upload_files_in_drawer(drv, tid=0, job_id="") -> bool:
    """V11: Click Upload files inside the visible drawer (drawer-scoped)."""
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    drawer_element = None
    try:
        drawer_element = drv.execute_script("""
            var candidates = document.querySelectorAll('div[class*="drawer"], div[class*="toolbox"], div[class*="popover"], [role="menu"], [role="dialog"]');
            for (var i=0;i<candidates.length;i++){var el=candidates[i];if(el.offsetParent!==null){var r=el.getBoundingClientRect();if(r.width>100&&r.height>50){var t=el.innerText.toLowerCase();if(t.indexOf('upload')!==-1||t.indexOf('files')!==-1)return el;}}}
            var menus = document.querySelectorAll('[role="menu"]');
            for (var i=0;i<menus.length;i++){if(menus[i].offsetParent!==null)return menus[i];}
            return null;
        """)
    except Exception: pass
    if drawer_element: log(f"{prefix} DRAWER_ROOT_FOUND")
    else: log(f"{prefix} DRAWER_ROOT_NOT_FOUND"); return _click_upload_files_fallback(drv, tid, job_id)
    
    upload_button = None
    try:
        els = drawer_element.find_elements(By.CSS_SELECTOR, "button[data-test-id='local-images-files-uploader-button']")
        for el in els:
            if el.is_displayed() and el.is_enabled(): upload_button = el; log(f"{prefix} UPLOAD_CONTROL_FOUND: data-test-id"); break
    except Exception: pass
    if not upload_button:
        try: upload_button = drawer_element.find_element(By.XPATH, ".//button[contains(., 'Upload files')]")
            if upload_button.is_displayed() and upload_button.is_enabled(): log(f"{prefix} UPLOAD_CONTROL_FOUND: text 'Upload files'")
        except Exception: pass
    if not upload_button:
        try: upload_button = drawer_element.find_element(By.XPATH, ".//span[contains(text(),'Upload files')]/ancestor::button")
            if upload_button.is_displayed() and upload_button.is_enabled(): log(f"{prefix} UPLOAD_CONTROL_FOUND: span 'Upload files'")
        except Exception: pass
    if not upload_button:
        try: upload_button = drawer_element.find_element(By.XPATH, ".//button[contains(., 'Upload from computer')]")
            if upload_button.is_displayed() and upload_button.is_enabled(): log(f"{prefix} UPLOAD_CONTROL_FOUND: 'Upload from computer'")
        except Exception: pass
    if not upload_button:
        try: upload_button = drawer_element.find_element(By.CSS_SELECTOR, "button[aria-label*='Upload']")
            if upload_button.is_displayed() and upload_button.is_enabled(): log(f"{prefix} UPLOAD_CONTROL_FOUND: aria-label 'Upload'")
        except Exception: pass
    
    if not upload_button: log(f"{prefix} UPLOAD_CONTROL_NOT_FOUND_IN_DRAWER"); return _click_upload_files_fallback(drv, tid, job_id)
    _log_target_rect(drv, upload_button, prefix, "UPLOAD_IN_DRAWER")
    if not _verify_element_ownership(drv, upload_button, prefix):
        log(f"{prefix} UPLOAD_NOT_OWNED — retrying with scroll")
        try: drv.execute_script("arguments[0].scrollIntoView({block:'center'});", upload_button); time.sleep(0.2)
            if not _verify_element_ownership(drv, upload_button, prefix): return False
        except Exception: return False
    if _safe_click_element(drv, upload_button, prefix, "UPLOAD_FILES_BUTTON"):
        log(f"{prefix} UPLOAD_CONTROL_CLICKED"); return True
    log(f"{prefix} UPLOAD_CONTROL_CLICK_FAILED"); return False


def _click_upload_files_fallback(drv, tid=0, job_id="") -> bool:
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    log(f"{prefix} UPLOAD_FALLBACK_START")
    try:
        res = drv.execute_script("""
            var btns = document.querySelectorAll('button'); var candidates = [];
            for (var i=0;i<btns.length;i++){var b=btns[i];if(!b.offsetParent||b.disabled)continue;var t=(b.textContent||'').toLowerCase();if(t.indexOf('upload files')!==-1||t.indexOf('upload from computer')!==-1||t.indexOf('upload file')!==-1)candidates.push(b);}
            return candidates.length>0?candidates[0]:null;
        """)
        if res and res.is_displayed() and res.is_enabled():
            _log_target_rect(drv, res, prefix, "UPLOAD_FALLBACK")
            if _safe_click_element(drv, res, prefix, "UPLOAD_FALLBACK_BUTTON"): return True
    except Exception: pass
    log(f"{prefix} UPLOAD_FALLBACK_FAILED"); return False


def perform_robust_upload(drv, paths, tid=0, job_id=""):
    """V11 Robust upload state machine."""
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    log(f"{prefix} FILE_INPUT_DIRECT_CHECK")
    fi = _find_file_input(drv)
    if fi: log(f"{prefix} FILE_INPUT_READY (direct)")
    else:
        log(f"{prefix} FILE_INPUT_NOT_FOUND")
        for attempt in range(1, 5):
            log(f"{prefix} UPLOAD_DRAWER_OPENING (attempt {attempt})")
            composer_root = _get_composer_root(drv, prefix)
            if not composer_root:
                log(f"{prefix} COMPOSER_ROOT_LOST — reloading")
                drv.refresh(); time.sleep(2.0); ensure_create_image_mode(drv, tid, job_id); continue
            if _detect_wrong_sidebar_menu(drv, prefix):
                log(f"{prefix} WRONG_MENU_DETECTED_ON_ATTEMPT_{attempt}")
                _press_esc(drv, prefix); time.sleep(0.5)
                composer_root = _reacquire_composer(drv, prefix)
                if not composer_root or _detect_wrong_sidebar_menu(drv, prefix): continue
            if not click_plus_button(drv, tid, job_id):
                log(f"{prefix} PLUS_CLICK_FAILED on attempt {attempt}")
                if attempt >= 4: drv.refresh(); time.sleep(2.0); ensure_create_image_mode(drv, tid, job_id); continue
                time.sleep(0.3); continue
            if not open_upload_drawer(drv, tid, job_id):
                log(f"{prefix} DRAWER_NOT_OPENED on attempt {attempt}")
                if attempt >= 4: drv.refresh(); time.sleep(2.0); ensure_create_image_mode(drv, tid, job_id); continue
                time.sleep(0.3); continue
            if not click_upload_files_in_drawer(drv, tid, job_id):
                log(f"{prefix} UPLOAD_IN_DRAWER_FAILED on attempt {attempt}")
                if attempt >= 4: drv.refresh(); time.sleep(2.0); ensure_create_image_mode(drv, tid, job_id); continue
                time.sleep(0.3); continue
            deadline = time.time() + 6.0; fi = None
            while time.time() < deadline:
                fi = _find_file_input(drv)
                if fi: log(f"{prefix} FILE_INPUT_READY (after drawer)"); break
                time.sleep(0.3)
            if fi: break
            if attempt >= 2 and click_plus_button(drv, tid, job_id):
                time.sleep(0.5); fi = _find_file_input(drv)
                if fi: log(f"{prefix} FILE_INPUT_READY (direct after plus)"); break
        if not fi:
            drv.refresh(); time.sleep(2.0); ensure_create_image_mode(drv, tid, job_id)
            fi = _find_file_input(drv)
            if not fi: raise RuntimeError("FILE_INPUT_MISSING after all upload attempts")
    try: fi.send_keys("\n".join(paths)); log(f"{prefix} UPLOAD_SENT {len(paths)} files")
    except Exception as e: raise RuntimeError(f"UPLOAD_FAILED: {e}")

'''
    code = code[:u_start] + new_upload + code[u_end:]
    print("✅ perform_robust_upload replaced")

# ============================================================================
# 4. UPDATE CALL SITES
# ============================================================================
# ensure_create_image_mode: click_plus_button(drv) -> click_plus_button(drv, tid, job_id)
code = code.replace("if click_plus_button(drv):", "if click_plus_button(drv, tid, job_id):")
# _submit_job_to_tab: _click_send_button(chrome_driver) -> _click_send_button(chrome_driver, tid, job_id)
code = code.replace("if not _click_send_button(chrome_driver):", "if not _click_send_button(chrome_driver, tid, job_id):")

# ============================================================================
# 5. UPDATE HEADER
# ============================================================================
code = code.replace("# 🚀 QUEUE WORKER v9.0", "# 🚀 QUEUE WORKER v11.0")
code = code.replace("# V9 CHANGES:", "# V11 CHANGES:\n#   • COMPOSER-SCOPED DOM targeting for ALL critical clicks (+, Upload, Send)\n#   • _get_composer_root() locates Gemini image composer first\n#   • click_plus_button() searches ONLY inside composer_root\n#   • open_upload_drawer() polls for drawer visibility (up to 5s)\n#   • click_upload_files_in_drawer() searches ONLY inside visible drawer\n#   • elementFromPoint verification before every critical click\n#   • WRONG_SIDEBAR_MENU detection + ESC recovery\n#   • ActionChains (not JS click) as primary method\n#   • Coordinate diagnostics logged\n#   • Retry: 4 attempts before page reload")

# ============================================================================
# 6. SAVE
# ============================================================================
with open(V11_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print(f"\n✅ V11 saved to {V11_PATH}")
print(f"   Total lines: {code.count(chr(10)) + 1}")
