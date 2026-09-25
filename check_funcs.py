# Check for open_new_chat_and_reload - is it defined?
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    source = f.read()
    
import re
if "def open_new_chat_and_reload" in source:
    print("FOUND: open_new_chat_and_reload")
else:
    print("MISSING: open_new_chat_and_reload")

# Also check check_chrome_driver_health
if "def check_chrome_driver_health" in source:
    print("FOUND: check_chrome_driver_health")
else:
    print("MISSING: check_chrome_driver_health")
    
# check_gemini_error
if "def check_gemini_error" in source:
    print("FOUND: check_gemini_error")
else:
    print("MISSING: check_gemini_error")

# snapshot_urls
if "def snapshot_urls" in source:
    print("FOUND: snapshot_urls")
else:
    print("MISSING: snapshot_urls")
    
# verify_generation_started
if "def verify_generation_started" in source:
    print("FOUND: verify_generation_started")
else:
    print("MISSING: verify_generation_started")

# _inject_prompt_atomic
if "def _inject_prompt_atomic" in source:
    print("FOUND: _inject_prompt_atomic")
else:
    print("MISSING: _inject_prompt_atomic")
    
# create_persistent_chrome_driver
if "def create_persistent_chrome_driver" in source:
    print("FOUND: create_persistent_chrome_driver")
else:
    print("MISSING: create_persistent_chrome_driver")
