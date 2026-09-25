with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
m = re.finditer(r'from bullmq import .*', text)
for x in m:
    print(x.group(0))
