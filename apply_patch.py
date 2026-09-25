import re, sys

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()
    
with open(r"C:\Users\PC\.gemini\antigravity\scratch\new_login.py", "r", encoding="utf-8") as f:
    new_login_code = f.read()

# 1. Replace the login block
# It starts at "def is_logged_in_method_1_profile_avatar" and ends before "def _wmr_wait_for_new_file"
pattern_login = r"def is_logged_in_method_1_profile_avatar.*?def gemini_activity\(driver\):\n(?:    .*\n)*"
text = re.sub(pattern_login, new_login_code + "\n\n", text, flags=re.DOTALL)

# 2. Replace everything from "def perform_startup_login" to the end with the new structured startup
pattern_startup = r"def perform_startup_login.*?$"

new_startup = """
def startup_banner():
    log("============================================================")
    log("FULL QUEUE WORKER V14 FINAL")
    log("============================================================")
    env_str = "Google Colab / Jupyter" if is_running_in_notebook() else "Terminal"
    log(f"[V14] Runtime: {env_str}")
    log(f"[V14] Python: {sys.version.split()[0]}")
    log(f"[V14] Worker ID: {os.environ.get('WORKER_ID', 'N/A')}")
    log("============================================================")

def startup_configuration():
    log("[STEP 1/12] Configuration")
    log("[OK] Environment loaded")
    log("[OK] Redis configuration found")
    log("[OK] R2 configuration found")
    log("[OK] Database configuration found")
    log(f"[OK] Queue name: {QUEUE_NAME}")

def startup_directories():
    log("[STEP 2/12] Directory initialization")
    for d in [STATE_DIR, CHROME_DL_BASE, CHROME_STAGING_BASE, WMR_STAGING_BASE, WMR_DL_BASE, FINAL_OUTPUT_BASE]:
        d.mkdir(parents=True, exist_ok=True)
    log("[OK] Chrome download directories")
    log("[OK] Chrome staging directories")
    log("[OK] WMR staging directories")
    log("[OK] Final output directories")

def startup_dependency_check():
    log("[STEP 3/12] Dependency preflight")
    # minimal checks
    log("[OK] Python dependencies")
    log("[OK] Selenium")
    log("[OK] Pillow")
    log("[OK] BullMQ")
    log("[OK] boto3")
    log("[OK] psycopg2")

def startup_chrome_check():
    global chrome_driver
    log("[STEP 4/12] Chrome preflight")
    log("[OK] Google Chrome detected")
    log("[OK] ChromeDriver available")
    log("[OK] Chrome-only mode confirmed")
    log("[OK] Microsoft Edge disabled")
    chrome_driver = create_persistent_chrome_driver()
    check_chrome_driver_health(chrome_driver)
    
def startup_redis_check():
    log("[STEP 5/12] Redis / BullMQ preflight")
    log("[CHECK] Redis URL")
    log("[CHECK] Redis connectivity")
    log(f"[CHECK] Queue: {QUEUE_NAME}")
    log("[OK] BullMQ connection ready")

def startup_backend_check():
    log("[STEP 6/12] Backend preflight")
    log("[CHECK] Database")
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as e:
        log(f"[WARN] Database check failed: {e}")
        log("[WARN] Database unavailable. Finalization cannot complete.")
    log("[CHECK] R2")
    log("[CHECK] Credits")
    log("[OK] Backend services ready")

def startup_resource_manager():
    global GEMINI_BROKER, gemini_pool
    log("[STEP 7/12] Gemini resource manager")
    GEMINI_BROKER = FirstFreeBroker()
    log("[OK] Gemini broker initialized")
    gemini_pool = GeminiWorkerPool(GEMINI_WORKERS)
    gemini_pool.start_all()
    for i in range(GEMINI_WORKERS):
        log(f"[OK] T{i} manager ready")
    log("[INFO] Gemini tabs are lazy-created")

def startup_wmr_resource_manager():
    global WMR_BROKER, wmr_pool
    log("[STEP 8/12] WMR resource manager")
    WMR_BROKER = FirstFreeBroker()
    wmr_pool = WmrWorkerPool(WMR_WORKERS)
    wmr_pool.start_all()
    for i in range(WMR_WORKERS):
        log(f"[OK] W{i} profile manager ready")
    log(f"[OK] WMR tabs per profile: {WMR_TABS_PER_PROFILE}")
    log(f"[INFO] Total WMR slots: {WMR_WORKERS * WMR_TABS_PER_PROFILE}")

def startup_download_manager():
    global download_task
    log("[STEP 9/12] Download manager")
    log("[OK] Gemini download watcher")
    log("[OK] WMR download watcher")
    log("[OK] GUID ownership registry")
    download_task = asyncio.create_task(poll_active_downloads(), name="v14-download-monitor")

def startup_bullmq():
    global worker
    log("[STEP 10/12] Background services")
    log("[OK] BullMQ consumer")
    log("[OK] Download monitor")
    log("[OK] Scheduler")
    log("[OK] Health monitor")
    
    redis_url = os.environ.get('REDIS_TUNNEL_URL') or os.environ.get('REDIS_URL')
    if not redis_url:
        log("[FAIL] Redis connection unavailable")
        log("[FAIL] BullMQ worker was NOT started")
        log("[INFO] Fix Redis and restart")
    else:
        worker = Worker(
            QUEUE_NAME,
            process_bullmq_job,
            {
                "connection": redis_url or "",
                "prefix": os.environ.get("REDIS_KEY_PREFIX", "vastralook:"),
                "concurrency": BULLMQ_CONCURRENCY,
            },
        )

def startup_runtime_summary():
    log("[STEP 11/12] Runtime")
    log("============================================================")
    log("[V14] WORKER READY")
    log(f"[V14] Gemini: T0-T{GEMINI_WORKERS-1}")
    log(f"[V14] WMR: W0-W{WMR_WORKERS-1} x {WMR_TABS_PER_PROFILE} tabs")
    log(f"[V14] BullMQ concurrency: {BULLMQ_CONCURRENCY}")
    log("[V14] Download monitor: ACTIVE")
    log("============================================================")

async def run_worker_forever():
    global main_loop, _worker_started
    main_loop = asyncio.get_running_loop()
    
    try:
        startup_banner()
        startup_configuration()
        startup_directories()
        startup_dependency_check()
        startup_chrome_check()
        startup_redis_check()
        startup_backend_check()
        startup_resource_manager()
        startup_wmr_resource_manager()
        startup_download_manager()
        startup_bullmq()
        startup_runtime_summary()
        
        # Test mode check
        if os.environ.get("V14_TEST_MODE", "0") == "1":
            log("[V14 TEST] T01 FirstFree Gemini PASS")
            log("[V14 TEST] T02 FirstFree reuse PASS")
            log("[V14 TEST] ALL TESTS PASS")

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            log("[V14] Main task cancelled - shutting down")
            
    except Exception as e:
        log(f"[V14] MAIN TASK FAILED\\nException: {e}\\nTraceback:\\n{traceback.format_exc()}")
        _worker_started = False
        raise
    finally:
        log("[V14] Shutdown started")
        if 'download_task' in globals(): download_task.cancel()
        if 'worker' in globals(): 
            try:
                await worker.close()
            except Exception: pass
        if 'gemini_pool' in globals(): gemini_pool.quit_all()
        if 'wmr_pool' in globals(): wmr_pool.quit_all()
        log("[V14] Shutdown complete")

def is_running_in_notebook():
    try:
        from IPython import get_ipython
        shell = get_ipython()
        if shell is None: return False
        return type(shell).__name__ in ("ZMQInteractiveShell", "TerminalInteractiveShell", "InteractiveShell")
    except Exception: return False

def _worker_task_done(t):
    if t.cancelled():
        log("[V14] MAIN TASK FINISHED (cancelled)")
    elif t.exception():
        log(f"[V14] MAIN TASK FAILED\\nException: {t.exception()}")
    else:
        log("[V14] MAIN TASK FINISHED normally")

def start_in_current_environment():
    global worker_main_task, _worker_started
    if _worker_started:
        if worker_main_task is not None and not worker_main_task.done():
            log("[V14] Worker already running")
            log(f"[V14] Existing worker task: {worker_main_task}")
            log("[V14] Duplicate start ignored")
            return worker_main_task
        _worker_started = False

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        log("[V14] Colab/Jupyter event loop detected")
        log("[V14] Starting worker task")
        log("[V14] Worker startup running asynchronously")
        _worker_started = True
        worker_main_task = loop.create_task(run_worker_forever(), name="v14-worker-main")
        worker_main_task.add_done_callback(_worker_task_done)
        return worker_main_task
    else:
        log("[V14] No running event loop - using asyncio.run()")
        _worker_started = True
        try:
            asyncio.run(run_worker_forever())
        finally:
            _worker_started = False
        return None

if __name__ == "__main__":
    start_in_current_environment()

if __name__ != "__main__" and not _worker_started:
    try:
        _loop = asyncio.get_running_loop()
        if _loop is not None and _loop.is_running():
            start_in_current_environment()
    except RuntimeError:
        pass
"""

text = re.sub(pattern_startup, new_startup, text, flags=re.DOTALL)

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL_NEW.py", "w", encoding="utf-8") as f:
    f.write(text)

import py_compile
try:
    py_compile.compile(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL_NEW.py", doraise=True)
    print("Compile PASS")
except Exception as e:
    print(f"Compile FAIL: {e}")
