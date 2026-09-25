import re

with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"                # Wait for download to actually START \(\.crdownload or image file\)[\s\S]*?asyncio.create_task\(assign_jobs_to_idle_tabs\(\)\)\n                continue"

new_code = '''                # Change state to let poll_active_downloads watch for .crdownload
                # We do NOT wait here under the Chrome lock
                log(f"{prefix} WAITING_FOR_DOWNLOAD_START")
                info["state"] = "DOWNLOAD_START_WAITING"
                info["t_dl_start"] = time.time()
                info["cdp_ok"] = cdp_ok
                info["dinfo"] = dinfo
                
                # Check immediately if next job is queued
                if not job_queue.empty():
                    asyncio.create_task(assign_jobs_to_idle_tabs())
                continue'''

new_text = re.sub(pattern, new_code, text)
if text != new_text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched poll_active_tabs download start logic')
else:
    print('Regex failed')
