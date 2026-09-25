import re

with open(r"C:\Users\PC\.gemini\antigravity\scratch\user_prompt_v14_rebuild.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Extract the ULTRA-FIXED GOOGLE LOGIN block
match = re.search(r'(def is_logged_in_method_1_profile_avatar.*?def handle_google_login_fast.*?return False\s*except Exception as e:.*?return False)', text, re.DOTALL)
if match:
    login_code = match.group(1)
    with open(r"C:\Users\PC\.gemini\antigravity\scratch\new_login.py", "w", encoding="utf-8") as f:
        f.write(login_code)
    print(f"Login code extracted: {len(login_code)} bytes")
else:
    print("Could not extract login code")
