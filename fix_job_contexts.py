import os

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("job_contexts", "JOB_CONTEXTS")
text = text.replace("JOB_CONTEXTS = {}", "") # Remove the duplicate lowercase initialization since we have it near dataclasses

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
