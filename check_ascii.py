with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'rb') as f:
    text = f.read()
if any(c > 127 for c in text):
    print("Non-ASCII bytes found!")
else:
    print("ALL ASCII")
