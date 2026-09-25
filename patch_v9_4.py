import re

with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"def ensure_create_image_mode\(drv, tid=0, job_id=\"\"\):[\s\S]*?raise RuntimeError\(f\"{prefix} Failed to activate Create image mode\"\)"
new_func = '''def ensure_create_image_mode(drv, tid=0, job_id=""):
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    # Wait for Gemini UI to settle first
    deadline = time.time() + 4.0
    while time.time() < deadline:
        if is_create_image_mode(drv):
            log(f"{prefix} CREATE_IMAGE_VERIFIED")
            return True
        time.sleep(0.5)

    for attempt in range(1, 3):
        if click_plus_button(drv):
            time.sleep(0.5)
            try:
                btns = drv.find_elements(By.CSS_SELECTOR,
                    "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button")
                for btn in btns:
                    if btn.is_displayed() and "create image" in btn.text.lower():
                        drv.execute_script("arguments[0].click();", btn)
                        time.sleep(1.0)
                        break
                else:
                    for icon in drv.find_elements(By.CSS_SELECTOR,
                            "mat-icon[data-mat-icon-name='image_create'], mat-icon[fonticon='image_create']"):
                        if icon.is_displayed():
                            btn = drv.execute_script(
                                "var e=arguments[0];while(e&&e.tagName!=='BUTTON')e=e.parentElement;return e;", icon)
                            if btn and btn.is_displayed():
                                drv.execute_script("arguments[0].click();", btn)
                                time.sleep(1.0)
                                break
            except Exception: pass
            
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if is_create_image_mode(drv):
                log(f"{prefix} CREATE_IMAGE_VERIFIED")
                return True
            time.sleep(0.5)

    raise RuntimeError(f"{prefix} Failed to activate Create image mode")'''

new_text = re.sub(pattern, new_func, text)
if text != new_text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched ensure_create_image_mode')
else:
    print('Regex failed to match ensure_create_image_mode')
