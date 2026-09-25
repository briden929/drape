with open("FULL_QUEUE_WORKER_FINAL_V16_PREP.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(2795, 2810):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
