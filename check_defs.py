with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines[2048:]):
    if line.startswith("def ") or line.startswith("async def ") or line.startswith("class "):
        print(f"{i+2048}: {line.rstrip()}")
