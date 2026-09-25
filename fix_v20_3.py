import sys
with open('v20_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

def find_line(substr, start=0):
    for i in range(start, len(lines)):
        if substr in lines[i]: return i
    return -1

pool_start = find_line('class WmrWorkerPool:')
if pool_start != -1:
    pool_end = find_line('active_downloads = {}', pool_start)
    if pool_end != -1:
        new_pool = """class WmrWorkerPool:
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
"""
        lines[pool_start:pool_end] = new_pool.split('\n') + ['']

with open('v20_work.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("Step 3: WmrWorkerPool done cleanly")
