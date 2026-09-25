import re, sys, os

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()
    
with open(r"C:\Users\PC\.gemini\antigravity\scratch\new_login.py", "r", encoding="utf-8") as f:
    new_login_code = f.read()

# Replace login block manually to avoid regex escape issues
match = re.search(r'(def is_logged_in_method_1_profile_avatar.*?def gemini_activity\(driver\):\n(?:    .*\n)*)', text, re.DOTALL)
if match:
    text = text[:match.start()] + new_login_code + "\n\n" + text[match.end():]
else:
    print("Could not find login block")

# Replace startup
match2 = re.search(r'(def perform_startup_login.*?)$', text, re.DOTALL)
if match2:
    # Read the new startup block from file so I don't need to put it inline in PowerShell string
    pass
