import sys; sys.stdout.reconfigure(encoding="utf-8")
import re

with open('v13_clean_ast_v5.py', 'r', encoding='utf-8') as f:
    text = f.read()

import ast
tree = ast.parse(text)
new_text = []
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == '_free_tab':
        continue
    new_text.append(ast.unparse(node))
text = "\n".join(new_text)

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

with open('v13_clean_ast_fixed.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Fixes applied safely.")
