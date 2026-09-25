import os
import re

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

# Strip out everything starting from `class GeminiWorker:`
match = re.search(r'^class GeminiWorker:', text, flags=re.MULTILINE)
if match:
    text = text[:match.start()]

# Remove old `WmrWorkerPool` from V9 AST if it's there
text = re.sub(r'class WmrWorkerPool:.*?(?=wmr_pool = WmrWorkerPool)', '', text, flags=re.DOTALL)
text = re.sub(r'wmr_pool = WmrWorkerPool\(CHROME_WMR_WORKERS\)', '', text)

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
