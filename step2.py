import re, sys

with open('v18_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Modify GeminiWorker init to include job_queue and handle
new_gemini_init = '''
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
text = re.sub(r'class GeminiWorker:\n.*?log\(f"\[T\{tid\}\] Gemini worker slot registered \(LAZY\)"\)', new_gemini_init, text, flags=re.DOTALL)

# Modify GeminiWorker._run_loop to pull from self.job_queue and handle finally: close tab
new_run_loop = '''
    def _run_loop(self):
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
                        try:
                            self.driver.quit()
                        except: pass
                        self.driver = None
                
                # If window handles are messed up, just quit to be safe
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
start_idx = text.find('class GeminiWorker:')
end_idx = text.find('    def _process_job(self, item):', start_idx)
orig_run_loop = text[start_idx:end_idx]
text = text[:start_idx + orig_run_loop.find('    def _run_loop(self):')] + new_run_loop + text[end_idx:]

# Modify _process_job to store current_window_handle
text = text.replace(
    '        # 1) Switch to a new/idle tab',
    '        # 1) Create or switch to a new tab\n        if not self.driver:\n            self.driver = create_gemini_driver(self.tid)\n        # Open a new tab for the job\n        self.driver.execute_script("window.open(\'about:blank\', \'_blank\');")\n        self.driver.switch_to.window(self.driver.window_handles[-1])\n        self.current_window_handle = self.driver.current_window_handle'
)
# Ensure _process_job doesn't use self.driver.close() explicitly if it's handled in finally
text = text.replace('self.driver.close()', '')

with open('v18_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Step 2 done")
