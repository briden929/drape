with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i in range(790, 820):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
