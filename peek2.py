with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(1993, 2046):
    if i < len(lines):
        print(f"{i}: {lines[i].rstrip()}")
