with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(300, 325):
    print(lines[i].rstrip())
