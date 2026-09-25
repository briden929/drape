with open('v13_clean_ast_v5.py', 'r', encoding='utf-8') as f:
    text = f.read()

import ast
tree = ast.parse(text)
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.lineno <= 1762 <= node.end_lineno:
            print(f"L1762 is in: {node.name}")
