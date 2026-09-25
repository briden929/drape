with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
lines = text.split('\n')
for i, line in enumerate(lines):
    if 'async def poll_active_tabs():' in line:
        print("poll_active_tabs start at", i)
    if 'def ensure_flash_mode(' in line:
        print("ensure_flash_mode start at", i)
    if 'async def _submit_job_to_tab(' in line:
        print("_submit_job_to_tab start at", i)
    if 'def is_create_image_mode(' in line:
        print("is_create_image_mode start at", i)
