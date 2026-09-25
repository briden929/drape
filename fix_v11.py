import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\PC\Downloads\FULL_QUEUE_WORKER_V11.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# Fix ALL try: single-line patterns in the upload functions
# The issue is: "try: some_code(); log(...)" on one line, then next line has if/except

# Fix pattern in click_upload_files_in_drawer:
# try: upload_button = ... \n if upload_button...: log(...)
# -> try: \n upload_button = ... \n if ...: log(...)

import re

# Pattern 1: try: <find_element>; if ...: log(...); except Exception: pass
# Replace with properly indented try/except

# Find the click_upload_files_in_drawer function and rewrite it properly
func_start = code.find("def click_upload_files_in_drawer(drv, tid=0, job_id=\"\") -> bool:")
func_end = code.find("\ndef _click_upload_files_fallback", func_start)

if func_start != -1 and func_end != -1:
    new_func = '''def click_upload_files_in_drawer(drv, tid=0, job_id="") -> bool:
    """V11: Click Upload files inside the visible drawer (drawer-scoped)."""
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    # 1. Locate the currently visible drawer
    drawer_element = None
    try:
        drawer_element = drv.execute_script("""
            var candidates = document.querySelectorAll('div[class*="drawer"], div[class*="toolbox"], div[class*="popover"], [role="menu"], [role="dialog"]');
            for (var i=0;i<candidates.length;i++){var el=candidates[i];if(el.offsetParent!==null){var r=el.getBoundingClientRect();if(r.width>100&&r.height>50){var t=el.innerText.toLowerCase();if(t.indexOf('upload')!==-1||t.indexOf('files')!==-1)return el;}}}
            var menus = document.querySelectorAll('[role="menu"]');
            for (var i=0;i<menus.length;i++){if(menus[i].offsetParent!==null)return menus[i];}
            return null;
        """)
    except Exception:
        pass
    if drawer_element: log(f"{prefix} DRAWER_ROOT_FOUND")
    else: log(f"{prefix} DRAWER_ROOT_NOT_FOUND"); return _click_upload_files_fallback(drv, tid, job_id)
    
    # 2. Search ONLY inside the drawer
    upload_button = None
    
    try:
        els = drawer_element.find_elements(By.CSS_SELECTOR, "button[data-test-id='local-images-files-uploader-button']")
        for el in els:
            if el.is_displayed() and el.is_enabled():
                upload_button = el
                log(f"{prefix} UPLOAD_CONTROL_FOUND: data-test-id")
                break
    except Exception:
        pass
    
    if not upload_button:
        try:
            upload_button = drawer_element.find_element(By.XPATH, ".//button[contains(., 'Upload files')]")
            if upload_button.is_displayed() and upload_button.is_enabled():
                log(f"{prefix} UPLOAD_CONTROL_FOUND: text 'Upload files'")
        except Exception:
            pass
    
    if not upload_button:
        try:
            upload_button = drawer_element.find_element(By.XPATH, ".//span[contains(text(),'Upload files')]/ancestor::button")
            if upload_button.is_displayed() and upload_button.is_enabled():
                log(f"{prefix} UPLOAD_CONTROL_FOUND: span 'Upload files'")
        except Exception:
            pass
    
    if not upload_button:
        try:
            upload_button = drawer_element.find_element(By.XPATH, ".//button[contains(., 'Upload from computer')]")
            if upload_button.is_displayed() and upload_button.is_enabled():
                log(f"{prefix} UPLOAD_CONTROL_FOUND: 'Upload from computer'")
        except Exception:
            pass
    
    if not upload_button:
        try:
            upload_button = drawer_element.find_element(By.CSS_SELECTOR, "button[aria-label*='Upload']")
            if upload_button.is_displayed() and upload_button.is_enabled():
                log(f"{prefix} UPLOAD_CONTROL_FOUND: aria-label 'Upload'")
        except Exception:
            pass
    
    if not upload_button:
        log(f"{prefix} UPLOAD_CONTROL_NOT_FOUND_IN_DRAWER")
        return _click_upload_files_fallback(drv, tid, job_id)
    
    # 3. Verify and click
    _log_target_rect(drv, upload_button, prefix, "UPLOAD_IN_DRAWER")
    if not _verify_element_ownership(drv, upload_button, prefix):
        log(f"{prefix} UPLOAD_NOT_OWNED — retrying with scroll")
        try:
            drv.execute_script("arguments[0].scrollIntoView({block:'center'});", upload_button)
            time.sleep(0.2)
            if not _verify_element_ownership(drv, upload_button, prefix):
                return False
        except Exception:
            return False
    if _safe_click_element(drv, upload_button, prefix, "UPLOAD_FILES_BUTTON"):
        log(f"{prefix} UPLOAD_CONTROL_CLICKED")
        return True
    log(f"{prefix} UPLOAD_CONTROL_CLICK_FAILED")
    return False


'''
    code = code[:func_start] + new_func + code[func_end:]
    print("✅ click_upload_files_in_drawer rewritten")

