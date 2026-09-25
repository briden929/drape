with open('v18_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')
start = -1
end = -1
for i, line in enumerate(lines):
    if 'class WmrWorkerPool:' in line:
        start = i
    if start != -1 and 'self.work_queue.put(None)' in line:
        end = i
        break

if start != -1 and end != -1:
    new_pool = '''class WmrWorkerPool:
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
            WMR_GLOBAL_Q.put(None)'''
    lines[start:end+1] = new_pool.split('\n')
    with open('v18_work.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print("Replaced by index!")
else:
    print("Could not find boundaries")
