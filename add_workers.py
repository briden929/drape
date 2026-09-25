with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("""
    add('''
class WmrDriverThread(threading.Thread):
    def __init__(self, profile_id):
        super().__init__(daemon=True)
        self.profile_id = profile_id
        self.cmd_queue = queue.Queue()
        self.driver = None
        self.running = True

    def run(self):
        try:
            self.driver = create_wmr_chrome_driver(self.profile_id)
            log(f"[WMR-{self.profile_id}] Driver ready")
        except Exception as e:
            log(f"Failed to create driver for WMR profile {self.profile_id}: {e}")
            return
            
        while self.running:
            try:
                cmd = self.cmd_queue.get(timeout=1.0)
                if cmd is None:
                    break
                func, args, future = cmd
                try:
                    res = func(self.driver, *args)
                    if future and not future.done():
                        future.set_result(res)
                except Exception as e:
                    if future and not future.done():
                        future.set_exception(e)
            except queue.Empty:
                pass

    def execute(self, func, *args):
        fut = concurrent.futures.Future()
        self.cmd_queue.put((func, args, fut))
        return fut.result()

    def quit(self):
        self.running = False
        self.cmd_queue.put(None)

class WmrWorkerPool:
    def __init__(self, num_profiles):
        self.num_profiles = num_profiles
        self.threads = {}
        
    def start_all(self):
        for i in range(self.num_profiles):
            self.threads[i] = WmrDriverThread(i)
            self.threads[i].start()
            for t in range(WMR_TABS_PER_PROFILE):
                WMR_BROKER.release(f"W{i}-T{t}")

    def execute(self, resource_id, func, *args):
        # resource_id is "W0-T0"
        profile_id = int(resource_id.split('-')[0][1:])
        return self.threads[profile_id].execute(func, *args)

class GeminiWorkerPool:
    def __init__(self, max_workers: int=GEMINI_WORKERS):
        self.max_workers = max_workers

    def start_all(self):
        for i in range(self.max_workers):
            GEMINI_BROKER.release(i)
''')
""")
