with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(2035, 2048):
    if i < len(lines):
        print(f"{i}: {lines[i].rstrip()}")
