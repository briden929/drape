import sys; sys.stdout.reconfigure(encoding="utf-8")
import re
with open('v13_clean_ast_fixed.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = re.sub(r'global _drive_cookies\n\s*if _drive_cookies:\n\s*return _drive_cookies\n', '', text)
text = re.sub(r'_drive_cookies = cookies\n', '', text)
with open('v13_clean_ast_fixed.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Cookies fixed.")
