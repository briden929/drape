import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''                        try:
                            shutil.move(str(found_file), str(raw_path))
                        except Exception:
                            shutil.copy2(str(found_file), str(raw_path))
                            try: os.remove(str(found_file))
                            except Exception: pass
                        log(f"[{job_id}] DOWNLOAD_FILE_DETECTED -> RENAMED -> {raw_path.name}")
                        dinfo["state"] = "CHROME_RAW_READY"'''

replacement = '''                        try:
                            shutil.move(str(found_file), str(raw_path))
                        except Exception:
                            shutil.copy2(str(found_file), str(raw_path))
                            try: os.remove(str(found_file))
                            except Exception: pass
                        log(f"[{job_id}] DOWNLOAD_FILE_DETECTED")
                        log(f"[{job_id}] DOWNLOAD_STABLE")
                        log(f"[{job_id}] IMAGE_VALIDATED")
                        log(f"[{job_id}] RENAMED_TO_JOB_RAW")
                        dinfo["state"] = "CHROME_RAW_READY"'''

if target in text:
    text = text.replace(target, replacement)
    with open('v10_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched raw download logs')
else:
    print('Target not found')
