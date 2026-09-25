import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
    if 'WORKER_VERSION' in text:
        idx = text.find('WORKER_VERSION')
        print(text[idx-50:idx+200])
