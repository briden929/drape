import re, sys

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

with open(r"C:\Users\PC\.gemini\antigravity\scratch\new_login.py", "r", encoding="utf-8") as f:
    new_login_code = f.read()

with open(r"C:\Users\PC\.gemini\antigravity\scratch\new_startup.py", "r", encoding="utf-8") as f:
    new_startup_code = f.read()

# 1. Login replace
match_login = re.search(r'(def is_logged_in_method_1_profile_avatar.*?def gemini_activity\(driver\):\n(?:    .*\n)*)', text, re.DOTALL)
if match_login:
    text = text[:match_login.start()] + new_login_code + "\n\n" + text[match_login.end():]
else:
    print("Could not find login block")
    sys.exit(1)

# 2. Startup replace
match_startup = re.search(r'(def perform_startup_login.*?)$', text, re.DOTALL)
if match_startup:
    text = text[:match_startup.start()] + new_startup_code + "\n"
else:
    print("Could not find startup block")
    sys.exit(1)

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL_NEW.py", "w", encoding="utf-8") as f:
    f.write(text)

import py_compile
try:
    py_compile.compile(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL_NEW.py", doraise=True)
    print("Compile PASS")
except Exception as e:
    print(f"Compile FAIL: {e}")
    sys.exit(1)
