with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "class GeminiWorkerPool" in line or "class WmrWorkerPool" in line or "GEMINI_WORKERS" in line or "def __init__" in line and "workers:" in line:
        print(f"L{i}: {line.strip()}")
