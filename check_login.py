import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('v14_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')
for i, line in enumerate(lines):
    if 'verify_login' in line:
        print(f"Line {i}: {line}")
