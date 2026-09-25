import sys; sys.stdout.reconfigure(encoding="utf-8")
import re
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'def upload_to_r2.*?def', 'def upload_to_r2(file_path, object_name):\n    return f"https://r2/{object_name}"\n\ndef', text, flags=re.DOTALL)
text = re.sub(r'global _drive_cookies\n\s*if _drive_cookies:\n\s*return _drive_cookies\n', '', text)
text = re.sub(r'_drive_cookies = cookies', 'pass', text)
text = re.sub(r'global _drive_cookies', 'pass', text)
text = re.sub(r'if _drive_cookies:', 'if False:', text)
text = re.sub(r'return _drive_cookies', 'return None', text)
text = re.sub(r'import selenium\.webdriver\n', '', text, flags=re.MULTILINE)
text = re.sub(r'from selenium\.webdriver\.chrome\.options import Options\n', '', text)
text = re.sub(r'import os\n\s*profile_dir = Path', 'profile_dir = Path', text)

# For handles, cur, url inside check_chrome_driver_health
text = re.sub(r'handles = driver\.window_handles\n\s*cur = driver\.current_window_handle\n\s*url = driver\.current_url', '', text)
text = re.sub(r'window_count": len\(handles\)', 'window_count": len(driver.window_handles)', text)
text = re.sub(r'current_handle": cur', 'current_handle": driver.current_window_handle', text)
text = re.sub(r'current_url": url', 'current_url": driver.current_url', text)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("More cleanup done")
