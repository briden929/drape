import sys; sys.stdout.reconfigure(encoding="utf-8")
import ast

with open('FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)

func_names = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

critical = [
    "create_gemini_driver", "create_wmr_chrome_driver", "poll_active_downloads",
    "_enqueue_wmr", "poll_wmr_workers", "_finalize_and_clean_job",
    "update_redis_queue_stats_loop", "central_scheduler_loop", "process_bullmq_job",
    "print_pipeline_status", "_fail_job"
]
for c in critical:
    count = func_names.count(c)
    if count == 0:
        print(f"AST ERROR: missing critical function {c}")
    elif count > 1:
        print(f"AST ERROR: duplicate critical function {c} (found {count} times)")
    else:
        print(f"AST OK: {c}")
        
for node in ast.walk(tree):
    if isinstance(node, ast.For):
        if isinstance(node.iter, ast.Call) and getattr(node.iter.func, 'id', '') == 'range':
            try:
                arg = node.iter.args[0]
                if getattr(arg, 'value', 0) == 4 or getattr(arg, 'id', '') == 'GEMINI_WORKERS':
                    for stmt in node.body:
                        if isinstance(stmt, ast.If) and 'idle' in ast.unparse(stmt.test).lower():
                            print("AST ERROR: Forbidden numeric tid scanning found.")
            except: pass
print("AST test done")
