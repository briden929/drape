with open('v20_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = 'import sys; sys.stdout.reconfigure(encoding="utf-8")\n' + text
with open('v20_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
