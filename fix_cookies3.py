import sys; sys.stdout.reconfigure(encoding="utf-8")
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace("COOKIES_FILE = _drive_cookies if _drive_cookies.parent.parent.exists() else STATE_DIR / 'cookies.pkl'", "COOKIES_FILE = STATE_DIR / 'cookies.pkl'")

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("COOKIES_FILE fixed.")
