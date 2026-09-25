import os

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"

chunk6 = """
# ================================================================================================================
# WMR WORKER
# ================================================================================================================

class WmrDriverThread(threading.Thread):
    def __init__(self, profile_id: str):
        super().__init__(daemon=True)
        self.profile_id = profile_id
        self.driver = None
        self.command_queue = __import__('queue').Queue()
        self.ready_event = threading.Event()
        self.stop_event = threading.Event()
        self.profile_dir = f"/content/downloads/chrome_profile/{profile_id}"

    def run(self):
        self._create_driver()
        self.ready_event.set()
        while not self.stop_event.is_set():
            try:
                cmd, args = self.command_queue.get(timeout=1.0)
                if cmd == "EXECUTE":
                    loop, ctx, tid = args
                    try:
                        self._do_execute(loop, ctx, tid)
                    except Exception as e:
                        print(f"[ERROR] WMR {tid} failed: {e}")
                        threadsafe_resolve_future(loop, ctx.completion_future, exception=e)
                elif cmd == "STOP":
                    break
            except __import__('queue').Empty:
                pass
        self._quit_safe()

    def _create_driver(self):
        opts = Options()
        opts.add_argument(f"--user-data-dir={self.profile_dir}")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        import undetected_chromedriver as uc
        self.driver = uc.Chrome(options=opts, driver_executable_path=None, browser_executable_path="/usr/bin/google-chrome-stable")

    def _quit_safe(self):
        if self.driver:
            try:
                self.driver.quit()
            except: pass
            self.driver = None

    def _do_execute(self, loop, ctx: JobContext, tid: str):
        import time
        self.driver.get("https://watermarkremover.io")
        time.sleep(2)
        guid = f"wmr-guid-{int(time.time())}"
        rec = DownloadRecord(
            guid=guid, job_id=ctx.job_id, resource_id=tid, resource_type="WMR",
            staging_dir=f"/content/downloads/wmr/{tid}", expected_filename=f"{guid}.png"
        )
        DOWNLOAD_REGISTRY[guid] = rec
        ctx.wmr_guid = guid
        
        print(f"[WMR_DOWNLOAD_START] job={ctx.job_id} resource={tid} guid={guid}")
        WMR_BROKER.release(tid)
        
        asyncio.run_coroutine_threadsafe(ctx.transition(JobState.WMR_RELEASED), loop)
        time.sleep(3)
        rec.state = "completed"
        rec.completed_at = time.time()
        rec.path = os.path.join(rec.staging_dir, f"{guid}.png")
        with open(rec.path, "w") as f: f.write("clean")
        
        ctx.clean_png_path = rec.path
        asyncio.run_coroutine_threadsafe(ctx.transition(JobState.CLEAN_READY), loop)
        threadsafe_resolve_future(loop, ctx.completion_future, result=True)

class WmrWorkerPool:
    def __init__(self, profiles=4, tabs_per_profile=2):
        self.threads = {}
        for i in range(profiles):
            pid = f"W{i}"
            th = WmrDriverThread(pid)
            th.start()
            self.threads[pid] = th
            for j in range(tabs_per_profile):
                tid = f"{pid}-T{j}"
                WMR_BROKER.add_resource(tid)
"""

chunk7 = """
# ================================================================================================================
# BACKEND / BULLMQ
# ================================================================================================================

async def process_job(job: Job):
    job_id = job.id
    ctx = JobContext(job_id=job_id, payload=job.data)
    JOB_CONTEXTS[job_id] = ctx
    loop = asyncio.get_running_loop()
    
    try:
        # 1. Gemini
        tid = await GEMINI_BROKER.acquire()
        ctx.gemini_resource = tid
        await ctx.transition(JobState.GEMINI_RESERVED)
        
        ctx.completion_future = loop.create_future()
        GEMINI_POOL.workers[tid].execute_job(loop, ctx)
        await ctx.completion_future
        
        # 2. WMR
        ctx.completion_future = loop.create_future()
        await ctx.transition(JobState.WMR_QUEUED)
        w_tid = await WMR_BROKER.acquire()
        ctx.wmr_resource = w_tid
        await ctx.transition(JobState.WMR_RESERVED)
        
        pid = w_tid.split("-")[0]
        WMR_POOL.threads[pid].command_queue.put(("EXECUTE", (loop, ctx, w_tid)))
        await ctx.completion_future
        
        # 3. WEBP
        ctx.webp_path = f"/content/downloads/final/{job_id}.webp"
        os.makedirs(os.path.dirname(ctx.webp_path), exist_ok=True)
        with open(ctx.webp_path, "w") as f: f.write("webp")
        await ctx.transition(JobState.WEBP_READY)
        
        # 4. R2 & DB
        await ctx.transition(JobState.COMPLETED)
        return {"status": "completed"}
        
    except Exception as e:
        await ctx.transition(JobState.FAILED)
        ctx.error = str(e)
        raise
"""

chunk8 = """
# ================================================================================================================
# ENTRYPOINT
# ================================================================================================================

GEMINI_POOL = None
WMR_POOL = None
WORKER_MAIN_TASK = None

async def initialize_worker():
    global GEMINI_POOL, WMR_POOL
    GEMINI_POOL = GeminiWorkerPool(capacity=4)
    WMR_POOL = WmrWorkerPool(profiles=4, tabs_per_profile=2)

async def worker_run_loop():
    worker = Worker("job-queue", process_job, {"connection": {"host": "localhost", "port": 6379}})
    print("[BOOT] BullMQ Worker started")
    import asyncio
    while True:
        await asyncio.sleep(3600)

async def main():
    await initialize_worker()
    await worker_run_loop()

def start_worker():
    global WORKER_MAIN_TASK
    try:
        loop = asyncio.get_running_loop()
        if WORKER_MAIN_TASK is not None and not WORKER_MAIN_TASK.done():
            print("[V15] Worker already running")
            return WORKER_MAIN_TASK
        WORKER_MAIN_TASK = loop.create_task(main())
        return WORKER_MAIN_TASK
    except RuntimeError:
        asyncio.run(main())

if __name__ == "__main__":
    start_worker()
"""

with open(os.path.join(ROOT, "chunks", "06_wmr.py"), "w") as f: f.write(chunk6)
with open(os.path.join(ROOT, "chunks", "07_backend.py"), "w") as f: f.write(chunk7)
with open(os.path.join(ROOT, "chunks", "08_entrypoint.py"), "w") as f: f.write(chunk8)
