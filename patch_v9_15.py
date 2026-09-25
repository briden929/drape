import re

with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"def find_file_input_strict\(drv, tid=0, job_id=\"\"\):[\s\S]*?raise RuntimeError\(f\"{prefix} INPUT_MISSING: file input type=file not found in DOM\"\)"
new_func = '''def find_file_input_strict(drv, tid=0, job_id=""):
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    deadline = time.time() + 4.0
    while time.time() < deadline:
        try:
            drv.execute_script("""
                document.querySelectorAll('input[type="file"]').forEach(i => {
                    i.style.display = 'block';
                    i.style.visibility = 'visible';
                    i.style.opacity = '1';
                    i.style.width = '1px';
                    i.style.height = '1px';
                    i.removeAttribute('hidden');
                });
            """)
        except Exception:
            pass

        time.sleep(0.3)
        try:
            inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
            if inputs:
                return inputs[-1]
        except Exception:
            pass
            
    raise RuntimeError(f"{prefix} INPUT_MISSING: file input type=file not found in DOM after 4s")'''

new_text = re.sub(pattern, new_func, text)
if text != new_text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched find_file_input_strict')
else:
    print('Regex failed')
