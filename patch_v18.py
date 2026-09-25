import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('v18_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Module Level
mod_vars = """
GEMINI_ADMISSION_Q = None
WMR_GLOBAL_Q = None
gemini_pool = None
wmr_pool = None
main_loop = None
"""
text = text.replace('WMR_GLOBAL_Q = queue.Queue()', '')
text = text.replace('GEMINI_ADMISSION_Q = None # Will be initialized in main()', '')
text = text.replace('GEMINI_ADMISSION_Q = asyncio.Queue(maxsize=4)', '')
text = re.sub(r'(import queue\n)', r'\1' + mod_vars, text)

# 2. Fix GeminiWorker & Pool Initialization Race
new_gemini_init = '''
class GeminiWorker:
    def __init__(self, tid: int):
        self.tid = tid
        self.state = "IDLE"
        self.current_job_id = None
        self.start_time = 0
        self.driver = None

    def start(self):
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"GeminiWorker-T{self.tid}"
        )
        self._thread.start()
        log(f"[T{self.tid}] Gemini worker slot registered (LAZY)")
'''
text = re.sub(r'class GeminiWorker:\n.*?log\(f"\[T\{tid\}\] Gemini worker slot registered \(LAZY\)"\)', new_gemini_init, text, flags=re.DOTALL)

pool_start_all = '''
    def start_all(self):
        for w in self.workers:
            w.start()
'''
text = re.sub(r'gemini_pool = GeminiWorkerPool\(\)', '', text)
text = re.sub(r'(class GeminiWorkerPool:.*?self\.workers = \[GeminiWorker\(i\) for i in range\(max_workers\)\])', r'\1\n' + pool_start_all, text, flags=re.DOTALL)

# Update GeminiWorker._run_loop to correctly await the asyncio queue BEFORE fetching
new_run_loop = '''
    def _run_loop(self):
        while True:
            try:
                future = asyncio.run_coroutine_threadsafe(GEMINI_ADMISSION_Q.get(), main_loop)
                item = future.result()
            except Exception as e:
                log(f"[T{self.tid}] GEMINI ADMISSION GET FAILED: {e}")
                import time
                time.sleep(1)
                continue
                
            if item is None: break
            self.current_job_id = item["job_id"]
            self.state = "SUBMITTING"
            self.start_time = time.time()
            
            try:
                self._process_job(item)
            except Exception as e:
                log(f"[T{self.tid}][{self.current_job_id}] GEMINI_FAILED: {e}")
                _fail_job(self.current_job_id, item.get("gen"), f"Gemini failed: {e}", item.get("future"), 1)
            finally:
                self.state = "IDLE"
                self.current_job_id = None
                self.start_time = 0
                try:
                    main_loop.call_soon_threadsafe(GEMINI_ADMISSION_Q.task_done)
                except Exception:
                    pass
'''
start_idx = text.find('class GeminiWorker:')
end_idx = text.find('    def _process_job(self, item):', start_idx)
orig_run_loop = text[start_idx:end_idx]
text = text[:start_idx + orig_run_loop.find('    def _run_loop(self):')] + new_run_loop + text[end_idx:]


# 3. WmrWorker & Pool Refactor
new_wmr_init = '''
class WmrWorker:
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.staging_dir = get_wmr_staging_dir(worker_id)
        self.driver = None
        self.driver_lock = threading.Lock()
        self.state = "IDLE"
        self.current_job_id = None

    def start(self):
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"WmrWorker-W{self.worker_id}"
        )
        self._thread.start()
        log(f"[WMR-W{self.worker_id}] Worker slot registered (LAZY — Chrome not yet started)")
'''
text = re.sub(r'class WmrWorker:\n.*?log\(f\'\[WMR-W\{self\.worker_id\}\] Worker slot registered \(LAZY.*?\'\)', new_wmr_init, text, flags=re.DOTALL)

wmr_run_loop = '''
    def _run_loop(self):
        while True:
            item = WMR_GLOBAL_Q.get()
            if item is None:
                break
            
            job_id, tid, raw_path, future, loop = item
            self.state = "PROCESSING"
            self.current_job_id = job_id
            prefix = f"[WMR-W{self.worker_id}][{job_id}]"

            try:
                clean_png, webp_path = self._process_job(job_id, tid, raw_path, prefix)
                loop.call_soon_threadsafe(future.set_result, (clean_png, webp_path))
            except Exception as e:
                log(f"{prefix} FAILED: {e}", file=sys.stderr)
                loop.call_soon_threadsafe(future.set_exception, e)
            finally:
                self.state = "IDLE"
                self.current_job_id = None
                WMR_GLOBAL_Q.task_done()
'''
text = re.sub(r'    def _run_loop\(self\):.*?WMR_GLOBAL_Q\.task_done\(\)', wmr_run_loop, text, flags=re.DOTALL)

new_wmr_pool = '''class WmrWorkerPool:
    def __init__(self, n: int = CHROME_WMR_WORKERS):
        self._max = n
        self._workers = [WmrWorker(i) for i in range(n)]

    def start_all(self):
        for w in self._workers:
            w.start()

    def submit_job(self, job_id: str, chrome_tab_id: int, raw_png_path: str, future, loop):
        WMR_GLOBAL_Q.put((job_id, chrome_tab_id, raw_png_path, future, loop))
        log(f"[WMR_GLOBAL] Enqueued job {job_id} (Q_depth={WMR_GLOBAL_Q.qsize()})")
        
    def status(self):
        return [(w.worker_id, w.state, w.current_job_id) for w in self._workers]

    def quit_all(self):
        for _ in range(self._max):
            WMR_GLOBAL_Q.put(None)
'''
text = re.sub(r'class WmrWorkerPool:.*?def quit_all\(self\):.*?WMR_GLOBAL_Q\.put\(None\)\n', new_wmr_pool, text, flags=re.DOTALL)


# 4. Inject Missing Functions (from clean_extracted.py)
with open('clean_extracted.py', 'r', encoding='utf-8') as f:
    clean_ext = f.read()
text = re.sub(r'(async def central_scheduler_loop\(\):)', clean_ext + r'\n\n\1', text)


# 5. Fix Main function & Preflight
main_func = '''
def preflight_validate_runtime():
    required = [
        "create_gemini_driver",
        "create_wmr_chrome_driver",
        "update_redis_queue_stats_loop",
        "central_scheduler_loop",
        "process_bullmq_job",
        "print_pipeline_status",
        "poll_active_downloads",
        "_enqueue_wmr",
        "poll_wmr_workers",
        "_finalize_and_clean_job",
        "GEMINI_ADMISSION_Q",
        "WMR_GLOBAL_Q",
        "redis_queue_stats",
        "gemini_pool",
        "wmr_pool",
    ]

    missing = [x for x in required if x not in globals()]
    if missing:
        raise RuntimeError("STARTUP_PREFLIGHT_FAILED: " + ", ".join(missing))
        
    assert callable(poll_active_downloads)
    assert callable(_enqueue_wmr)
    assert callable(poll_wmr_workers)
    assert callable(_finalize_and_clean_job)
    assert callable(update_redis_queue_stats_loop)
    assert isinstance(GEMINI_ADMISSION_Q, asyncio.Queue)
    
    print("STARTUP_PREFLIGHT=PASS")

async def main():
    global GEMINI_ADMISSION_Q, WMR_GLOBAL_Q, main_loop, gemini_pool, wmr_pool
    main_loop = asyncio.get_running_loop()
    
    GEMINI_ADMISSION_Q = asyncio.Queue(maxsize=4)
    import queue
    WMR_GLOBAL_Q = queue.Queue()
    
    gemini_pool = GeminiWorkerPool(MAX_CONCURRENT_TABS)
    wmr_pool = WmrWorkerPool(MAX_WMR_WORKERS)
    
    preflight_validate_runtime()
    run_startup_self_test()
    
    gemini_pool.start_all()
    wmr_pool.start_all()
'''
text = re.sub(r'def preflight_validate_runtime\(\):.*?run_startup_self_test\(\)', main_func, text, flags=re.DOTALL)


# 6. Self-test update
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


# 7. Add redis stats loop back (in case v16 missed it, v16 didn't have it either since v16 was before fix_redis)
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
text = re.sub(r'(# ============================================================================\n# COMPACT PIPELINE STATUS)', redis_stats_code + r'\n\1', text)


# 8. print_pipeline_status rewrite
status_func = '''
last_status_print = 0
def print_pipeline_status():
    global last_status_print
    now = time.time()
    if now - last_status_print < 2.5:
        return
    last_status_print = now

    dl_waiting = sum(1 for d in active_downloads.values() if d.get("state") == "DOWNLOAD_WAITING")
    dl_raw = sum(1 for d in active_downloads.values() if d.get("state") == "CHROME_RAW_READY")
    wmr_status = wmr_pool.status()

    print("\\n" + "=" * 68)
    print(f"PIPELINE STATUS {time.strftime('%H:%M:%S')}")
    print("=" * 68)
    
    print("\\nREDIS QUEUE")
    print(f"  WAIT={redis_queue_stats['wait']} | ACTIVE={redis_queue_stats['active']} | DELAYED={redis_queue_stats['delayed']} | PRIORITY={redis_queue_stats['prioritized']} | WAIT_CHILD={redis_queue_stats['waiting-children']}")
    
    print("\\nGEMINI ADMISSION")
    print(f"  WAIT={GEMINI_ADMISSION_Q.qsize()}")

    print("\\nGEMINI T-SLOTS")
    for tid, state, cur_jid, start_time in gemini_pool.status():
        jid = (cur_jid or "---")[:12]
        elapsed = f"{int(now - start_time)}s" if start_time > 0 else "0s"
        print(f"  T{tid} = {state:<13} {elapsed:>3}  {jid}")

    print("\\nDOWNLOADS")
    print(f"  START_WAIT={dl_waiting}")
    print(f"  RAW_READY={dl_raw}")
    
    print("\\nWMR CHROME WORKERS")
    print(f"  QUEUE={WMR_GLOBAL_Q.qsize()}")
    for wid, state, cur_jid in wmr_status:
        jid_str = (cur_jid or "---")[:12]
        print(f"  W{wid} = {state:<13}  Job={jid_str}")

    print("\\nRESULT")
    print(f"  DONE={counters['completed']} | FAIL={counters['failed']}")
    print("=" * 68 + "\\n")
'''
text = re.sub(r'last_status_print = 0\ndef print_pipeline_status\(\):.*?(?=async def central_scheduler_loop\(\):)', status_func + '\n', text, flags=re.DOTALL)


# Write back
with open('v18_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Finished patching v18_work.py perfectly.")
