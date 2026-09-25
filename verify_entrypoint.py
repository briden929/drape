# Verify the fix is correct - check entrypoint patterns
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    source = f.read()
    lines = source.split("\n")

print("=== Entrypoint scan after fix ===")
kws = ["asyncio.run", "create_task", "run_worker", "is_running_in_notebook", 
       "start_in_current_environment", "worker_main_task", "_worker_started",
       "raise RuntimeError", "Use: await main"]
for i, line in enumerate(lines, 1):
    for kw in kws:
        if kw in line:
            print(f"L{i}: {line.strip()[:90]}")
            break

print("\n=== Last 60 lines ===")
for i, line in enumerate(lines[-60:], len(lines)-60+1):
    print(f"L{i}: {line}")
