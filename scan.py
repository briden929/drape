import ast

with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    code = f.read()

tree = ast.parse(code)
for node in tree.body:
    if isinstance(node, ast.ClassDef):
        print(f"Class: {node.name}")
    elif isinstance(node, ast.FunctionDef):
        print(f"Function: {node.name}")
    elif isinstance(node, ast.AsyncFunctionDef):
        print(f"AsyncFunction: {node.name}")
