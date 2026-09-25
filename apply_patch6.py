import sys

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

with open(r"C:\Users\PC\.gemini\antigravity\scratch\new_login.py", "r", encoding="utf-8") as f:
    new_login_code = f.read().lstrip('\ufeff')

with open(r"C:\Users\PC\.gemini\antigravity\scratch\new_startup.py", "r", encoding="utf-8") as f:
    new_startup_code = f.read().lstrip('\ufeff')

start_login = text.find("def is_logged_in_method_1_profile_avatar")
end_login = text.find("def _wmr_wait_for_new_file")

start_startup = text.find("def perform_startup_login")

text = text[:start_startup] + new_startup_code + "\n"
text = text[:start_login] + new_login_code + "\n\n" + text[end_login:]

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL_NEW.py", "w", encoding="utf-8") as f:
    f.write(text)

import py_compile
try:
    py_compile.compile(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL_NEW.py", doraise=True)
    print("Compile PASS")
except Exception as e:
    print(f"Compile FAIL: {e}")
    sys.exit(1)
