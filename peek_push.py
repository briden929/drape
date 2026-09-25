with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
m = re.search(r'def push_generation.*?def ', text, flags=re.DOTALL)
if m: print(m.group(0))
