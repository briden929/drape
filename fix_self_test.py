import re
with open('v15_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_checks = '''
        assert 'update_redis_queue_stats_loop' in globals(), "missing"
        assert 'redis_queue_stats' in globals(), "missing"
        assert 'central_scheduler_loop' in globals(), "missing"
        assert 'process_bullmq_job' in globals(), "missing"
        assert 'print_pipeline_status' in globals(), "missing"
        assert 'poll_active_downloads' in globals(), "missing"
        assert 'poll_wmr_workers' in globals(), "missing"
'''

text = re.sub(r'(print\("  WMR pool \.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\. PASS"\))', r'\1\n' + new_checks, text)

with open('v15_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated self test")
