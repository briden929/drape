with open('FULL_QUEUE_WORKER_V5_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for j in range(2646, 2670):
    print(f"{j}: {lines[j].strip().encode('ascii', 'ignore').decode('ascii')}")
