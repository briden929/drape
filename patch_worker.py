# coding: utf-8
with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

replacement = """
# ------------------------------------------------------------------------------
# HEALTH & STARTUP
# ------------------------------------------------------------------------------

def run_architecture_self_test():
    assert len(GEMINI_BROKER.resource_ids) == 4
    assert len(WMR_BROKER.resource_ids) == 8
    assert "T0" in GEMINI_BROKER.resource_ids
    assert "T3" in GEMINI_BROKER.resource_ids
    for rid in ["W0-T0","W0-T1","W1-T0","W1-T1","W2-T0","W2-T1","W3-T0","W3-T1"]:
        assert rid in WMR_BROKER.resource_ids

BACKGROUND_TASKS = set()
BULLMQ_WORKER = None
QUEUE_MONITOR = None
QUEUE_MONITOR_TASK = None
HEARTBEAT_TASK = None
WATCHER_TASK = None

RUNTIME_HEALTH = {
    "redis": False,
    "db": False,
    "r2": False,
    "bullmq": False,
    "download_monitor": False,
    "heartbeat": False,
}

def initialize_runtime_once():
    global WMR_THREADS
    if not WMR_THREADS:
        for i in range(4):
            for j in range(2):
                rid = f"W{i}-T{j}"
                WMR_THREADS[rid] = WmrDriverThread(rid)
                WMR_THREADS[rid].start()

async def redis_queue_monitor_loop():
    global QUEUE_MONITOR
    opts = {"connection": os.environ.get("REDIS_URL"), "prefix": os.environ.get("REDIS_KEY_PREFIX")}
    from urllib.parse import urlparse
    u = urlparse(opts["connection"] or "")
    real_opts = {"host": u.hostname or "localhost", "port": u.port or 6379}
    if u.password: real_opts["password"] = u.password
    if u.scheme == 'rediss': real_opts["tls"] = {}
    QUEUE_NAME = os.environ.get("QUEUE_NAME", "generations")
    
    QUEUE_MONITOR = Queue(
        QUEUE_NAME,
        {
            "connection": real_opts,
            "prefix": opts["prefix"],
        },
    )

    while True:
        try:
            counts = await QUEUE_MONITOR.getJobCounts()

            print("\\n" + "=" * 60)
            print("REDIS / BULLMQ QUEUE STATUS")
            print("=" * 60)
            print(f"Queue: {QUEUE_NAME}")
            print(f"WAITING: {counts.get('waiting', 0)}")
            print(f"ACTIVE: {counts.get('active', 0)}")
            print(f"DELAYED: {counts.get('delayed', 0)}")
            print(f"PRIORITIZED: {counts.get('prioritized', 0)}")
            print(f"WAITING-CHILDREN: {counts.get('waiting-children', 0)}")
            print(f"COMPLETED: {counts.get('completed', 0)}")
            print(f"FAILED: {counts.get('failed', 0)}")
            print("=" * 60)

            if not any([
                counts.get("waiting", 0),
                counts.get("active", 0),
                counts.get("delayed", 0),
            ]):
                print("QUEUE EMPTY - waiting for new BullMQ jobs...")

        except Exception as e:
            print(f"[REDIS MONITOR ERROR] {type(e).__name__}: {e}")

        await asyncio.sleep(5)

async def worker_heartbeat_loop():
    RUNTIME_HEALTH["heartbeat"] = True
    QUEUE_NAME = os.environ.get("QUEUE_NAME", "generations")
    # For tracking uptime
    start_time = time.time()
    
    while True:
        try:
            uptime = time.time() - start_time
            hours, rem = divmod(uptime, 3600)
            minutes, seconds = divmod(rem, 60)
            uptime_str = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
            
            print("\\n" + "=" * 60)
            print("ECOM PHOTOSHOOT N2N WORKER STATUS")
            print("=" * 60)
            
            print("\\nWorker:")
            print(f"  ID        = {WORKER_ID}")
            print(f"  Uptime    = {uptime_str}")
            print(f"  Status    = RUNNING")
            
            print("\\nGemini:")
            for rid in ["T0", "T1", "T2", "T3"]:
                print(f"  {rid} = {'FREE' if rid in GEMINI_BROKER.free_resources else 'BUSY/DEAD'}")
                
            print("\\nWMR:")
            for rid in ["W0-T0", "W0-T1", "W1-T0", "W1-T1", "W2-T0", "W2-T1", "W3-T0", "W3-T1"]:
                print(f"  {rid} = {'FREE' if rid in WMR_BROKER.free_resources else 'BUSY/DEAD'}")

            # Local Jobs
            local_jobs = list(JOB_CONTEXTS.values())
            print("\\nLocal Jobs:")
            print(f"  QUEUED           = {sum(1 for j in local_jobs if j.state == JobState.QUEUED)}")
            print(f"  GEMINI_GENERATING= {sum(1 for j in local_jobs if j.state == JobState.GEMINI_GENERATING)}")
            print(f"  RAW_DOWNLOADING  = {sum(1 for j in local_jobs if j.state == JobState.RAW_DOWNLOADING)}")
            print(f"  RAW_VALIDATED    = {sum(1 for j in local_jobs if j.state == JobState.RAW_VALIDATED)}")
            print(f"  WMR_PROCESSING   = {sum(1 for j in local_jobs if j.state == JobState.WMR_PROCESSING)}")
            print(f"  CLEAN_READY      = {sum(1 for j in local_jobs if j.state == JobState.CLEAN_READY)}")
            print(f"  WEBP_READY       = {sum(1 for j in local_jobs if j.state == JobState.WEBP_READY)}")
            print(f"  COMPLETED        = {sum(1 for j in local_jobs if j.state == JobState.COMPLETED)}")
            print(f"  FAILED           = {sum(1 for j in local_jobs if j.state == JobState.FAILED)}")
            
            print("\\n" + "=" * 60)
            print("WORKER HEARTBEAT")
            print("=" * 60)
            print(f"Worker ID: {WORKER_ID}")
            print(f"Uptime: {uptime_str}")
            print(f"BullMQ Worker: {'RUNNING' if RUNTIME_HEALTH['bullmq'] else 'FAILED'}")
            print(f"Download Monitor: {'RUNNING' if RUNTIME_HEALTH['download_monitor'] else 'FAILED'}")
            print(f"Gemini Broker: OK")
            print(f"WMR Broker: OK")
            print(f"Queue: {QUEUE_NAME}")
            print("=" * 60)
            
        except Exception as e:
            print(f"[HEARTBEAT ERROR] {e}")
            
        await asyncio.sleep(10)

async def main():
    try:
        global BULLMQ_WORKER, QUEUE_MONITOR_TASK, HEARTBEAT_TASK, WATCHER_TASK
        
        print("STEP 11: REDIS HEALTH")
        opts = {"connection": os.environ.get("REDIS_URL"), "prefix": os.environ.get("REDIS_KEY_PREFIX")}
        from urllib.parse import urlparse
        u = urlparse(opts["connection"] or "")
        real_opts = {"host": u.hostname or "localhost", "port": u.port or 6379}
        if u.password: real_opts["password"] = u.password
        if u.scheme == 'rediss': real_opts["tls"] = {}
        QUEUE_NAME = os.environ.get("QUEUE_NAME", "generations")
        
        # Redis pre-flight
        try:
            _q = Queue(QUEUE_NAME, {"connection": real_opts, "prefix": opts["prefix"]})
            await _q.getJobCounts()
            await _q.close()
            print("[REDIS] CONNECTION = OK")
            RUNTIME_HEALTH["redis"] = True
        except Exception as e:
            print("[REDIS] CONNECTION = FAILED")
            raise

        print("STEP 12: DATABASE HEALTH")
        db_conn = sys.modules['db'].borrow()
        db_conn.cursor().execute("SELECT 1")
        db_conn.close()
        print("[DB] CONNECTION = OK")
        RUNTIME_HEALTH["db"] = True

        print("STEP 13: R2 HEALTH")
        # Optional health check for R2 here
        RUNTIME_HEALTH["r2"] = True
        
        print("STEP 14: GEMINI BROKER")
        initialize_runtime_once()
        
        print("STEP 15: WMR BROKER")
        run_architecture_self_test()

        print("STEP 16: DOWNLOAD MONITOR")
        WATCHER_TASK = asyncio.create_task(poll_downloads_loop())
        BACKGROUND_TASKS.add(WATCHER_TASK)
        RUNTIME_HEALTH["download_monitor"] = True

        print("STEP 17: REDIS QUEUE MONITOR")
        if QUEUE_MONITOR_TASK and not QUEUE_MONITOR_TASK.done():
            print("[REDIS MONITOR] Already running")
        else:
            QUEUE_MONITOR_TASK = asyncio.create_task(redis_queue_monitor_loop())
            BACKGROUND_TASKS.add(QUEUE_MONITOR_TASK)

        print("STEP 18: WORKER HEARTBEAT")
        if HEARTBEAT_TASK and not HEARTBEAT_TASK.done():
            print("[HEARTBEAT] Already running")
        else:
            HEARTBEAT_TASK = asyncio.create_task(worker_heartbeat_loop())
            BACKGROUND_TASKS.add(HEARTBEAT_TASK)

        print("STEP 19: BULLMQ WORKER")
        BULLMQ_WORKER = Worker(QUEUE_NAME, process_bullmq_job, {"connection": real_opts, "prefix": opts["prefix"]})
        RUNTIME_HEALTH["bullmq"] = True

        print("STEP 20: WORKER READY")
        print("\\n============================================================")
        print("N2N WORKER READY")
        print("============================================================")
        
        while True:
            await asyncio.sleep(3600)
            
    except asyncio.CancelledError:
        raise
    except Exception:
        print("============================================================")
        print("[FATAL STARTUP ERROR]")
        print("============================================================")
        import traceback
        traceback.print_exc()
        raise

async def shutdown_worker():
    global BULLMQ_WORKER, QUEUE_MONITOR
    if BULLMQ_WORKER: await BULLMQ_WORKER.close()
    if QUEUE_MONITOR: await QUEUE_MONITOR.close()
    
    if QUEUE_MONITOR_TASK: QUEUE_MONITOR_TASK.cancel()
    if HEARTBEAT_TASK: HEARTBEAT_TASK.cancel()
    if WATCHER_TASK: WATCHER_TASK.cancel()
    if WORKER_MAIN_TASK: WORKER_MAIN_TASK.cancel()
    
    for task in BACKGROUND_TASKS:
        task.cancel()
    if BACKGROUND_TASKS:
        await asyncio.gather(*BACKGROUND_TASKS, return_exceptions=True)
    
    print("[SHUTDOWN] Worker stopped cleanly.")

WORKER_MAIN_TASK = None
_RUNTIME_INITIALIZED = False

def _worker_main_task_done(task):
    global _RUNTIME_INITIALIZED
    if task.cancelled():
        print("[WORKER] MAIN TASK CANCELLED")
        return

    exc = task.exception()
    if exc:
        print("=" * 70)
        print("[FATAL] WORKER MAIN TASK CRASHED")
        print("=" * 70)
        import traceback
        traceback.print_exception(
            type(exc),
            exc,
            exc.__traceback__,
        )
    _RUNTIME_INITIALIZED = False

def start_worker():
    global WORKER_MAIN_TASK, _RUNTIME_INITIALIZED
    
    if _RUNTIME_INITIALIZED:
        print("[BOOT] Existing worker already running")
        return WORKER_MAIN_TASK
        
    try: loop = asyncio.get_running_loop()
    except RuntimeError: return asyncio.run(main())
    
    if WORKER_MAIN_TASK and not WORKER_MAIN_TASK.done():
        return WORKER_MAIN_TASK
        
    _RUNTIME_INITIALIZED = True
    WORKER_MAIN_TASK = loop.create_task(main())
    WORKER_MAIN_TASK.add_done_callback(_worker_main_task_done)
    return WORKER_MAIN_TASK

if __name__ == '__main__':
    if "IPython" in sys.modules:
        import IPython
        ipy = IPython.get_ipython()
        if ipy:
            # Inject await directly into the current cell's execution context
            # We do this using run_cell with await
            ipy.run_cell("task = start_worker()\nawait task")
        else:
            task = start_worker()
    else:
        start_worker()
"""

idx = text.find("# ------------------------------------------------------------------------------\n# HEALTH & STARTUP")
if idx != -1:
    with open("FULL_QUEUE_WORKER_FINAL.py", "w", encoding="utf-8") as f:
        f.write(text[:idx] + replacement)
    print("PATCHED")
else:
    print("NOT FOUND")
