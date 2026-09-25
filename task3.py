import re
with open('v19_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Modify _process_job handle tracking
text = text.replace(
    '        if not self.driver:\n            self.driver = create_gemini_driver(self.tid)',
    '        if not self.driver:\n            self.driver = create_gemini_driver(self.tid)\n        \n        self.driver.execute_script("window.open(\'about:blank\', \'_blank\');")\n        self.driver.switch_to.window(self.driver.window_handles[-1])\n        self.current_window_handle = self.driver.current_window_handle\n'
)
# We must avoid closing the driver inside _process_job
text = text.replace('            self.driver.close()\n', '')
text = text.replace('            self.driver.switch_to.window(info["handle"])', '            # handle switch is managed')
text = text.replace('        info["handle"] = _create_gemini_tab(tid)', '')

# Modify central_scheduler_loop
scheduler = '''async def central_scheduler_loop():
    while True:
        try:
            # Assign Gemini jobs
            for w in gemini_pool.workers:
                if w.state == "IDLE" and w.job_queue.empty():
                    try:
                        job = GEMINI_ADMISSION_Q.get_nowait()
                        w.job_queue.put(job)
                    except asyncio.QueueEmpty:
                        break

            await poll_active_downloads()
            await poll_wmr_workers()
            print_pipeline_status()
        except Exception as e:
            import sys
            log(f"Scheduler loop error: {e}", file=sys.stderr)
        await asyncio.sleep(0.1)
'''
text = re.sub(r'async def central_scheduler_loop\(\):.*?await asyncio\.sleep\(0\.1\)\n', scheduler, text, flags=re.DOTALL)

with open('v19_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Task 3 done")
