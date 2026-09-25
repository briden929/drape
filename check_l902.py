with open('v13_clean_ast_v3.py', 'r', encoding='utf-8') as f:
    text = f.read()

import ast
tree = ast.parse(text)
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.lineno <= 902 <= node.end_lineno:
            print(f"L902 is in: {node.name}")
