import re
with open('v14_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'def _make_tab_state.*?return handle', '', text, flags=re.DOTALL)
with open('v14_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Removed _create_gemini_tab and _make_tab_state")
