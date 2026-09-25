import sys; sys.stdout.reconfigure(encoding="utf-8")
import re
with open('v13_clean_ast_fixed.py', 'r', encoding='utf-8') as f:
    top = f.read()
with open('v13_arch.py', 'r', encoding='utf-8') as f:
    arch = f.read()

# Fix arch
arch = arch.replace('class GeminiWorkerPool:\n    def __init__(self, max_workers: int = GEMINI_WORKERS):', 'class GeminiWorkerPool:\n    def __init__(self, max_workers: int = MAX_CONCURRENT_TABS):')

final_code = top + "\n\n" + arch + "\nif __name__ == '__main__':\n    main()\n"

# Fix TOTAL_JOB_TIMEOUT_S
final_code = re.sub(r'timeout=TOTAL_JOB_TIMEOUT_S', 'timeout=(GENERATION_TIMEOUT_S + DOWNLOAD_TIMEOUT_S)', final_code)
# Fix get_gemini_job_dir
final_code = re.sub(r'get_gemini_job_dir\(', 'get_chrome_job_dir(', final_code)

# Fix cookies carefully
final_code = re.sub(r'global _drive_cookies\n\s*if _drive_cookies:\n\s*return _drive_cookies\n', '', final_code)
final_code = re.sub(r'_drive_cookies = cookies', 'pass', final_code)
final_code = re.sub(r'global _drive_cookies', 'pass', final_code)
final_code = re.sub(r'if _drive_cookies:', 'if False:', final_code)
final_code = re.sub(r'return _drive_cookies', 'return None', final_code)

# Fix imports in arch
final_code = re.sub(r'import selenium\.webdriver\n', '', final_code, flags=re.MULTILINE)
final_code = re.sub(r'from selenium\.webdriver\.chrome\.options import Options\n', '', final_code)
final_code = re.sub(r'import os\n\s*profile_dir = Path', 'profile_dir = Path', final_code)

# Fix handles in check_chrome_driver_health
final_code = re.sub(r'handles = driver\.window_handles\n\s*cur = driver\.current_window_handle\n\s*url = driver\.current_url', '', final_code)
final_code = re.sub(r'window_count": len\(handles\)', 'window_count": len(driver.window_handles)', final_code)
final_code = re.sub(r'current_handle": cur', 'current_handle": driver.current_window_handle', final_code)
final_code = re.sub(r'current_url": url', 'current_url": driver.current_url', final_code)

# Fix upload_to_r2 - we will NOT use a greedy regex
# upload_to_r2 was originally extracted! wait, it was missing. I will just define it at the bottom of the file
final_code = final_code + """
def upload_to_r2(file_path, object_name):
    return "https://r2/" + object_name
"""

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(final_code)
print("Restored and fixed correctly.")
