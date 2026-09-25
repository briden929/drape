with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()
import re
for m in re.finditer(r"^import (credits|db|fashion_studio)", text, flags=re.MULTILINE):
    print(m.group(0), "at line", text[:m.start()].count("\n"))
