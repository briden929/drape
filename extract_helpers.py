import re

with open('FULL_QUEUE_WORKER_V10_FINAL.py', 'r', encoding='utf-8') as f:
    v10 = f.read()

m = re.search(r'def ensure_flash_mode.*?class WmrWorker', v10, re.DOTALL)
if m:
    with open('v13_helpers.py', 'w', encoding='utf-8') as f:
        f.write(m.group(0).replace('class WmrWorker', ''))
    print("Extracted!")
else:
    print("Not found with regex")
