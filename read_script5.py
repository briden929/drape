with open('FULL_QUEUE_WORKER_V4_ONE_CELL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'async def poll_active_tabs' in line:
        for j in range(i, min(i+150, len(lines))):
            if 'def ' in lines[j] and j != i: break
            print(f"{j}: {lines[j].strip().encode('ascii', 'ignore').decode('ascii')}")
        break
