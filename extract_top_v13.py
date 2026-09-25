import sys; sys.stdout.reconfigure(encoding="utf-8")
import ast
import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V9.1_FINAL.py', 'r', encoding='utf-8', errors='replace') as f:
    source = f.read()

source = re.sub(r'[\x80-\xFF]', '', source)

tree = ast.parse(source)

skip_names = {
    "GeminiWorker", "GeminiWorkerPool", "WmrWorker", "WmrWorkerPool", "EdgeWorkerPool",
    "central_scheduler_loop", "poll_active_downloads", "_enqueue_wmr", "poll_wmr_workers",
    "update_redis_queue_stats_loop", "process_bullmq_job", "_process_job",
    "assign_jobs_to_idle_tabs", "_finalize_and_clean_job", "main", "_fail_job",
    "create_chrome_driver", "create_wmr_chrome_driver", "print_pipeline_status",
    "run_ast_validation", "preflight_validate_runtime", "run_startup_self_test"
}

skip_globals = {
    "chrome_driver", "chrome_lock", "tab_states", "redis_queue_stats",
    "active_downloads", "counters", "WMR_TABS_PER_PROFILE", "GEMINI_ADMISSION_Q",
    "WMR_GLOBAL_Q", "active_wmr", "gemini_pool", "wmr_pool", "main_loop", "broker"
}

extracted = []
for node in tree.body:
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.name in skip_names:
            continue
    elif isinstance(node, ast.Assign):
        is_skip = False
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in skip_globals:
                is_skip = True
                break
        if is_skip:
            continue
    extracted.append(ast.unparse(node))

top_code = "\n".join(extracted)
with open('v13_clean_top.py', 'w', encoding='utf-8') as f:
    f.write(top_code)
print("Top code extracted!")
