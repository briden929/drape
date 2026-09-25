with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('WORKER_VERSION=V9.1', 'WORKER_VERSION=V10.0')
text = text.replace('GEMINI=T0-T3', 'GEMINI=T0-T3 INDEPENDENT')
text = text.replace('WMR=W0-W3 CHROME', 'WMR=W0-W3 CHROME GLOBAL-Q')

with open('v13_work.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Version updated")
