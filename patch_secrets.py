with open('v12_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
old_block_pattern = r"# ----------------------------------------------------------------------------\n# 1\. Secrets\n# ----------------------------------------------------------------------------.*?os\.environ\.setdefault\(\"REDIS_KEY_PREFIX\", \"vastralook:\"\)"

new_block = """# ----------------------------------------------------------------------------
# 1. Version Stamp & Secrets
# ----------------------------------------------------------------------------
import os

print("======================================================================")
print("WORKER_VERSION=V9.1")
print("GEMINI=T0-T3")
print("WMR=W0-W3 CHROME")
print("EDGE=DISABLED")
print("======================================================================")

_REQUIRED_SECRETS = [
    'DATABASE_URL', 'R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY',
    'R2_BUCKET_NAME', 'R2_PUBLIC_URL', 'REDIS_URL'
]

# Try to load from Colab userdata if available
try:
    from google.colab import userdata
    for _k in _REQUIRED_SECRETS:
        if not os.environ.get(_k):
            try:
                val = userdata.get(_k)
                if val: os.environ[_k] = val
            except Exception:
                pass
except ImportError:
    pass

missing = [_k for _k in _REQUIRED_SECRETS if not os.environ.get(_k)]
if missing:
    print(f"\\nWARNING: Missing required secrets: {missing}")
    print("Please configure these in Colab Secrets or os.environ.\\n")

os.environ.setdefault("REDIS_KEY_PREFIX", "vastralook:")"""

text = re.sub(old_block_pattern, new_block.replace("\\n", "\n"), text, flags=re.DOTALL)

with open('v12_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patched secrets!")
