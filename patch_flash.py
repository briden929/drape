with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

flash_code = '''def ensure_flash_mode(drv, tid: int, job_id: str):
    """
    1. Wait for model control to be ready.
    2. Check if currently selected model is already Flash.
    3. If not, open picker and select Flash.
    """
    prefix = f"[T{tid}][{job_id}]"
    
    js_check = """
    var btn = document.querySelector('.model-name-text');
    if (!btn) return 'NOT_FOUND';
    var text = (btn.textContent || '').toLowerCase();
    if (text.indexOf('flash') !== -1) return 'ALREADY_FLASH';
    return 'NEED_CHANGE';
    """
    
    log(f"{prefix} MODEL_CONTROL_READY")
    
    # Wait for model name text to exist
    for _ in range(15):
        status = safe_execute_script(drv, js_check)
        if status in ['ALREADY_FLASH', 'NEED_CHANGE']:
            break
        time.sleep(0.5)
        
    status = safe_execute_script(drv, js_check)
    if status == 'ALREADY_FLASH':
        log(f"{prefix} FLASH_ALREADY_ACTIVE")
        return
        
    log(f"{prefix} CURRENT_MODEL_READ (Not Flash)")
    
    # Open Picker
    try:
        picker = drv.find_element(By.CSS_SELECTOR, '.model-name-text')
        ActionChains(drv).move_to_element(picker).click().perform()
        log(f"{prefix} FLASH_PICKER_OPEN")
        time.sleep(0.5)
    except Exception as e:
        raise Exception(f"Could not open model picker: {e}")
        
    # Select Flash
    js_select = """
    var items = document.querySelectorAll('mat-option, [role="option"], .menu-item');
    for (var i=0; i<items.length; i++) {
        if ((items[i].textContent||'').toLowerCase().indexOf('flash') !== -1) {
            items[i].click();
            return true;
        }
    }
    return false;
    """
    clicked = safe_execute_script(drv, js_select)
    if not clicked:
        raise Exception("Flash option not found in picker")
        
    log(f"{prefix} FLASH_SELECTED")
    time.sleep(1.0)
    
    # Verify
    if safe_execute_script(drv, js_check) == 'ALREADY_FLASH':
        log(f"{prefix} FLASH_VERIFIED")
    else:
        raise Exception("Verification failed after selecting Flash")
'''

text = re.sub(r'def ensure_flash_mode\(.*?def is_create_image_mode', flash_code + '\n\ndef is_create_image_mode', text, flags=re.DOTALL)

with open('v13_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Flash patched")
