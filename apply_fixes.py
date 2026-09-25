import re, sys
with open('v15_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Inject Redis stats loop
redis_stats_code = '''
redis_queue_stats = {
    "wait": 0,
    "active": 0,
    "delayed": 0,
    "prioritized": 0,
    "waiting-children": 0,
}

async def update_redis_queue_stats_loop():
    from bullmq import Queue
    q = Queue(
        QUEUE_NAME,
        {
            "connection": REDIS_URL,
            "prefix": REDIS_KEY_PREFIX,
        }
    )

    try:
        while True:
            try:
                counts = await q.getJobCounts()

                redis_queue_stats["wait"] = counts.get("waiting", 0)
                redis_queue_stats["active"] = counts.get("active", 0)
                redis_queue_stats["delayed"] = counts.get("delayed", 0)
                redis_queue_stats["prioritized"] = counts.get("prioritized", 0)
                redis_queue_stats["waiting-children"] = counts.get("waiting-children", 0)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                log(f"Redis stats update failed: {e}", file=sys.stderr)

            await asyncio.sleep(2.5)

    finally:
        try:
            await q.close()
        except Exception:
            pass
'''
# Find print_pipeline_status and insert before it
text = re.sub(r'(# ============================================================================\n# COMPACT PIPELINE STATUS)', redis_stats_code + r'\n\1', text)

# 2. Change GEMINI_ADMISSION_Q
text = text.replace('GEMINI_ADMISSION_Q = queue.Queue(maxsize=4)', 'GEMINI_ADMISSION_Q = None # Will be initialized in main()')

# In main(), add the initialization and global main_loop
main_init = '''async def main():
    global GEMINI_ADMISSION_Q, main_loop
    main_loop = asyncio.get_running_loop()
    GEMINI_ADMISSION_Q = asyncio.Queue(maxsize=4)
    
    preflight_validate_runtime()
    run_startup_self_test()
'''
text = re.sub(r'async def main\(\):.*?(?=    log\(f"\[\{WORKER_ID\}\])', main_init + '\n', text, flags=re.DOTALL)

# Update GeminiWorker._run_loop to use async queue thread-safely
new_run_loop = '''
    def _run_loop(self):
        while True:
            try:
                # Thread-safe block until item is available in async queue
                future = asyncio.run_coroutine_threadsafe(GEMINI_ADMISSION_Q.get(), main_loop)
                item = future.result()
            except Exception as e:
                log(f"[T{self.tid}] GEMINI ADMISSION GET FAILED: {e}")
                time.sleep(1)
                continue
                
            if item is None: break
            self.current_job_id = item["job_id"]
            self.state = S_SUBMITTING
            self.start_time = time.time()
            
            try:
                self._process_job(item)
            except Exception as e:
                log(f"[T{self.tid}][{self.current_job_id}] GEMINI_FAILED: {e}")
                _fail_job(self.current_job_id, item.get("gen"), f"Gemini failed: {e}", item.get("future"), 1)
            finally:
                self.state = S_IDLE
                self.current_job_id = None
                self.start_time = 0
                try:
                    main_loop.call_soon_threadsafe(GEMINI_ADMISSION_Q.task_done)
                except Exception:
                    pass
'''
text = re.sub(r'    def _run_loop\(self\):.*?GEMINI_ADMISSION_Q\.task_done\(\)', new_run_loop, text, flags=re.DOTALL)

# 3. process_bullmq_job uses await put
text = text.replace('await asyncio.to_thread(GEMINI_ADMISSION_Q.put, job_envelope)', 'await GEMINI_ADMISSION_Q.put(job_envelope)')

with open('v15_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Applied Step 1, 2, 10, 11")
