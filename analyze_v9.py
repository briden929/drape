import ast

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V9.1_FINAL.py', 'r', encoding='utf-8', errors='replace') as f:
    source = f.read()

tree = ast.parse(source)

funcs = []
classes = []
imports = []

for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        imports.append(ast.unparse(node))
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        funcs.append(node.name)
    elif isinstance(node, ast.ClassDef):
        classes.append(node.name)

print("Functions:", len(funcs))
print("Classes:", len(classes))
