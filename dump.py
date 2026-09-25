with open('v18_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')
for i, line in enumerate(lines):
    if 'def _process_job(self, item):' in line:
        print('\n'.join(lines[i:i+150]))
        break
