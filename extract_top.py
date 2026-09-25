import re

with open('v13_base.py', 'r', encoding='utf-8') as f:
    text = f.read()

top = re.search(r'(.*?)(?=# ===============================================================================\n# V12 ARCHITECTURE: QUEUES & GLOBALS)', text, re.DOTALL)
top_code = top.group(1)

with open('v13_top.py', 'w', encoding='utf-8') as f:
    f.write(top_code)
