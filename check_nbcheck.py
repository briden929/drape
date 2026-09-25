# nb_check_image is called with 2 args (drv, prefix) in one place but defined with 3
# Let us check exactly
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if 'nb_check_image' in line:
        print(f"L{i}: {line.rstrip()}")
