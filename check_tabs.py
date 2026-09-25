with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "MAX_CONCURRENT_TABS" in line or "TOTAL_JOB_TIMEOUT_S" in line:
        print(f"L{i}: {line.strip()}")
