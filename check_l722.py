with open('v13_clean_ast_fixed.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(717, 727):
    print(f"L{i}: {lines[i].rstrip()}")
