import re, sys
with open('v19_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Modify GeminiWorker init to use self.job_queue
init_code = '''
class GeminiWorker:
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
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"GeminiWorker-T{self.tid}"
        )
        self._thread.start()
        log(f"[T{self.tid}] Gemini worker slot registered (LAZY)")
'''
text = re.sub(r'class GeminiWorker:\n.*?log\(f"\[T\{tid\}\] Gemini worker slot registered \(LAZY\)"\)', init_code, text, flags=re.DOTALL)

# Modify GeminiWorker._run_loop
run_loop = '''
    def _run_loop(self):
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
'''
# Careful replacement of _run_loop
start_idx = text.find('class GeminiWorker:')
r_start = text.find('    def _run_loop(self):', start_idx)
p_start = text.find('    def _process_job(self, item):', r_start)
text = text[:r_start] + run_loop + text[p_start:]

# Modify GeminiWorkerPool
pool_code = '''class GeminiWorkerPool:
    def __init__(self, max_workers: int = MAX_CONCURRENT_TABS):
        self.workers = [GeminiWorker(i) for i in range(max_workers)]

    def start_all(self):
        for w in self.workers:
            w.start()

    def status(self):
        return [(w.tid, w.state, w.current_job_id, w.start_time) for w in self.workers]
'''
text = re.sub(r'class GeminiWorkerPool:.*?def status\(self\):.*?return \[\(w\.tid, w\.state, w\.current_job_id, w\.start_time\) for w in self\.workers\]\n', pool_code, text, flags=re.DOTALL)
text = text.replace('gemini_pool = GeminiWorkerPool()', '')

with open('v19_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Task 2 done")
