import re

with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"def find_file_input_strict\(drv, tid=0, job_id=\"\"\):[\s\S]*?raise FileInputMissing\(f\"Tab T\{tid\}: file input not found after Create Image mode was verified\"\)"
new_func = '''def find_file_input_strict(drv, tid=0, job_id=""):
    """
    Finds the file input element. Raises FileInputMissing if not found.
    Never silently continues.
    """
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    deadline = time.time() + 4.0
    while time.time() < deadline:
        try:
            drv.execute_script("""
                document.querySelectorAll('input[type="file"]').forEach(function(el){
                    el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                    el.removeAttribute('hidden'); el.removeAttribute('disabled');
                });
            """)
        except Exception:
            pass
            
        inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if inputs:
            return inputs[0]
            
        time.sleep(0.3)
        
    raise FileInputMissing(f"Tab T{tid}: file input not found after Create Image mode was verified (4s wait)")'''

new_text = re.sub(pattern, new_func, text)
if text != new_text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched find_file_input_strict')
else:
    print('Regex failed')
