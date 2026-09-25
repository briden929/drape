with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V12_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('try:\n            \n        except', 'try:\n            pass\n        except')

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V12_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)
