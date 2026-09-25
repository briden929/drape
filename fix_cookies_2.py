import sys; sys.stdout.reconfigure(encoding="utf-8")
with open('v13_clean_ast_fixed.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('global _drive_cookies', 'pass')
text = text.replace('if _drive_cookies:', 'if False:')
text = text.replace('return _drive_cookies', 'return None')
with open('v13_clean_ast_fixed.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Replaced drive_cookies")
