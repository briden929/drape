import ast
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())
print("AST Parse: PASS")
