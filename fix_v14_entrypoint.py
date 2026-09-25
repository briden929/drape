"""
V14 COMPREHENSIVE ENTRYPOINT FIX + RUNTIME HARDENING
=====================================================
Fixes:
1. Replaces broken is_running_in_notebook() raise -> schedules on existing loop
2. Adds worker_main_task global for lifecycle tracking
3. Adds start_in_current_environment() helper
4. Double-start protection
5. Clean terminal + Colab dual mode
6. Auto-exec logic for exec() in Colab
7. Adds startup logging sequence per blueprint
"""
import re
import ast

v14_path = r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py"
with open(v14_path, "r", encoding="utf-8") as f:
    source = f.read()

# ---- Step 1: Add worker_main_task global near the other globals ----
old_globals_block = "# Globals\nmain_loop = None\ngemini_pool = None\nwmr_pool = None\njob_contexts = {}\ndownload_registry = {}\nGEMINI_BROKER = None\nWMR_BROKER = None\nchrome_driver = None"

new_globals_block = """# Globals
main_loop = None
gemini_pool = None
wmr_pool = None
job_contexts = {}
download_registry = {}
GEMINI_BROKER = None
WMR_BROKER = None
chrome_driver = None

# Entrypoint lifecycle
worker_main_task = None        # asyncio.Task — holds the running main() coroutine
_worker_started = False        # double-start guard"""

if old_globals_block in source:
    source = source.replace(old_globals_block, new_globals_block)
    print("[FIX] Added worker_main_task and _worker_started globals")
else:
    print("[WARN] globals block not matched exactly - trying partial")
    if "chrome_driver = None" in source and "worker_main_task" not in source:
        source = source.replace(
            "chrome_driver = None\n",
            "chrome_driver = None\n\n# Entrypoint lifecycle\nworker_main_task = None\n_worker_started = False\n"
        )
        print("[FIX] Added lifecycle globals via partial match")

# ---- Step 2: Replace the broken tail (is_running_in_notebook + run_worker + if __name__) ----
# Find start of the broken section
old_tail = '''def is_running_in_notebook():
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

if __name__ == "__main__":
    run_worker()'''

new_tail = '''# ==============================================================================
# ENTRYPOINT — DUAL MODE: Colab/Jupyter + Terminal
# ==============================================================================
# Colab (inside running event loop):
#     await main()
#   OR — if source executed via exec() in a cell:
#     start_in_current_environment() is called automatically at module level
#
# Terminal:
#     python FULL_QUEUE_WORKER_V14_FINAL.py
#   → asyncio.run(main()) via run_worker_terminal()
# ==============================================================================

def is_running_in_notebook():
    """Detect whether we are inside an IPython/Colab/Jupyter environment."""
    try:
        from IPython import get_ipython
        shell = get_ipython()
        if shell is None:
            return False
        return type(shell).__name__ in (
            "ZMQInteractiveShell",   # Jupyter / Colab
            "TerminalInteractiveShell",  # IPython terminal
            "InteractiveShell",
        )
    except Exception:
        return False


def start_in_current_environment():
    """
    Universal entrypoint.  Call from any context:

      • Colab cell that exec()s the source
      • import + manual call
      • terminal (fallback)

    Returns:
      asyncio.Task  — when scheduled onto an existing running loop
      None          — when asyncio.run(main()) is used (blocking terminal path)
    """
    global worker_main_task, _worker_started

    # ── Double-start guard ──────────────────────────────────────────────────
    if _worker_started:
        if worker_main_task is not None and not worker_main_task.done():
            log("[WARN] V14 worker is already running — ignoring duplicate start")
            return worker_main_task
        # Previous task finished/crashed — allow restart
        _worker_started = False

    # ── Detect whether an event loop is already running ─────────────────────
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # ── Colab / Jupyter path ────────────────────────────────────────────
        # We are inside an already-running event loop (IPython's).
        # Schedule main() as a task on that loop — never call asyncio.run().
        log("[V14] Colab/Jupyter event loop detected — scheduling worker task")
        _worker_started = True
        worker_main_task = loop.create_task(main(), name="v14-worker-main")
        # Add a done-callback so we can see if it crashes silently
        def _on_done(t):
            if t.cancelled():
                log("[V14] Worker task cancelled")
            elif t.exception():
                log(f"[V14] Worker task CRASHED: {t.exception()}")
            else:
                log("[V14] Worker task completed normally")
        worker_main_task.add_done_callback(_on_done)
        return worker_main_task
    else:
        # ── Terminal / subprocess path ───────────────────────────────────────
        log("[V14] No running event loop — using asyncio.run()")
        _worker_started = True
        try:
            asyncio.run(main())
        finally:
            _worker_started = False
        return None


def run_worker_terminal():
    """Blocking terminal entrypoint.  Use: python FULL_QUEUE_WORKER_V14_FINAL.py"""
    return asyncio.run(main())


# ── Auto-exec when this file is the __main__ module ────────────────────────
# Also auto-exec when exec()'d from a Colab cell (since __name__ won't be
# "__main__" there, we rely on the module-level call below).

if __name__ == "__main__":
    # Terminal execution: python FULL_QUEUE_WORKER_V14_FINAL.py
    start_in_current_environment()


# ── Colab exec() auto-start ─────────────────────────────────────────────────
# When the user does: exec(open("FULL_QUEUE_WORKER_V14_FINAL.py").read())
# inside a Colab cell, __name__ is NOT "__main__".
# We detect a running IPython loop and auto-schedule if that's the case.
# The guard _worker_started prevents double-scheduling on import.

if __name__ != "__main__" and not _worker_started:
    try:
        _loop = asyncio.get_running_loop()
        if _loop is not None and _loop.is_running():
            # Running inside Colab cell via exec() — auto-start
            start_in_current_environment()
    except RuntimeError:
        pass  # No running loop — module was imported, not exec()'d
'''

