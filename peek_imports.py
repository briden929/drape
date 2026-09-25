with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find("from bullmq import Worker")
if idx != -1:
    print(text[idx:idx+2000])
