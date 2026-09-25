import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target1 = '''    try:
        async with chrome_lock:
            chrome_driver.switch_to.window(info["handle"])

            # 1. Open verified new Gemini chat'''

replacement1 = '''    try:
        async with chrome_lock:
            chrome_driver.switch_to.window(info["handle"])
            
            # Setup isolated download directory for this job early
            chrome_job_dir, incoming_dir = get_chrome_job_dir(tid, job_id)
            set_tab_download_dir(chrome_driver, str(incoming_dir))

            # 1. Open verified new Gemini chat'''

target2 = '''                chrome_job_dir, incoming_dir = get_chrome_job_dir(tid, job_id)
                raw_path = chrome_job_dir / f"{job_id}_raw.png"
                files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()

                # Set Chrome download directory to job's private incoming dir
                set_tab_download_dir(chrome_driver, str(incoming_dir))

                # PRIMARY: hover-click download (browser native)'''

replacement2 = '''                chrome_job_dir, incoming_dir = get_chrome_job_dir(tid, job_id)
                raw_path = chrome_job_dir / f"{job_id}_raw.png"
                files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()

                # PRIMARY: hover-click download (browser native)'''

if target1 in text and target2 in text:
    text = text.replace(target1, replacement1)
    text = text.replace(target2, replacement2)
    with open('v10_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched early download dir')
else:
    print('Target not found')
