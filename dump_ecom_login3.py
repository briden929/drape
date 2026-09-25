import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('ecom_source_clean.py', 'r', encoding='utf-8') as f:
    source = f.read()

import ast
tree = ast.parse(source)
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in ('handle_login', 'quick_check_logged_in', 'check_captcha'):
        start = node.lineno - 1
        end = node.end_lineno
        lines = source.split('\n')[start:end]
        print('\n'.join(lines))
        print('-'*80)
