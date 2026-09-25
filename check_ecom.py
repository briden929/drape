import ast

with open('ecom_source.py', 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)
funcs = [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
print("Functions in ECOM:", funcs)
