import ast
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            print(f"Empty function: {node.name}")
