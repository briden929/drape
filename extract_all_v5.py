import sys; sys.stdout.reconfigure(encoding="utf-8")
import ast
import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V9.1_FINAL.py', 'r', encoding='utf-8', errors='replace') as f:
    source = f.read()

source = re.sub(r'[\x80-\xFF]', '', source)
source = re.sub(r'[^\x00-\x7F]+', '', source)

tree = ast.parse(source)

old_arch_funcs = {
    "create_chrome_driver", "create_wmr_chrome_driver", "main", "GeminiWorker", 
    "GeminiWorkerPool", "WmrWorker", "WmrWorkerPool", "EdgeWorkerPool",
    "central_scheduler_loop", "poll_active_downloads", "_enqueue_wmr",
    "poll_wmr_workers", "update_redis_queue_stats_loop", "process_bullmq_job",
    "_process_job", "assign_jobs_to_idle_tabs", "_finalize_and_clean_job",
    "_fail_job", "print_pipeline_status", "run_ast_validation",
    "preflight_validate_runtime", "run_startup_self_test",
    "_submit_job_to_tab", "poll_active_tabs", "_recover_stuck_tab", "_create_gemini_tab",
    "set_tab_download_dir", "find_first_idle_tab"
}

extracted = []
for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        extracted.append(ast.unparse(node))
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if node.name not in old_arch_funcs:
            extracted.append(ast.unparse(node))
    elif isinstance(node, ast.Assign):
        is_allowed = False
        for t in node.targets:
            if isinstance(t, ast.Name):
                if t.id.isupper() or t.id in ["_pool", "_pool_lock", "_last_used", "_fallbacks", "WORKER_ID", "QUEUE_NAME"]:
                    is_allowed = True
        if is_allowed:
            extracted.append(ast.unparse(node))

top_code = "\n".join(extracted)

with open('v13_clean_ast_v5.py', 'w', encoding='utf-8') as f:
    f.write(top_code)
print("Extracted ALL non-arch functions v5.")
