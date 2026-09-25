with open('FULL_QUEUE_WORKER_V4_ONE_CELL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for j in range(1462, min(1462+100, len(lines))):
    if 'def ' in lines[j] and j != 1462: break
    print(f"{j}: {lines[j].strip().encode('ascii', 'ignore').decode('ascii')}")
