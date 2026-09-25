with open('FULL_QUEUE_WORKER_V4_ONE_CELL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'def _wait' in line or 'def _poll' in line or 'def wait' in line:
        print(f"{i}: {line.strip()}")
