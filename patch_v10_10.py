import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''            'concurrency': 8'''

replacement = '''            'concurrency': MAX_CONCURRENT_TABS'''

if target in text:
    text = text.replace(target, replacement)
    with open('v10_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched concurrency')
else:
    print('Target not found')
