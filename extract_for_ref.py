import ast

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)
funcs = {}
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        funcs[node.name] = ast.unparse(node)

import json
with open('v13_funcs.json', 'w', encoding='utf-8') as f:
    json.dump(funcs, f, indent=2)
print("Extracted V13 functions for read-only reference.")
