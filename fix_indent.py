import os
import re

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("    \n            if dl_guid:\n                log(f'{prefix} DOWNLOAD_START_EVENT guid={dl_guid}')\n                ctx.wmr_download_guid = dl_guid", "    \n    if dl_guid:\n        log(f'{prefix} DOWNLOAD_START_EVENT guid={dl_guid}')\n        ctx.wmr_download_guid = dl_guid")

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
