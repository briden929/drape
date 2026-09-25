import re

with open('gen_v14_clean_2.py', 'r', encoding='utf-8') as f:
    source = f.read()

new_omits = """
    'update_redis_queue_stats_loop', 'print_pipeline_status', 'central_scheduler_loop',
    'startup_sequence', 'run_ast_validation', 'run_startup_self_test', 'preflight_validate_runtime',
    '_make_tab_state', 'WmrWorker', '_finalize_and_clean_job', '_enqueue_wmr', 'poll_wmr_workers',
    'record_dead_letter', 'fetch_generation', '_fail_job',
    '_get_pool', '_mark_used', '_checkout', 'db_connection', '_PooledBorrow', 'db_borrow',
    'credits_settle_look', 'credits_refund_look', 'fs_configured', '_r2_client',
    'fashion_tryon_prompt', 'download_remote_image', 'push_generation'
"""
source = re.sub(r"'update_redis_queue_stats_loop'.*?'fetch_generation'", new_omits, source, flags=re.DOTALL)

with open('gen_v14_clean_4.py', 'w', encoding='utf-8') as f:
    f.write(source)
