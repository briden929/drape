import os
import re

FINAL = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_FINAL.py"

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

# Replace _FALLBACKS dictionary to an empty dictionary or just fetch from environ directly
new_secrets_block = """_REQUIRED_SECRETS = [
    'DATABASE_URL',
    'REDIS_URL',
    'R2_ACCOUNT_ID',
    'R2_ACCESS_KEY_ID',
    'R2_SECRET_ACCESS_KEY',
    'R2_BUCKET_NAME',
    'R2_PUBLIC_URL'
]
_missing = []
for _k in _REQUIRED_SECRETS:
    if not os.environ.get(_k):
        _missing.append(_k)

if _missing:
    print(f"[FATAL ERROR] Missing required environment variables: {', '.join(_missing)}")
    sys.exit(1)
"""

# The existing block starts with _FALLBACKS = {...} and has a loop for _k, _v in _FALLBACKS.items(): if not os.environ.get(_k): os.environ[_k] = _v
pattern = r"_FALLBACKS\s*=\s*\{.*?\}.*?os\.environ\[_k\]\s*=\s*_v"
text = re.sub(pattern, new_secrets_block, text, flags=re.DOTALL)

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
print("Updated secrets block.")
