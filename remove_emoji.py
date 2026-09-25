import sys; sys.stdout.reconfigure(encoding="utf-8")
import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Strip all characters outside basic ASCII and some common punctuation
text = re.sub(r'[^\x00-\x7F]+', '', text)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Non-ASCII removed!")
