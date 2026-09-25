import os
import re

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

# Strip out the forbidden files_before / files_after fallback logic in both Gemini and WMR
text = re.sub(r'cur = set\(staging_dir\.iterdir\(\)\)\s*new_files = cur - files_before.*?(?=if not dl_guid)', 'pass\n                ', text, flags=re.DOTALL)
text = re.sub(r'files_before = set\(staging_dir\.iterdir\(\)\)', 'pass', text)

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
