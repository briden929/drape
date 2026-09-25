import re, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace tab_states and related locks
text = re.sub(r'tab_states = \[\](.*?)chrome_lock = asyncio\.Lock\(\)', 'GEMINI_ADMISSION_Q = queue.Queue(maxsize=4)\n# Removed tab_states and chrome_lock\n', text, flags=re.DOTALL)

# Delete def _create_gemini_tab, def _free_tab, def _recover_stuck_tab
text = re.sub(r'def _create_gemini_tab.*?def verify_login', 'def verify_login', text, flags=re.DOTALL)

# Delete def open_new_chat_and_reload
text = re.sub(r'def open_new_chat_and_reload.*?def ensure_flash_mode', 'def ensure_flash_mode', text, flags=re.DOTALL)

with open('v13_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Removed legacy Gemini tab functions")
