with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
if 'import queue' in text:
    print("Has queue")
else:
    print("Does NOT have queue")
