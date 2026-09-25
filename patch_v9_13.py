import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''            # 5. Click "Upload files" in drawer
            click_upload_files_in_drawer(chrome_driver)
            time.sleep(0.1)

            # 6. Find file input (strict — no silent continue)
            try:
                f_input = find_file_input_strict(chrome_driver, timeout=2.0)'''

replacement = '''            # 5. Click "Upload files" in drawer
            if not click_upload_files_in_drawer(chrome_driver):
                raise RuntimeError(f"{prefix} DRAWER_FAILED: Could not click Upload files in drawer")
            time.sleep(0.1)

            # 6. Find file input (strict — no silent continue)
            try:
                f_input = find_file_input_strict(chrome_driver, timeout=4.0)'''

if target in text:
    text = text.replace(target, replacement)
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched upload click logic')
else:
    print('Target not found')
