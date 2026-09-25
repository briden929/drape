import sys; sys.stdout.reconfigure(encoding="utf-8")
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

import ast
tree = ast.parse(text)
main_func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
print(ast.unparse(main_func))
