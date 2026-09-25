import ast
import json

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)
classes = {}
for node in tree.body:
    if isinstance(node, ast.ClassDef):
        classes[node.name] = ast.unparse(node)

with open('v13_classes.json', 'w', encoding='utf-8') as f:
    json.dump(classes, f, indent=2)
print("Extracted V13 classes.")
