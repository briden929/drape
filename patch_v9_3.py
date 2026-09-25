import re

with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"def is_create_image_mode\(drv\):[\s\S]*?return False\n"
new_func = '''def is_create_image_mode(drv):
    try:
        editors = drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder*='Describe'], div.ql-editor[data-placeholder*='image']")
        if any(e.is_displayed() for e in editors):
            return True
            
        signals = [
            "mat-icon[data-mat-icon-name='image_create']",
            "mat-icon[fonticon='image_create']",
            "button[aria-label*='Aspect ratio']",
            "//span[contains(text(), 'Aspect ratio')]",
            "//h1[contains(text(), 'Create images')]",
            "//button[contains(., 'Images')]",
        ]
        for sig in signals:
            by = By.XPATH if sig.startswith("//") else By.CSS_SELECTOR
            for el in drv.find_elements(by, sig):
                if el.is_displayed():
                    return True
        return False
    except Exception:
        return False
'''

new_text = re.sub(pattern, new_func, text)
if text != new_text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched is_create_image_mode')
else:
    print('Regex failed to match is_create_image_mode')
