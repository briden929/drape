import sys; sys.stdout.reconfigure(encoding="utf-8")
import re

with open('v13_clean_ast_v5.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Imports
unused_imports = [
    'asyncio', 'hmac', 'math', 'platform', 'queue', 'threading', 'traceback', 'types',
    'collections.defaultdict', 'psycopg2', 'selenium.webdriver', 
    'selenium.webdriver.chrome.options.Options as ChromeOptions',
    'bullmq.Worker', 'bullmq.Queue'
]
for imp in unused_imports:
    if '.' in imp and ' ' not in imp:
        mod, name = imp.split('.')
        text = re.sub(rf'^from {mod} import {name}\n', '', text, flags=re.MULTILINE)
    elif ' as ' in imp:
        text = re.sub(rf'^from .*? import {imp}\n', '', text, flags=re.MULTILINE)
    else:
        text = re.sub(rf'^import {imp}\n', '', text, flags=re.MULTILINE)
        
text = re.sub(r'^from datetime import datetime\n', '', text, flags=re.MULTILINE)

# 2. _drive_cookies
text = re.sub(r'global _drive_cookies\n\s*if _drive_cookies:\n\s*return _drive_cookies\n', '', text)
text = re.sub(r'_drive_cookies = cookies\n', '', text)

# 3. Add globals at top
globals_to_add = """
import asyncio
import threading
import psycopg2
import traceback
from selenium.webdriver.chrome.options import Options as ChromeOptions
from bullmq import Worker, Queue
import heapq

SCREEN_W = 1920
SCREEN_H = 1080
_db_pool_lock = threading.Lock()
_db_last_used = {}
_mod_db = None
"""
text = globals_to_add + text

# 4. Remove _free_tab
import ast
tree = ast.parse(text)
new_text = []
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == '_free_tab':
        continue
    new_text.append(ast.unparse(node))
    
text = "\n".join(new_text)

# 5. Fix f-string missing placeholders
text = re.sub(r'f"(\s*\[(?:OK|WARN|ERROR)\].*?)"', r'"\1"', text)
text = re.sub(r"f'(\s*\[(?:OK|WARN|ERROR)\].*?)'", r"'\1'", text)
text = re.sub(r'f"({[^}]+})"', r'f"\1"', text) # just to be safe, wait, re.sub above handles the exact ones

# 6. Unused clicked
text = re.sub(r'clicked = False\n', '', text)

with open('v13_clean_ast_fixed.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Fixes applied.")
