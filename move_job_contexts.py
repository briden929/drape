import os

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("DOWNLOAD_REGISTRY: Dict[str, DownloadRecord] = {}\nJOB_CONTEXTS: Dict[str, JobContext] = {}", "DOWNLOAD_REGISTRY: Dict[str, DownloadRecord] = {}")

target = "self.updated_at = time.time()"
text = text.replace(target, target + "\n\nJOB_CONTEXTS: Dict[str, JobContext] = {}")

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
