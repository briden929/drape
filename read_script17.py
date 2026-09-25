with open('FULL_QUEUE_WORKER_V6_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for j in range(1200, 1240):
    print(f"{j}: {lines[j].strip().encode('ascii', 'ignore').decode('ascii')}")