if old_tail in source:
    source = source.replace(old_tail, new_tail)
    print("[FIX] Replaced broken entrypoint with dual-mode entrypoint")
else:
    print("[WARN] old_tail not matched exactly — trying line-based replacement")
    # Find the line number of is_running_in_notebook
    lines = source.split("\n")
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "def is_running_in_notebook():":
            start_idx = i
            break
    if start_idx is not None:
        source = "\n".join(lines[:start_idx]) + "\n" + new_tail
        print(f"[FIX] Replaced from L{start_idx+1} to end")
    else:
        print("[FAIL] Could not find is_running_in_notebook to replace")

# ---- Step 3: Fix main() startup logging per blueprint ----
# Find the startup sequence inside main() and add proper log messages
old_main_header = '''async def main():
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
    print("===============================================================")'''

new_main_header = '''async def main():
    global main_loop, gemini_pool, wmr_pool, GEMINI_BROKER, WMR_BROKER, _worker_started

    # ── Step 1: Acquire event loop ──────────────────────────────────────────
    main_loop = asyncio.get_running_loop()
    log("[V14] Runtime starting")
    log("[V14] Event loop acquired")

    try:
        # ── Step 2: Directories + configuration ──────────────────────────────
        log("[V14] Running startup preflight...")
        startup_preflight()
        log("[V14] Configuration validated")'''

if old_main_header in source:
    source = source.replace(old_main_header, new_main_header)
    print("[FIX] Enhanced main() header with blueprint startup logging")
else:
    print("[WARN] main() header not matched exactly")

# ---- Step 4: Fix main() broker init logging ----
old_broker_init = '''    # ------------------------------------------------------------
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
    wmr_pool.start_all()'''

new_broker_init = '''        # ── Step 4: Gemini broker ─────────────────────────────────────────────
        GEMINI_BROKER = FirstFreeBroker()
        log("[V14] Gemini broker ready")

        # ── Step 5: WMR broker ───────────────────────────────────────────────
        WMR_BROKER = FirstFreeBroker()
        log("[V14] WMR broker ready")

        # ── Step 6: Gemini pool ───────────────────────────────────────────────
        gemini_pool = GeminiWorkerPool(GEMINI_WORKERS)
        gemini_pool.start_all()
        log(f"[V14] Gemini pool starting ({GEMINI_WORKERS} slots: T0-T{GEMINI_WORKERS-1})")

        # ── Step 7: WMR pool ─────────────────────────────────────────────────
        wmr_pool = WmrWorkerPool(WMR_WORKERS)
        wmr_pool.start_all()
        log(f"[V14] WMR pool starting ({WMR_WORKERS} profiles x {WMR_TABS_PER_PROFILE} tabs)")'''

