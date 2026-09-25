import os

with open(r"C:\Users\PC\Downloads\google login.py", "r", encoding="utf-8") as f:
    google_login_code = f.read()
    
with open(r"C:\Users\PC\Downloads\FULL_QUEUE_WORKER_V11.py", "r", encoding="utf-8") as f:
    v11_code = f.read()

# I will write these to scratch so I can reference them easily.
with open(r"C:\Users\PC\.gemini\antigravity\scratch\google_login_raw.py", "w", encoding="utf-8") as f:
    f.write(google_login_code)
    
with open(r"C:\Users\PC\.gemini\antigravity\scratch\v11_raw.py", "w", encoding="utf-8") as f:
    f.write(v11_code)

print(f"google_login.py size: {len(google_login_code)}")
print(f"v11 size: {len(v11_code)}")
