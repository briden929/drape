with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

import ast
tree = ast.parse(source)
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == 'comprehensive_login_check':
        start = node.lineno - 1
        end = node.end_lineno
        lines = source.split('\n')[start:end]
        print('\n'.join(lines))
