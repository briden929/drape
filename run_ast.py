import os
print("Running AST parse...")
import ast
with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    ast.parse(f.read())
print("AST parsed successfully.")
