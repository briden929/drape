import sys; sys.stdout.reconfigure(encoding="utf-8")
import ast

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)

func_names = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

critical = [
    "create_gemini_driver", "create_wmr_chrome_driver", "poll_active_downloads",
    "_enqueue_wmr", "poll_wmr_workers", "_finalize_and_clean_job",
    "update_redis_queue_stats_loop", "central_scheduler_loop", "process_bullmq_job",
    "print_pipeline_status", "_fail_job"
]

passed = True
for c in critical:
    count = func_names.count(c)
    if count == 0:
        print(f"AST ERROR: missing {c}")
        passed = False
    elif count > 1:
        print(f"AST ERROR: duplicate {c} ({count})")
        passed = False
        
print(f"AST PASS: {passed}")
