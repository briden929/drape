import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('v17_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Module level variables
mod_vars = """
GEMINI_ADMISSION_Q = None
WMR_GLOBAL_Q = None
gemini_pool = None
wmr_pool = None
main_loop = None
"""
# Find where WMR_GLOBAL_Q = queue.Queue() is and remove it
text = text.replace('WMR_GLOBAL_Q = queue.Queue()', '')
text = text.replace('GEMINI_ADMISSION_Q = None # Will be initialized in main()', '')
text = re.sub(r'(import queue\n)', r'\1' + mod_vars, text)

# 2. GeminiWorker & Pool Refactor
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
text = re.sub(r'gemini_pool = GeminiWorkerPool\(\)', '', text) # Remove global instantiation
text = re.sub(r'(class GeminiWorkerPool:.*?self\.workers = \[GeminiWorker\(i\) for i in range\(max_workers\)\])', r'\1\n' + pool_start_all, text, flags=re.DOTALL)

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

wmr_pool_submit = '''
    def submit_job(self, job_id: str, chrome_tab_id: int, raw_png_path: str, future, loop):
        WMR_GLOBAL_Q.put((job_id, chrome_tab_id, raw_png_path, future, loop))
        log(f"[WMR_GLOBAL] Enqueued job {job_id} (Q_depth={WMR_GLOBAL_Q.qsize()})")
'''
text = re.sub(r'    def submit_job\(self, job_id: str, chrome_tab_id: int, raw_png_path: str, loop\) -> asyncio\.Future:.*?return future', wmr_pool_submit, text, flags=re.DOTALL)

pool_wmr_start_all = '''
    def start_all(self):
        for w in self.workers.values():
            w.start()
'''
text = re.sub(r'(self\.workers\[wid\] = WmrWorker\(wid\))', r'\1\n' + pool_wmr_start_all, text)
text = re.sub(r'wmr_pool = WmrWorkerPool\(\)', '', text) # Remove global instantiation

# 4. Inject Missing Functions (from extracted.py)
with open('extracted.py', 'r', encoding='utf-8') as f:
    extracted = f.read()

# Replace _enqueue_wmr in extracted to use new signature
extracted = re.sub(r'def _enqueue_wmr.*?wmr_pool\.submit\(.*?loop\n    \)', '''
def _enqueue_wmr(job_id: str, dinfo: dict):
    loop = main_loop
    future = loop.create_future()
    dinfo["wmr_future"] = future
    active_wmr[job_id] = dinfo
    wmr_pool.submit_job(
        job_id,
        dinfo["tid"],
        str(dinfo["raw_path"]),
        future,
        loop
    )
    log(f"[{job_id}] WMR_QUEUE -> WMR_GLOBAL_Q")
''', extracted, flags=re.DOTALL)

text = re.sub(r'(async def central_scheduler_loop\(\):)', extracted + r'\n\n\1', text)

# 5. Fix Main function
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
    WMR_GLOBAL_Q = queue.Queue()
    
    gemini_pool = GeminiWorkerPool(MAX_CONCURRENT_TABS)
    wmr_pool = WmrWorkerPool(MAX_WMR_WORKERS)
    
    preflight_validate_runtime()
    run_startup_self_test()
    
    gemini_pool.start_all()
    wmr_pool.start_all()
'''
text = re.sub(r'def preflight_validate_runtime\(\):.*?run_startup_self_test\(\)', main_func, text, flags=re.DOTALL)

with open('v17_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Applied massive architecture fixes!")
