import sys; sys.stdout.reconfigure(encoding="utf-8")
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'rb') as f:
    b = f.read()

try:
    s = b.decode("utf-8")
    mojibake = ['\xf0\x9f', '\xe2\x9c', '\xe2\x9a', '\xc2', '\xef\xbf\xbd']
    found = []
    for m in mojibake:
        if m in s:
            found.append(m)
    if found:
        print(f"MOJIBAKE FOUND: {found}")
    else:
        print("UTF8/MOJIBAKE PASS")
except Exception as e:
    print(f"UTF8 ERROR: {e}")
