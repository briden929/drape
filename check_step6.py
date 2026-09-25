with open('v13_clean_top.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "STEP 6" in line:
        print(f"L{i}: {line.strip().encode('ascii', 'ignore').decode('ascii')}")
