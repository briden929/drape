import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"def verify_attachment_count\(drv, expected: int, tid=0, job_id=\"\"\) -> tuple:[\s\S]*?log\(f\"\{prefix\} ATTACHMENT_TIMEOUT expected \{expected\}, actual \{chip_count\}\"\)\n    return False, chip_count\n"
new_func = '''def verify_attachment_count(drv, expected: int, tid=0, job_id="") -> tuple:
    """
    Polls until attachment count == expected. Uses canonical identities to avoid double counting wrappers.
    Returns (verified: bool, actual_count: int).
    """
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    if expected == 0:
        return True, 0
        
    deadline = time.time() + 15.0
    actual_count = 0
    while time.time() < deadline:
        identities = set()
        
        # 1. Look for canonical image src or data-test-id
        try:
            imgs = drv.find_elements(By.CSS_SELECTOR, "img[data-test-id='uploaded-img'], gem-media-attachment img")
            for img in imgs:
                src = img.get_attribute("src")
                if src: identities.add(src)
        except Exception: pass
        
        # 2. Look for close buttons as a proxy (1 button = 1 attachment)
        if not identities:
            try:
                btns = drv.find_elements(By.CSS_SELECTOR, "button[aria-label='close attachment']")
                for idx, btn in enumerate(btns):
                    if btn.is_displayed():
                        identities.add(f"close-btn-{idx}")
            except Exception: pass
            
        # 3. Look for gem-media-attachment custom elements
        if not identities:
            try:
                els = drv.find_elements(By.CSS_SELECTOR, "gem-media-attachment")
                for idx, el in enumerate(els):
                    if el.is_displayed():
                        identities.add(f"attachment-{idx}")
            except Exception: pass
            
        actual_count = len(identities)
        if actual_count == expected:
            log(f"{prefix} ATTACHMENT_IDENTITIES expected={expected} actual={actual_count}")
            log(f"{prefix} ATTACHMENTS_VERIFIED")
            return True, actual_count
            
        time.sleep(0.5)

    log(f"{prefix} ATTACHMENT_TIMEOUT expected {expected}, actual {actual_count}")
    return False, actual_count
'''

new_text = re.sub(pattern, new_func, text)
if text != new_text:
    with open('v10_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched verify_attachment_count')
else:
    print('Regex failed')
