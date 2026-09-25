with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(12, 22):
    print(f"L{i+1}: {lines[i].rstrip()}")
