with open('v15_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

preflight = '''
def preflight_validate_runtime():
    required = [
        "create_gemini_driver",
        "create_wmr_chrome_driver",
        "update_redis_queue_stats_loop",
        "central_scheduler_loop",
        "process_bullmq_job",
        "print_pipeline_status",
        "poll_active_downloads",
        "poll_wmr_workers",
        "GEMINI_ADMISSION_Q",
        "WMR_GLOBAL_Q",
        "redis_queue_stats",
        "gemini_pool",
        "wmr_pool",
    ]

    missing = [
        x for x in required
        if x not in globals()
    ]

    if missing:
        raise RuntimeError(
            "STARTUP_PREFLIGHT_FAILED: " +
            ", ".join(missing)
        )

    print("STARTUP_PREFLIGHT=PASS")
'''
text = text.replace('def run_startup_self_test():', preflight + '\n\ndef run_startup_self_test():')
text = text.replace('V9.1 READY — CHROME-ONLY DUAL-SYSTEM', 'V10 READY —')

with open('v15_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Added preflight")
