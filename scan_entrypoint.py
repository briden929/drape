# Scan for all asyncio.run / create_task / main() bare calls in V14
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

keywords = ["asyncio.run", "create_task", "ensure_future", "run_until_complete",
            "main()", "run_worker", "is_running_in_notebook", "nest_asyncio",
            "worker_main_task", "start_in_current_environment"]

print("=== Asyncio/entrypoint scan ===")
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    for kw in keywords:
        if kw in stripped:
            print(f"L{i}: {stripped[:90]}")
            break
