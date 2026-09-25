import os
import re

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("ctx.gemini_download_guid = dl_guid\n\n        ctx.transition(JobState.WMR_RESOURCE_RELEASED)", "ctx.wmr_download_guid = dl_guid\n\n        ctx.transition(JobState.WMR_RESOURCE_RELEASED)")

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
