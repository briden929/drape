with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V11_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('WmrWorkerPool(MAX_WMR_WORKERS)', 'WmrWorkerPool(CHROME_WMR_WORKERS)')
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V11_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)
