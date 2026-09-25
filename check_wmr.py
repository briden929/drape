with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "WMR_WORKERS" in line or "WmrWorkerPool" in line:
        print(f"L{i}: {line.strip()}")
