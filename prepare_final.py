import os
import re

FINAL = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_FINAL.py"

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Fix secrets at the top
secrets_pattern = r"_HARDCODED\s*=\s*\{.*?\}"
new_secrets = """_HARDCODED = {
    'DATABASE_URL': os.environ.get('DATABASE_URL', ''),
    'R2_ACCOUNT_ID': os.environ.get('R2_ACCOUNT_ID', ''),
    'R2_ACCESS_KEY_ID': os.environ.get('R2_ACCESS_KEY_ID', ''),
    'R2_SECRET_ACCESS_KEY': os.environ.get('R2_SECRET_ACCESS_KEY', ''),
    'R2_BUCKET_NAME': os.environ.get('R2_BUCKET_NAME', 'studio-photoshoot'),
    'R2_PUBLIC_URL': os.environ.get('R2_PUBLIC_URL', ''),
    'REDIS_URL': os.environ.get('REDIS_URL', 'redis://localhost:6379'),
    'QUEUE_NAME': os.environ.get('QUEUE_NAME', 'vastralook-queue'),
}"""
text = re.sub(secrets_pattern, new_secrets, text, flags=re.DOTALL)

# 2. Slice off everything after job_queue = asyncio.Queue()
cut_marker = 'job_queue = asyncio.Queue()'
idx = text.find(cut_marker)
if idx != -1:
    text = text[:idx]
else:
    print("Could not find cut marker!")

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
