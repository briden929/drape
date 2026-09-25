import os
import re

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

# Completely remove the filesystem fallback loops.
# Let's replace the whole block starting from `dl_confirmed_fs = False` down to `if not dl_guid:`
# We will use a regex that captures everything from `dl_confirmed_fs = False` to `ctx.gemini_download_guid = dl_guid or ...`

def replacer(match):
    return f"""
            if dl_guid:
                log(f'{{prefix}} DOWNLOAD_START_EVENT guid={{dl_guid}}')
                ctx.gemini_download_guid = dl_guid
"""

# Gemini replacement
text = re.sub(r'dl_confirmed_fs = False.*?ctx\.gemini_download_guid = dl_guid or [^\n]*', replacer, text, flags=re.DOTALL)
# WMR replacement
text = re.sub(r'dl_confirmed_fs = False.*?ctx\.wmr_download_guid = dl_guid or [^\n]*', replacer, text, flags=re.DOTALL)

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
