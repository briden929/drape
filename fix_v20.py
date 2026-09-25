import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('v20_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

# Helpers
def find_line(substr, start=0):
    for i in range(start, len(lines)):
        if substr in lines[i]: return i
    return -1

def delete_block(start_cond, end_cond):
    global lines
    s = find_line(start_cond)
    if s == -1: return
    e = find_line(end_cond, s)
    if e == -1: return
    lines = lines[:s] + lines[e+1:]

# 1. Configs & MAX_WMR_WORKERS
for i, l in enumerate(lines):
    if 'MAX_WMR_WORKERS' in l: lines[i] = l.replace('MAX_WMR_WORKERS', 'CHROME_WMR_WORKERS')
    if 'MAX_CONCURRENT_TABS = 4' in l:
        lines[i] = "GEMINI_WORKERS = 4\nWMR_WORKERS = 4\nBULLMQ_CONCURRENCY = 8\nGEMINI_ADMISSION_SIZE = 4\nCHROME_WMR_WORKERS = WMR_WORKERS\nMAX_CONCURRENT_TABS = GEMINI_WORKERS"

# 2. Mask Credentials
for i, l in enumerate(lines):
    if "'DATABASE_URL': '" in l: lines[i] = "    'DATABASE_URL': 'postgresql://MASKED',"
    elif "'R2_ACCESS_KEY_ID': '" in l: lines[i] = "    'R2_ACCESS_KEY_ID': 'MASKED',"
    elif "'R2_SECRET_ACCESS_KEY': '" in l: lines[i] = "    'R2_SECRET_ACCESS_KEY': 'MASKED',"

# 3. Deduplicate Redis stats
# Delete all redis blocks first
delete_block('redis_queue_stats = {', '}')
delete_block('redis_queue_stats = {', '}')
delete_block('async def update_redis_queue_stats_loop():', '            pass')
delete_block('async def update_redis_queue_stats_loop():', '            pass')

redis_stats_code = """
redis_queue_stats = {
    "wait": 0, "active": 0, "delayed": 0, "prioritized": 0, "waiting-children": 0,
}

async def update_redis_queue_stats_loop():
    from bullmq import Queue
    q = Queue(QUEUE_NAME, {"connection": REDIS_URL, "prefix": REDIS_KEY_PREFIX})
    try:
        while True:
            try:
                counts = await q.getJobCounts()
                redis_queue_stats.update({k: counts.get(k, 0) for k in redis_queue_stats.keys()})
            except asyncio.CancelledError:
                raise
            except Exception as e:
                import sys
                log(f"Redis stats update failed: {e}", file=sys.stderr)
            await asyncio.sleep(2.5)
    finally:
        try:
            await q.close()
        except Exception:
            pass
"""
# Insert before central scheduler
cs_idx = find_line('async def central_scheduler_loop():')
lines.insert(cs_idx, redis_stats_code)

# 4. Remove find_first_idle_tab
delete_block('def find_first_idle_tab():', 'return None')

# 5. Modify GeminiWorker and GeminiWorkerPool
for i, l in enumerate(lines):
    if 'class GeminiWorker:' in l:
        # replace init
        e = find_line('def start(self):', i)
        if e == -1: e = find_line('def _run_loop(self):', i)
        lines[i:e] = """class GeminiWorker:
    def __init__(self, tid: int):
        self.tid = tid
        self.state = "IDLE"
        self.current_job_id = None
        self.start_time = 0
        self.driver = None
        self.current_window_handle = None
        import queue
        self.job_queue = queue.Queue(maxsize=1)

    def start(self):
        import threading
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"GeminiWorker-T{self.tid}"
        )
        self._thread.start()
        log(f"[T{self.tid}] Gemini worker slot registered (LAZY)")
""".split('\n')
        break

# Modify GeminiWorker._run_loop
for i, l in enumerate(lines):
    if 'def _run_loop(self):' in l and 'GeminiWorker' in lines[i-30:i]: # make sure it's GeminiWorker
        e = find_line('def _process_job(self, item):', i)
        lines[i:e] = """    def _run_loop(self):
        import time, sys
        while True:
            item = self.job_queue.get()
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
                if self.driver and self.current_window_handle:
                    try:
                        self.driver.switch_to.window(self.current_window_handle)
                        self.driver.close()
                    except Exception as ex:
                        log(f"[T{self.tid}] Failed to close tab: {ex}", file=sys.stderr)
                        try: self.driver.quit()
                        except: pass
                        self.driver = None
                        
                if self.driver:
                    try:
                        if len(self.driver.window_handles) == 0:
                            self.driver.quit()
                            self.driver = None
                    except:
                        try: self.driver.quit()
                        except: pass
                        self.driver = None

                self.state = "IDLE"
                self.current_job_id = None
                self.start_time = 0
                self.current_window_handle = None
                self.job_queue.task_done()

""".split('\n')
        break

# Modify _process_job to store handle
for i, l in enumerate(lines):
    if 'if not self.driver:' in l:
        lines[i:i+2] = """        if not self.driver:
            self.driver = create_gemini_driver(self.tid)
        self.driver.execute_script("window.open('about:blank', '_blank');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        self.current_window_handle = self.driver.current_window_handle
""".split('\n')
        break

# Delete self.driver.close() from _process_job if present, and handle logic
for i, l in enumerate(lines):
    if 'self.driver.close()' in l and 'def _process_job' in lines[i-150:i]:
        lines[i] = "        pass # handled in finally"

# GeminiWorkerPool
for i, l in enumerate(lines):
    if 'class GeminiWorkerPool:' in l:
        e = find_line('class ', i+1)
        if e == -1: e = find_line('active_downloads', i+1)
        lines[i:e] = """class GeminiWorkerPool:
    def __init__(self, max_workers: int = MAX_CONCURRENT_TABS):
        self.workers = [GeminiWorker(i) for i in range(max_workers)]

    def start_all(self):
        for w in self.workers:
            w.start()

    def status(self):
        return [(w.tid, w.state, w.current_job_id, w.start_time) for w in self.workers]

""".split('\n')
        break

with open('v20_work.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("Step 1 done cleanly")
