with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_TEST.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
# check where the login logic is
match_login = re.search(r'(def is_logged_in_method.*?)(def extract_verification_number)', text, re.DOTALL)
if match_login:
    print(f"Login logic length: {len(match_login.group(1))}")
    print(f"Starts at: {text.find('def is_logged_in_method')}")
