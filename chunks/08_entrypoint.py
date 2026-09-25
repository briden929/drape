
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
