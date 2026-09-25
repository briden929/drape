with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
with open("orchestration_current.py", "w", encoding="utf-8") as f:
    f.writelines(lines[2050:])
