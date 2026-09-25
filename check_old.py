with open('v13_clean_ast_v3.py', 'r', encoding='utf-8') as f:
    text = f.read()

import ast
tree = ast.parse(text)
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        lines = text.split('\n')[node.lineno-1:node.end_lineno]
        for l in lines:
            if "chrome_lock" in l or "job_queue" in l:
                print(f"Func: {node.name}")
                break
