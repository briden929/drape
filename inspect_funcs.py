import ast

with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def print_func(name):
    print(f"\n--- {name} ---")
    start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith(f"def {name}") or line.strip().startswith(f"async def {name}"):
            start = i
            break
    if start != -1:
        # print up to 50 lines of it
        for j in range(start, min(start + 50, len(lines))):
            print(lines[j].rstrip())

print_func("main")
print_func("start_worker")
