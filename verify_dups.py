with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
print("class FirstFreeBroker:", len(re.findall(r"^class FirstFreeBroker\b", text, flags=re.MULTILINE)))
print("class JobContext:", len(re.findall(r"^class JobContext\b", text, flags=re.MULTILINE)))
