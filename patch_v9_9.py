import re

with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"    # Decide: requeue or fail\n    if saved_job is not None and attempt < MAX_JOB_RETRIES:[\s\S]*?asyncio.create_task\(assign_jobs_to_idle_tabs\(\)\)"

new_code = '''    # Let BullMQ handle retries. We just fail the internal envelope future.
    if saved_job is not None:
        log(f"{prefix} BROWSER_UI_ERROR ({reason}) — failing internal job to let BullMQ retry.", file=sys.stderr)
        _fail_job(job_id, saved_gen, reason, future, attempt)

    log(f"{prefix} TAB_T{tid}_RECOVERED — ready for next job.")
    if not job_queue.empty():
        asyncio.create_task(assign_jobs_to_idle_tabs())'''

new_text = re.sub(pattern, new_code, text)
if text != new_text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched _recover_stuck_tab')
else:
    print('Regex failed to match _recover_stuck_tab')
