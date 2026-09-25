with open('v13_modified.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "close()" in line and "driver" in line.lower() or "drv.close" in line:
        print(f"L{i}: {line.strip()}")
