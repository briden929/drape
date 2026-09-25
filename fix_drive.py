import sys; sys.stdout.reconfigure(encoding="utf-8")
import re
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('global _drive_cookies\n', '')
text = text.replace('if _drive_cookies:', 'if False:')
text = text.replace('return _drive_cookies', 'return None')
text = text.replace('import selenium.webdriver\n', '')
text = re.sub(r'^import asyncio\n', '', text, count=1, flags=re.MULTILINE)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Drive cookies fixed.")
