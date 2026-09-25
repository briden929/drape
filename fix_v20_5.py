import sys
with open('v20_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

def find_line(substr, start=0):
    for i in range(start, len(lines)):
        if substr in lines[i]: return i
    return -1

run_idx = find_line('def _run_loop(self):')
if run_idx != -1:
    end_idx = find_line('def _process_job(self,', run_idx)
    new_run = """    def _run_loop(self):
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
                resolve_future_once(loop, future, result=(clean_png, webp_path))
            except Exception as e:
                import sys
                log(f"{prefix} FAILED: {e}", file=sys.stderr)
                resolve_future_once(loop, future, exception=e)
            finally:
                self.state = "IDLE"
                self.current_job_id = None
                WMR_GLOBAL_Q.task_done()
"""
    lines[run_idx:end_idx] = new_run.split('\n')

with open('v20_work.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("Step 5: WmrWorker._run_loop done cleanly")
