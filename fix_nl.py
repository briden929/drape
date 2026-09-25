with open('v20_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('print("' + chr(10), 'print("\\n')
text = text.replace('print("' + chr(10) + '"', 'print("\\n"')
text = text.replace('=" * 68 + "' + chr(10), '=" * 68 + "\\n')
text = text.replace('=" * 60 + "' + chr(10), '=" * 60 + "\\n')
with open('v20_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
