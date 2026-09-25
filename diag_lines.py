with open('v14_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

for i, line in enumerate(lines):
    if any(k in line for k in ['create_chrome_driver', 'chrome_lock', 'tab_states', 'chrome_driver =']):
        print(f"Line {i+1}: {line.strip()}")