# Fix _verify_element_ownership one-liners
# Fix: "if not owned: log(...); return False" -> properly indented
code = code.replace(
    'if not owned:\n                log(f"{prefix} TARGET_STILL_OCCLUDED ({action_desc})")\n                return False',
    'if not owned:\n                    log(f"{prefix} TARGET_STILL_OCCLUDED ({action_desc})")\n                    return False'
)

# Fix _verify_element_ownership return blocks
code = code.replace(
    '        if not owned: log(f"{prefix} TARGET_NOT_OWNED x={rect[\'x\']:.0f} y={rect[\'y\']:.0f}"); return False',
    '        if not owned:\n            log(f"{prefix} TARGET_NOT_OWNED x={rect[\'x\']:.0f} y={rect[\'y\']:.0f}")\n            return False'
)
code = code.replace(
    '        if not owned: log(f"{prefix} TARGET_OWNERSHIP_VERIFIED x={rect[\'x\']:.0f} y={rect[\'y\']:.0f}"); return True',
    '        if not owned:\n            pass\n        else:\n            log(f"{prefix} TARGET_OWNERSHIP_VERIFIED x={rect[\'x\']:.0f} y={rect[\'y\']:.0f}")\n            return True'
)

# Fix _click_upload_files_fallback one-liners
code = code.replace(
    '            if res and res.is_displayed() and res.is_enabled():\n            _log_target_rect(drv, res, prefix, "UPLOAD_FALLBACK")\n            if _safe_click_element(drv, res, prefix, "UPLOAD_FALLBACK_BUTTON"): return True',
    '            if res and res.is_displayed() and res.is_enabled():\n                _log_target_rect(drv, res, prefix, "UPLOAD_FALLBACK")\n                if _safe_click_element(drv, res, prefix, "UPLOAD_FALLBACK_BUTTON"): return True'
)

# Fix UPLOAD_CONTROL_FOUND one-liners in click_upload_files_in_drawer (the data-test-id block)
code = code.replace(
    "                upload_button = el\n                log(f\"{prefix} UPLOAD_CONTROL_FOUND: data-test-id\")\n                break",
    "                upload_button = el\n                log(f\"{prefix} UPLOAD_CONTROL_FOUND: data-test-id\")\n                break"
)

# Fix the fallback block inside open_upload_drawer
# Check for try: single-line patterns in open_upload_drawer
# Actually let me also check _get_composer_root and _safe_click_element for issues

# Fix _safe_click_element: "log(f...); return False" on one line after if
code = code.replace(
    '            log(f"{prefix} TARGET_NOT_VISIBLE ({action_desc})"); return False',
    '            log(f"{prefix} TARGET_NOT_VISIBLE ({action_desc})")\n            return False'
)
code = code.replace(
    '            log(f"{prefix} TARGET_DISABLED ({action_desc})"); return False',
    '            log(f"{prefix} TARGET_DISABLED ({action_desc})")\n            return False'
)
code = code.replace(
    '            log(f"{prefix} TARGET_RECT_INVALID ({action_desc})"); return False',
    '            log(f"{prefix} TARGET_RECT_INVALID ({action_desc})")\n            return False'
)
code = code.replace(
    '                    if not owned: log(f"{prefix} TARGET_STILL_OCCLUDED ({action_desc})"); return False',
    '                    if not owned:\n                        log(f"{prefix} TARGET_STILL_OCCLUDED ({action_desc})")\n                        return False'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print("All fixes applied.")
