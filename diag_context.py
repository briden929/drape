import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('v14_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

print("--- Line 754 Context ---")
print('\n'.join(lines[745:765]))

print("\n--- Line 1760 Context ---")
print('\n'.join(lines[1750:1770]))
