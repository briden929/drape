def print_func():
    with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
        lines = f.readlines()
    start = -1
    for i, line in enumerate(lines):
        if line.startswith("async def poll_downloads_loop"):
            start = i
            break
    if start != -1:
        for j in range(start, start + 60):
            print(lines[j].rstrip())
print_func()
