with open('FULL_QUEUE_WORKER_V6_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'STEP 7:' in line:
        for j in range(i, min(i+50, len(lines))):
            print(f"{j}: {lines[j].strip().encode('ascii', 'ignore').decode('ascii')}")
        break
