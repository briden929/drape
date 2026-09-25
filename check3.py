with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
if 'def assign_jobs_to_idle_tabs' in text:
    print("assign_jobs_to_idle_tabs still exists")
if 'async def central_scheduler_loop' in text:
    print("scheduler loop still exists")