if old_broker_init in source:
    source = source.replace(old_broker_init, new_broker_init)
    print("[FIX] Enhanced broker/pool init with blueprint logging")
else:
    print("[WARN] broker init block not matched exactly")

# ---- Step 5: Fix main() task start logging ----
old_task_start = '''    # ------------------------------------------------------------
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
        log("[V14] Shutdown started")'''

new_task_start = '''        # ── Step 10: Download monitor ─────────────────────────────────────────
        download_task = asyncio.create_task(
            poll_active_downloads(),
            name="v14-download-monitor"
        )
        log("[V14] Download monitor starting")

        # ── Step 11: BullMQ Worker ────────────────────────────────────────────
        redis_url = os.environ.get('REDIS_TUNNEL_URL') or os.environ.get('REDIS_URL')
        if not redis_url:
            log("[WARN] REDIS_TUNNEL_URL / REDIS_URL not set — BullMQ will not connect")
        log("[V14] BullMQ worker starting")
        worker = Worker(
            QUEUE_NAME,
            process_bullmq_job,
            {
                "connection": redis_url or "",
                "prefix": os.environ.get("REDIS_KEY_PREFIX", "vastralook:"),
                "concurrency": BULLMQ_CONCURRENCY,
            },
        )

        # ── Step 12: Mark ready ───────────────────────────────────────────────
        log(
            f"[V14] Worker READY | "
            f"Gemini={GEMINI_WORKERS} T-slots | "
            f"WMR={WMR_WORKERS}x{WMR_TABS_PER_PROFILE} tabs | "
            f"BullMQ concurrency={BULLMQ_CONCURRENCY}"
        )

        # ── Step 13: Keep alive ───────────────────────────────────────────────
        try:
            await asyncio.Event().wait()

        except asyncio.CancelledError:
            log("[V14] Main task cancelled — shutting down")

    except Exception as _startup_err:
        log(f"[V14] STARTUP FAILED: {_startup_err}")
        _worker_started = False
        raise

    finally:
        log("[V14] Shutdown started")'''

if old_task_start in source:
    source = source.replace(old_task_start, new_task_start)
    print("[FIX] Enhanced BullMQ/task startup with blueprint logging")
else:
    print("[WARN] task_start block not matched — trying partial")
    # Try key substring
    if "# Keep the current asyncio loop alive." in source:
        source = source.replace(
            "    try:\n        # Keep the current asyncio loop alive.\n        await asyncio.Event().wait()\n\n    except asyncio.CancelledError:\n        log(\"[V14] Main task cancelled\")\n\n    finally:\n        log(\"[V14] Shutdown started\")",
            "        try:\n            await asyncio.Event().wait()\n\n        except asyncio.CancelledError:\n            log(\"[V14] Main task cancelled\")\n\n    except Exception as _startup_err:\n        log(f\"[V14] STARTUP FAILED: {_startup_err}\")\n        _worker_started = False\n        raise\n\n    finally:\n        log(\"[V14] Shutdown started\")"
        )
        print("[FIX] Partial fix applied for main() keep-alive block")

# ---- Save ----
with open(v14_path, "w", encoding="utf-8") as f:
    f.write(source)

print("\n[DONE] All fixes written to V14")

# ---- Validate ----
import ast
try:
    ast.parse(source)
    print("[PASS] AST parse OK")
except SyntaxError as e:
    print(f"[FAIL] SyntaxError: {e}")
    lines = source.split("\n")
    if hasattr(e, "lineno") and e.lineno:
        for i in range(max(0, e.lineno-5), min(len(lines), e.lineno+5)):
            print(f"  L{i+1}: {lines[i]}")
