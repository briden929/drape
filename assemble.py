import os

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

chunks = [
    r"chunks\01_bootstrap.py",
    r"chunks\02_dataclasses.py",
    r"chunks\03_broker.py",
    r"chunk_04.py",
    r"chunk_05.py",
    r"chunks\06_wmr.py",
    r"chunks\07_backend.py",
    r"chunks\08_entrypoint.py"
]

content = ""
for chunk in chunks:
    with open(os.path.join(ROOT, chunk), "r", encoding="utf-8") as f:
        content += f.read() + "\n\n"

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(content)
