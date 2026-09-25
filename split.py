import sys; sys.stdout.reconfigure(encoding="utf-8")
with open('final_build.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

with open('bottom.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines[1429:]))
