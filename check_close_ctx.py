with open('v13_modified.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(2058, 2068):
    print(f"L{i}: {lines[i].rstrip()}")
print("---")
for i in range(2174, 2184):
    print(f"L{i}: {lines[i].rstrip()}")
