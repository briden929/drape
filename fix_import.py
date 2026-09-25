with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL_NEW.py", "r", encoding="utf-8") as f:
    text = f.read()

text = "from datetime import datetime\n" + text

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL_NEW.py", "w", encoding="utf-8") as f:
    f.write(text)
