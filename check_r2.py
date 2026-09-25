# Check upload_to_r2 - line 1831 shows a fake stub!
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", 'r', encoding='utf-8') as f:
    lines = f.readlines()
    
for i, line in enumerate(lines, 1):
    if 'upload_to_r2' in line:
        print(f"L{i}: {line.rstrip()}")
