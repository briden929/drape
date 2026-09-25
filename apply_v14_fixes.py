import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

# 1. Replace resolve_future_once
new_resolve = """def resolve_future_once(loop, future, result, is_exception=False):
    if future is None:
        return False

    if loop is None:
        return False

    if loop.is_closed():
        return False

    def _resolve():
        if future.done():
            return

        if is_exception:
            future.set_exception(result)
        else:
            future.set_result(result)

    try:
        loop.call_soon_threadsafe(_resolve)
        return True
    except RuntimeError:
        return False"""
source = re.sub(r'def resolve_future_once.*?asyncio\.run_coroutine_threadsafe\(_resolve\(\), loop\)', new_resolve, source, flags=re.DOTALL)

# 2. Add is_running_in_notebook before run_from_terminal / main
new_main_and_entry = """async def main():
    global main_loop
    global gemini_pool
    global wmr_pool
    global GEMINI_BROKER
    global WMR_BROKER

    main_loop = asyncio.get_running_loop()

    log("[V14] Main asyncio loop acquired")
    
    print("===============================================================")
    print("STARTUP PREFLIGHT")
    startup_preflight()
    print("PREFLIGHT SUCCESSFUL")
    print("===============================================================")

    # ------------------------------------------------------------
    # INITIALIZE BROKERS
    # ------------------------------------------------------------
    GEMINI_BROKER = FirstFreeBroker()
    WMR_BROKER = FirstFreeBroker()

    # ------------------------------------------------------------
    # INITIALIZE GEMINI POOL
    # ------------------------------------------------------------
    gemini_pool = GeminiWorkerPool(GEMINI_WORKERS)
    gemini_pool.start_all()

    # ------------------------------------------------------------
    # INITIALIZE WMR POOL
    # ------------------------------------------------------------
    wmr_pool = WmrWorkerPool(WMR_WORKERS)
    wmr_pool.start_all()

    # ------------------------------------------------------------
    # START BACKGROUND TASKS
    # ------------------------------------------------------------
    download_task = asyncio.create_task(
        poll_active_downloads(),
        name="v14-download-monitor"
    )

    # ------------------------------------------------------------
    # BULLMQ WORKER
    # ------------------------------------------------------------
    redis_url = os.environ.get('REDIS_TUNNEL_URL')
    
    worker = Worker(
        QUEUE_NAME,
        process_bullmq_job,
        {
            "connection": redis_url,
            "prefix": "vastralook:",
            "concurrency": BULLMQ_CONCURRENCY,
        },
    )

    log(
        f"[V14] READY | "
        f"Gemini={GEMINI_WORKERS} | "
        f"WMR={WMR_WORKERS}x{WMR_TABS_PER_PROFILE} | "
        f"BullMQ={BULLMQ_CONCURRENCY}"
    )

    try:
        # Keep the current asyncio loop alive.
        await asyncio.Event().wait()

    except asyncio.CancelledError:
        log("[V14] Main task cancelled")

    finally:
        log("[V14] Shutdown started")

        for task in (download_task,):
            task.cancel()

        await asyncio.gather(
            download_task,
            return_exceptions=True,
        )

        try:
            await worker.close()
        except Exception as e:
            log(f"[V14] BullMQ shutdown warning: {e}")

        # The pools in our implementation don't have a quit_all(), they are just python dicts and threads
        # We can implement a clean shutdown or just let daemon threads die.
        try:
            if wmr_pool:
                for t in wmr_pool.threads.values():
                    t.running = False
                    t.cmd_queue.put(None)
        except Exception as e:
            log(f"[V14] WMR shutdown warning: {e}")

        log("[V14] Shutdown complete")

def is_running_in_notebook():
    try:
        from IPython import get_ipython
        return get_ipython() is not None
    except Exception:
        return False

def run_worker():
    if is_running_in_notebook():
        raise RuntimeError(
            "V14 is running inside Jupyter/Colab. "
            "Use: await main()"
        )

    asyncio.run(main())

if __name__ == '__main__':
    run_worker()
"""

# We need to replace from `async def main():` to the end of the file.
source = re.sub(r'async def main\(\):.*', new_main_and_entry, source, flags=re.DOTALL)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(source)
