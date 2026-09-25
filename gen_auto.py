import json

v11 = json.load(open('v11_syms.json', 'r', encoding='utf-8'))
v13 = json.load(open('v13_syms.json', 'r', encoding='utf-8'))

defined_by_me = {
    'log', 'resolve_future_once', 'JobState', 'JobContext', 'FirstFreeBroker',
    'GeminiWorker', 'GeminiWorkerPool', 'WmrDriverThread', 'WmrWorkerPool',
    '_run_wmr_logic', 'poll_active_downloads', '_finalize_job',
    'process_job_pipeline', 'process_bullmq_job', 'startup_preflight', 'main',
    # We don't want these obsolete functions
    'update_redis_queue_stats_loop', 'print_pipeline_status', 'central_scheduler_loop',
    'startup_sequence', 'run_ast_validation', 'run_startup_self_test', 'preflight_validate_runtime',
    '_make_tab_state', 'WmrWorker', '_finalize_and_clean_job', '_enqueue_wmr', 'poll_wmr_workers'
}

out = []

for name in v11.keys():
    if name not in defined_by_me:
        out.append(v11[name])
        defined_by_me.add(name)
        
for name in v13.keys():
    if name not in defined_by_me:
        out.append(v13[name])
        defined_by_me.add(name)

with open('auto_funcs.py', 'w', encoding='utf-8') as f:
    f.write("\n\n".join(out))
