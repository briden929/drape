import sys; sys.stdout.reconfigure(encoding="utf-8")
import ast

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V9.1_FINAL.py', 'r', encoding='utf-8', errors='replace') as f:
    source = f.read()

tree = ast.parse(source)
funcs = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
print("Functions in V9.1:")
print(funcs[:50])
