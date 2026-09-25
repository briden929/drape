with open('v13_modified.py', 'r', encoding='utf-8') as f:
    text = f.read()
import ast
tree = ast.parse(text)
for node in tree.body:
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
        if node.name in ["_process_job", "assign_jobs_to_idle_tabs", "_finalize_and_clean_job"]:
            print(f"FOUND OLD FUNC: {node.name}")
