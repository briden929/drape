import sys; sys.stdout.reconfigure(encoding="utf-8")
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding="utf-8") as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if "edge" in l.lower():
        print(f"L{i}: {l.strip()}")
