import re
with open('v18_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

scheduler_loop = '''async def central_scheduler_loop():
    while True:
        try:
            # Stage 0: Assign Gemini jobs
            for w in gemini_pool.workers:
                if w.state == "IDLE" and w.job_queue.empty():
                    try:
                        job = GEMINI_ADMISSION_Q.get_nowait()
                        w.job_queue.put(job)
                    except asyncio.QueueEmpty:
                        break

            # Stage 1: Poll Chrome filesystem download watchers
            await poll_active_downloads()

            # Stage 2: Poll WMR Chrome worker completions
            await poll_wmr_workers()

            # Stage 3: Status display
            print_pipeline_status()

        except Exception as e:
            import sys
            log(f"Scheduler loop error: {e}", file=sys.stderr)

        await asyncio.sleep(0.1)
'''
text = re.sub(r'async def central_scheduler_loop\(\):.*?await asyncio\.sleep\(0\.1\)\n', scheduler_loop, text, flags=re.DOTALL)

with open('v18_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Step 3 done")
