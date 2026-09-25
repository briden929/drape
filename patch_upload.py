import re

with open('v11_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_sig = 'def _expose_file_inputs(drv):'
end_sig = 'def verify_attachment_count(drv, expected: int, tid=0, job_id="") -> tuple:'

start_idx = text.find(start_sig)
end_idx = text.find(end_sig)

if start_idx == -1 or end_idx == -1:
    print('Could not find block boundaries')
    exit(1)

new_code = '''def _expose_file_inputs(drv):
    try:
        drv.execute_script("""
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                el.removeAttribute('hidden'); el.removeAttribute('disabled');
            });
        """)
    except Exception:
        pass

def _find_file_input(drv):
    _expose_file_inputs(drv)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def _get_composer_root(drv, prefix):
    """
    Locates the main Gemini image composer root container.
    """
    try:
        res = drv.execute_script("""
            var ed = document.querySelector('div.ql-editor[data-placeholder*="Describe"], div.ql-editor[data-placeholder*="image"]');
            if (!ed) ed = document.querySelector('div[contenteditable="true"]');
            if (!ed) return null;
            return ed.closest('user-input') || ed.closest('.input-area-container') || ed.parentElement.parentElement.parentElement;
        """)
        if res:
            log(f"{prefix} COMPOSER_ROOT_FOUND")
            return res
    except Exception:
        pass
    log(f"{prefix} COMPOSER_ROOT_NOT_FOUND")
    return None

def _check_wrong_sidebar_menu(drv, prefix):
    try:
        res = drv.execute_script("""
            var text = document.body.innerText.toLowerCase();
            return (text.includes('share conversation') && text.includes('pin') && text.includes('rename') && text.includes('delete'));
        """)
        if res:
            log(f"{prefix} WRONG_SIDEBAR_MENU_OPEN")
            ActionChains(drv).send_keys(Keys.ESCAPE).perform()
            log(f"{prefix} ESC_SENT")
            time.sleep(0.5)
            return True
    except Exception:
        pass
    return False

def _exact_click(drv, element, prefix, label):
    """
    Scrolls, validates elementFromPoint, and clicks safely.
    """
    try:
        drv.execute_script("arguments[0].scrollIntoView({block:'center', behavior:'instant'});", element)
        time.sleep(0.15)
        
        rect = drv.execute_script("""
            var r = arguments[0].getBoundingClientRect();
            return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
        """, element)
        
        if rect['w'] == 0 or rect['h'] == 0:
            return False
            
        cx = rect['x'] + (rect['w'] / 2)
        cy = rect['y'] + (rect['h'] / 2)
        
        log(f"{prefix} {label}_RECT x={cx} y={cy} w={rect['w']} h={rect['h']}")
        
        owns = drv.execute_script("""
            var el = arguments[0];
            var topEl = document.elementFromPoint(arguments[1], arguments[2]);
            if (!topEl) return false;
            if (topEl === el || el.contains(topEl) || topEl.contains(el)) return true;
            return false;
        """, element, cx, cy)
        
        if not owns:
            log(f"{prefix} TARGET_OCCLUDED_OR_MISSING at {cx},{cy}")
            return False
            
        # Actual click
        try:
            ActionChains(drv).move_to_element(element).click().perform()
            log(f"{prefix} {label}_CLICKED (Action)")
            return True
        except Exception:
            try:
                element.click()
                log(f"{prefix} {label}_CLICKED (Native)")
                return True
            except Exception:
                drv.execute_script("arguments[0].click();", element)
                log(f"{prefix} {label}_CLICKED (JS)")
                return True
                
    except Exception as e:
        log(f"{prefix} EXACT_CLICK_ERROR: {e}")
        return False

def _click_composer_plus(drv, prefix, composer_root):
    try:
        btns = drv.execute_script("""
            var root = arguments[0];
            var cands = Array.from(root.querySelectorAll('button'));
            var res = [];
            for (var i=0; i<cands.length; i++) {
                var b = cands[i];
                if (b.offsetParent === null) continue;
                var aria = (b.getAttribute('aria-label') || '').toLowerCase();
                var jslog = (b.getAttribute('jslog') || '').toLowerCase();
                if (aria.includes('upload and tools') || aria.includes('upload') || jslog.includes('300142')) {
                    res.push(b);
                } else if (b.querySelector('mat-icon[fonticon="plus"], mat-icon[data-mat-icon-name="plus"]')) {
                    res.push(b);
                }
            }
            return res;
        """, composer_root)
        
        for btn in btns:
            if btn.is_displayed() and btn.is_enabled():
                log(f"{prefix} COMPOSER_PLUS_FOUND")
                if _exact_click(drv, btn, prefix, "COMPOSER_PLUS"):
                    return True
    except Exception:
        pass
    log(f"{prefix} COMPOSER_PLUS_NOT_FOUND")
    return False

def _click_drawer_upload_files(drv, prefix):
    try:
        drawer = drv.execute_script("""
            var menus = document.querySelectorAll('[role="menu"], [role="dialog"], .cdk-overlay-pane, .mat-mdc-menu-panel');
            for (var i=0; i<menus.length; i++) {
                if (menus[i].offsetParent !== null) {
                    var text = menus[i].innerText.toLowerCase();
                    if (text.includes('upload files') || text.includes('upload from computer') || text.includes('create image')) {
                        return menus[i];
                    }
                }
            }
            return null;
        """)
        if not drawer:
            log(f"{prefix} DRAWER_ROOT_NOT_FOUND")
            return False
            
        log(f"{prefix} DRAWER_ROOT_FOUND")
        
        btns = drv.execute_script("""
            var root = arguments[0];
            var cands = Array.from(root.querySelectorAll('button, [role="menuitem"]'));
            var res = [];
            for (var i=0; i<cands.length; i++) {
                var b = cands[i];
                if (b.offsetParent === null) continue;
                var testId = b.getAttribute('data-test-id') || '';
                var text = b.innerText.toLowerCase();
                var aria = (b.getAttribute('aria-label') || '').toLowerCase();
                if (testId === 'local-images-files-uploader-button' || text.includes('upload files') || text.includes('upload from computer') || aria.includes('upload')) {
                    res.push(b);
                }
            }
            return res;
        """, drawer)
        
        for btn in btns:
            if btn.is_displayed():
                log(f"{prefix} UPLOAD_CONTROL_FOUND")
                if _exact_click(drv, btn, prefix, "UPLOAD_CONTROL"):
                    return True
    except Exception:
        pass
    return False

def perform_robust_upload(drv, paths, tid=0, job_id=""):
    """
    State machine for strictly scoped DOM upload.
    """
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    # 1. DIRECT CHECK
    log(f"{prefix} FILE_INPUT_DIRECT_CHECK")
    fi = _find_file_input(drv)
    if fi:
        log(f"{prefix} FILE_INPUT_READY (direct)")
        try:
            fi.send_keys("\\n".join(paths))
            log(f"{prefix} UPLOAD_SENT {len(paths)} files")
            return
        except Exception as e:
            raise RuntimeError(f"UPLOAD_FAILED: {e}")
            
    log(f"{prefix} FILE_INPUT_NOT_FOUND")
    
    # 2. OPEN DRAWER AND CLICK
    for attempt in range(1, 4):
        log(f"{prefix} UPLOAD_DRAWER_OPENING (attempt {attempt})")
        
        if _check_wrong_sidebar_menu(drv, prefix):
            log(f"{prefix} TARGET_REACQUIRED (menus closed)")
            
        root = _get_composer_root(drv, prefix)
        if not root:
            if attempt == 3:
                raise RuntimeError("COMPOSER_ROOT_MISSING")
            drv.refresh()
            time.sleep(2.0)
            ensure_create_image_mode(drv, tid, job_id)
            continue
            
        if not _click_composer_plus(drv, prefix, root):
            if attempt == 3:
                raise RuntimeError("COMPOSER_PLUS_CLICK_FAILED")
            continue
            
        # Wait for drawer visible
        drawer_opened = False
        for _ in range(25):
            if _check_wrong_sidebar_menu(drv, prefix):
                break # need to retry outside
            
            # We can just attempt to click the upload files since it finds the drawer root inside
            if _click_drawer_upload_files(drv, prefix):
                drawer_opened = True
                break
            time.sleep(0.2)
            
        if drawer_opened:
            # Wait for file input
            deadline = time.time() + 6.0
            while time.time() < deadline:
                fi = _find_file_input(drv)
                if fi:
                    log(f"{prefix} FILE_INPUT_READY")
                    break
                time.sleep(0.3)
                
            if fi:
                try:
                    fi.send_keys("\\n".join(paths))
                    log(f"{prefix} UPLOAD_SENT {len(paths)} files")
                    return
                except Exception as e:
                    raise RuntimeError(f"UPLOAD_FAILED: {e}")
                    
        # Retry logic
        log(f"{prefix} UPLOAD_DRAWER_FAILED — reloading page before retry")
        drv.refresh()
        time.sleep(2.0)
        ensure_create_image_mode(drv, tid, job_id)
        
    raise RuntimeError("FILE_INPUT_MISSING after 3 attempts")

'''

text = text[:start_idx] + new_code + text[end_idx:]

with open('v11_work.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Patched upload block!')
