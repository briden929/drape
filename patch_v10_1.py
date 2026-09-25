import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
lines = text.split('\n')

start = -1
end = -1
for i, line in enumerate(lines):
    if line.startswith('def open_upload_drawer'):
        start = i
    if line.startswith('def verify_attachment_count'):
        end = i
        break

new_helpers = '''def _expose_file_inputs(drv):
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

def perform_robust_upload(drv, paths, tid=0, job_id=""):
    """
    Robust upload state machine.
    1. Check for file input directly
    2. If not found, open drawer, find upload button, click, wait for file input
    3. Handles retries and recovery logic.
    Raises RuntimeError on failure.
    """
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    # 1. DIRECT CHECK FIRST
    log(f"{prefix} FILE_INPUT_DIRECT_CHECK")
    fi = _find_file_input(drv)
    if fi:
        log(f"{prefix} FILE_INPUT_READY (direct)")
    else:
        log(f"{prefix} FILE_INPUT_NOT_FOUND")
        
        # 2. OPEN DRAWER AND CLICK
        for attempt in range(1, 4):
            log(f"{prefix} UPLOAD_DRAWER_OPENING (attempt {attempt})")
            click_plus_button(drv)
            time.sleep(0.5)
            log(f"{prefix} UPLOAD_DRAWER_OPENED")
            
            clicked = False
            for sel in [
                "button[data-test-id='local-images-files-uploader-button']",
                "//span[contains(text(),'Upload files')]/ancestor::button",
                "//div[contains(text(),'Upload files')]/ancestor::button",
                "//span[contains(text(),'Upload from computer')]/ancestor::button",
                "//span[contains(text(),'Upload file')]/ancestor::button",
            ]:
                try:
                    by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                    for btn in drv.find_elements(by, sel):
                        if btn.is_displayed() and btn.is_enabled():
                            log(f"{prefix} UPLOAD_CONTROL_FOUND: {sel}")
                            drv.execute_script("arguments[0].click();", btn)
                            log(f"{prefix} UPLOAD_CONTROL_CLICKED")
                            clicked = True
                            break
                except Exception:
                    continue
                if clicked: break
                
            if not clicked:
                try:
                    res = drv.execute_script("""
                        var btns = document.querySelectorAll('button');
                        for (var i = 0; i < btns.length; i++) {
                            var text = btns[i].textContent.toLowerCase();
                            if (btns[i].offsetParent !== null && (text.indexOf('upload files') !== -1 || text.indexOf('upload from computer') !== -1 || text.indexOf('upload file') !== -1 || text.indexOf('choose files') !== -1 || text.indexOf('add files') !== -1)) {
                                btns[i].click(); return 'OK';
                            }
                        } return 'NO';
                    """)
                    if res == 'OK':
                        log(f"{prefix} UPLOAD_CONTROL_FOUND: JS fallback")
                        log(f"{prefix} UPLOAD_CONTROL_CLICKED")
                        clicked = True
                except Exception:
                    pass

            if clicked:
                # Wait for file input
                deadline = time.time() + 6.0
                while time.time() < deadline:
                    fi = _find_file_input(drv)
                    if fi:
                        log(f"{prefix} FILE_INPUT_READY")
                        break
                    time.sleep(0.3)
                if fi:
                    break # Success!
                    
            if attempt == 3:
                raise RuntimeError("UPLOAD_CONTROL_NOT_CLICKABLE (exhausted 3 retries)")
            
            # Retry logic
            log(f"{prefix} UPLOAD_DRAWER_FAILED — reloading page before retry")
            drv.refresh()
            time.sleep(2.0)
            ensure_create_image_mode(drv, tid, job_id)
            
    if not fi:
        raise RuntimeError("FILE_INPUT_MISSING after click")
        
    try:
        fi.send_keys("\\n".join(paths))
        log(f"{prefix} UPLOAD_SENT {len(paths)} files")
    except Exception as e:
        raise RuntimeError(f"UPLOAD_FAILED: {e}")
'''

new_lines = lines[:start] + new_helpers.split('\n') + lines[end:]
text = '\n'.join(new_lines)

# Now replace inside _submit_job_to_tab
target_submit = '''            # 4. Open upload drawer
            if not open_upload_drawer(chrome_driver, tid, job_id):
                _recover_stuck_tab(tid, "DRAWER_FAILED: Could not open upload drawer")
                return

            # 5. Click "Upload files" in drawer
            if not click_upload_files_in_drawer(chrome_driver):
                raise RuntimeError(f"{prefix} DRAWER_FAILED: Could not click Upload files in drawer")
            time.sleep(0.1)

            # 6. Find file input (strict — no silent continue)
            try:
                fi = find_file_input_strict(chrome_driver, tid, job_id)
            except FileInputMissing as e:
                _recover_stuck_tab(tid, f"FILE_INPUT_MISSING: {e}")
                return

            # 7. Upload reference files
            ref_paths = [str(Path(p).resolve()) for p in info["refs"] if p and os.path.exists(p)]
            expected_count = len(ref_paths)
            try:
                fi.send_keys("\\n".join(ref_paths))
                log(f"{prefix} UPLOAD_SENT {expected_count} files")
            except Exception as e:
                _recover_stuck_tab(tid, f"UPLOAD_FAILED: {e}")
                return'''

replacement_submit = '''            # 4-7. Upload reference files (Robust State Machine)
            ref_paths = [str(Path(p).resolve()) for p in info["refs"] if p and os.path.exists(p)]
            expected_count = len(ref_paths)
            if expected_count > 0:
                try:
                    perform_robust_upload(chrome_driver, ref_paths, tid, job_id)
                except Exception as e:
                    _recover_stuck_tab(tid, f"SUBMISSION_EXCEPTION: {e}")
                    return'''

text = text.replace(target_submit, replacement_submit)

with open('v10_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Patched upload logic')
