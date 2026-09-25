with open('v17_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('=" * 68 + "' + chr(10), '=" * 68 + "\\n')

with open('v17_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
