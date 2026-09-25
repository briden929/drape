import os

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("pass if staging_dir.exists() else set()", "files_before = set()")

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
