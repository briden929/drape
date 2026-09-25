import ast

with open('ecom_source.py', 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in ('handle_login', 'quick_check_logged_in'):
        start = node.lineno - 1
        end = node.end_lineno
        lines = source.split('\n')[start:end]
        print('\n'.join(lines))
        print('-'*80)
