with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
m = re.search(r'def push_generation.*?def ', text, flags=re.DOTALL)
if m:
    with open("push_gen_output.txt", "w", encoding="utf-8") as out:
        out.write(m.group(0))
