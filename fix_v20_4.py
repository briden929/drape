import sys
with open('v20_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

def find_line(substr, start=0):
    for i in range(start, len(lines)):
        if substr in lines[i]: return i
    return -1

w_start = find_line('class WmrWorker:')
if w_start != -1:
    e_idx = find_line('def _ensure_driver(self):', w_start)
    if e_idx != -1:
        new_w = """class WmrWorker:
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.staging_dir = get_wmr_staging_dir(worker_id)
        self.driver = None
        self.driver_lock = threading.Lock()
        self.state = "IDLE"
        self.current_job_id = None

    def start(self):
        import threading
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"WmrWorker-W{self.worker_id}"
        )
        self._thread.start()
        log(f"[WMR-W{self.worker_id}] Worker slot registered (LAZY)")
"""
        lines[w_start:e_idx] = new_w.split('\n')

# Delete def submit and def quit from WmrWorker
sub_idx = find_line('def submit(self', w_start)
if sub_idx != -1 and 'def submit' in lines[sub_idx]:
    cls_end = find_line('class WmrWorkerPool:', sub_idx)
    if cls_end != -1:
        lines[sub_idx:cls_end] = ['']

with open('v20_work.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("Step 4: WmrWorker done cleanly")
