import re

with open('v11_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_sig = 'def ensure_create_image_mode(drv, tid=0, job_id=""):'
end_sig = 'def prepare_job_refs(job: dict) -> tuple:'

start_idx = text.find(start_sig)
end_idx = text.find(end_sig)

if start_idx == -1 or end_idx == -1:
    print('Could not find ensure block boundaries')
    exit(1)

new_code = '''def ensure_create_image_mode(drv, tid=0, job_id=""):
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    # Wait for Gemini UI to settle first
    deadline = time.time() + 4.0
    while time.time() < deadline:
        if is_create_image_mode(drv):
            log(f"{prefix} CREATE_IMAGE_VERIFIED")
            return True
        time.sleep(0.5)

    for attempt in range(1, 3):
        if _check_wrong_sidebar_menu(drv, prefix):
            log(f"{prefix} TARGET_REACQUIRED (menus closed)")
            
        root = _get_composer_root(drv, prefix)
        if root and _click_composer_plus(drv, prefix, root):
            time.sleep(0.5)
            
            # Use strict click for Create Image button
            try:
                drawer = drv.execute_script("""
                    var menus = document.querySelectorAll('[role="menu"], [role="dialog"], .cdk-overlay-pane, .mat-mdc-menu-panel');
                    for (var i=0; i<menus.length; i++) {
                        if (menus[i].offsetParent !== null) {
                            var text = menus[i].innerText.toLowerCase();
                            if (text.includes('create image')) return menus[i];
                        }
                    }
                    return document.body; // Fallback to entire body
                """)
                
                btns = drv.execute_script("""
                    var root = arguments[0];
                    var cands = Array.from(root.querySelectorAll('button, [role="menuitemcheckbox"]'));
                    var res = [];
                    for (var i=0; i<cands.length; i++) {
                        var b = cands[i];
                        if (b.offsetParent === null) continue;
                        if ((b.innerText || '').toLowerCase().includes('create image')) {
                            res.push(b);
                        } else if (b.querySelector('mat-icon[data-mat-icon-name="image_create"], mat-icon[fonticon="image_create"]')) {
                            res.push(b);
                        }
                    }
                    return res;
                """, drawer)
                
                for btn in btns:
                    if btn.is_displayed():
                        if _exact_click(drv, btn, prefix, "CREATE_IMAGE_MODE"):
                            time.sleep(1.0)
                            break
            except Exception as e:
                log(f"{prefix} CREATE_IMAGE_MODE_CLICK_ERROR: {e}")
            
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if is_create_image_mode(drv):
                log(f"{prefix} CREATE_IMAGE_VERIFIED")
                return True
            time.sleep(0.5)
            
        drv.refresh()
        time.sleep(3.0)
        
    return False

'''

text = text[:start_idx] + new_code + text[end_idx:]

with open('v11_work.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Patched ensure_create_image_mode!')
