with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(60, 70):
    print(f"L{i+1}: {repr(lines[i])}")
