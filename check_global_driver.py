import sys; sys.stdout.reconfigure(encoding="utf-8")
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

import ast
tree = ast.parse(text)
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "chrome_driver":
                print(f"chrome_driver global assign found: {ast.unparse(node)}")
