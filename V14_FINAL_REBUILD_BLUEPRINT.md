# V14 FINAL REBUILD BLUEPRINT

This blueprint specifies the intended, evidence-based architecture for the final production worker, based ONLY on evidence collected from the repository.

## A. Startup Sequence

1. **Phase A:** Standard-library imports only (asyncio, os, sys, pathlib, etc.)
2. **Phase B:** Check missing dependencies using `importlib.import_module()`. Install using `subprocess.run([sys.executable, "-m", "pip", "install", ...])`. Call `importlib.invalidate_caches()`. Verify all packages import.
3. **Phase C:** Invalidate import caches.
4. **Phase D:** Import third-party modules: selenium, bullmq, psycopg2, boto3, PIL, etc.
5. **System Dependencies:** Verify Chrome, Xvfb, x11vnc, websockify, fluxbox. Install if missing.
6. **Initialize:** Chrome profiles, T0-T3 drivers, W0-W3 drivers, brokers, BullMQ Worker.
7. **Entrypoint:** Colab: `loop.create_task(main())`. Standalone: `asyncio.run(main())`.

## B. Dependency Bootstrap

**RULE:** Do NOT import `selenium`, `PIL`, or `bullmq` at the top of the file.

```python
PYTHON_DEPENDENCIES = {
    "selenium": "selenium",
    "bullmq": "bullmq",
    "psycopg2": "psycopg2-binary",
    "boto3": "boto3",
    "PIL": "Pillow",
    "websockets": "websockets",
    "requests": "requests",
}

def bootstrap_dependencies():
    missing = [pkg for mod, pkg in PYTHON_DEPENDENCIES.items() 
               if not importlib.import_module(mod) succeeds]
    if missing:
        subprocess.run([sys.executable, "-m", "pip", "install", *missing])
        importlib.invalidate_caches()
    # Verify all imports
```

## C. Environment Preflight

- Create directory structure: `/content/downloads/chrome_staging/`, `/content/downloads/wmr_staging/`, `/content/downloads/final_output/`
- Verify Chrome binary installed (NOT Microsoft Edge)
- Clear stale `SingletonLock` files ONLY if no live Chrome process holds them
- Verify Xvfb display is running
- Verify VNC/novnc tunnel is active

## D. Chrome Initialization

- **Chrome Only:** Absolutely NO Microsoft Edge.
- **Arguments:** `--user-data-dir`, `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`, `--no-first-run`
- **CDP Tracking:** `Browser.setDownloadBehavior` with `behavior: "allowAndName"`, `eventsEnabled: True`
- **Profile Management:** Clone master profile to T-specific profiles, remove SingletonLock files

## E. Gemini T0-T3 Initialization

- **Lazy Creation:** T profiles generated when first assigned
- **Persistence:** Chrome window and Gemini application tab stay open indefinitely
- **Profile:** Independent `chrome_profile/T[0-3]` directories
- **Download Directory:** Per-T-slot download directories under `/content/downloads/chrome/T[0-3]/`

## F. WMR W0-W3 Initialization

- **Profiles:** 4 independent WMR profiles (`W0-W3`)
- **Tabs:** 2 logical tabs per profile (W0-T0, W0-T1, W1-T0, W1-T1, W2-T0, W2-T1, W3-T0, W3-T1)
- **Persistence:** Shared across multiple WMR tasks
- **Thread Safety:** Selenium operations in `asyncio.to_thread()`

## G. WMR Tabs

- **Count:** 2 per profile = 8 total logical resources
- **Naming:** W0-T0 through W3-T1
- **Scheduling:** Global First-Free-Wins across all 8 resources

## H. First-Free Brokers

- **Algorithm:** Monotonic sequence + `heapq` for ordering
- **Gemini:** `T0`, `T1`, `T2`, `T3` released in order of download start
- **WMR:** `W0-T0` through `W3-T1` released in order of download start
- **Never:** Search by lowest ID if it violates release order
- **Implementation:** `FirstFreeBroker` class with `acquire()` and `release()`

## I. BullMQ Admission

- Job enters BullMQ queue named `"generations"`
- Payload extracted: `prompt`, `job_id`, `references`, `user_id`
- Job isolated in `JobContext` with 19-state state machine
- BullMQ Worker concurrency: 8

## J. Job State Machine

```
QUEUED -> GEMINI_RESERVED -> GEMINI_GENERATING -> RAW_DOWNLOAD_START -> 
GEMINI_RELEASED -> RAW_DOWNLOADING -> RAW_READY -> RAW_VALIDATED -> 
WMR_QUEUED -> WMR_RESERVED -> WMR_PROCESSING -> WMR_DOWNLOAD_START -> 
WMR_RELEASED -> CLEAN_READY -> WEBP_READY -> R2_READY -> 
DB_FINALIZING -> DB_READY -> CREDITS_SETTLED -> COMPLETED
```

Failure path: Any state -> FAILED

## K. Download Registry

- **Global dict:** Maps `GUID -> JobContext`
- **Never use:** `newest_file`, `glob.glob()`, filename-only matching
- **Only use:** CDP `Browser.downloadWillBegin` event for GUID
- **Thread-safe:** `threading.Lock` protects all registry operations
- **Fields:** job_id, resource_id, browser/profile, download_guid, suggested_filename, target_path, state, start_time, completion_time

## L. CDP Event Flow

- `Browser.downloadWillBegin`: Extract `guid`, `suggestedFilename`. Register in DownloadRegistry.
- `Browser.downloadProgress`: Extract `state` (`completed`, `inProgress`). Update registry.
- `Browser.setDownloadBehavior`: `allowAndName` with `downloadPath` and `eventsEnabled: True`.

## M. Raw Download Pipeline

```
Gemini generation -> downloadWillBegin -> T resource RELEASED immediately
  -> raw download continues independently -> completed -> stable -> PIL validated
  -> WMR admission
```

**CRITICAL:** T resource becomes FREE immediately after DOWNLOAD START CONFIRMED.
It does NOT wait for raw download completion, PIL validation, WMR, WebP, R2, DB, credits, or BullMQ.

## N. WMR Pipeline

```
Acquire WMR resource -> Upload raw image -> Processing -> exact Download PNG click 
  -> downloadWillBegin -> WMR resource RELEASED immediately
  -> clean download continues -> validate -> WebP -> R2 -> DB -> Credits
```

**CRITICAL:** WMR resource becomes FREE immediately after DOWNLOAD PNG START CONFIRMED.
It does NOT wait for PNG download completion, WebP creation, R2 upload, DB update, or credits.

## O. WebP

```python
Image.open(clean_png_path).convert("RGB").save(webp_path, "WEBP", quality=90)
```
Validate bytes post-save.

## P. R2

- Uses `boto3` client injected via environment variables (`R2_ENDPOINT`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`)
- Uploads WebP payload
- Returns absolute URL

## Q. Database

- Uses `psycopg2` threaded connection pool
- Idempotent `UPDATE` queries for state transitions
- `DB_URL` from environment variable

## R. Credits

- `credits.decrement_credits()` called ONLY after successful pipeline
- Credits failure: log WARNING, do NOT fail the job
- Credits failure must NOT block job completion
- Credits failure must NOT crash the worker

## S. BullMQ Completion

```python
return {"status": "completed"}  # Only after Credits and DB fully committed
```

## T. Failure Isolation

- T0 browser failure MUST NOT kill T1, T2, T3
- W0 failure MUST NOT kill W1, W2, W3
- Single job failure MUST NOT kill worker
- Raw download failure MUST NOT leave T permanently occupied
- WMR download failure MUST NOT leave WMR tab permanently occupied
- DB failure MUST NOT corrupt another job
- Credits failure MUST NOT block job completion

## U. Browser Recovery

- Health check ping on `driver`
- If `WebDriverException`: `driver.quit()` and recreate ONLY that T driver
- Other T resources unaffected

## V. Login Recovery

- State Machine Auth: Google Auth Check + Gemini App Check
- If challenge/logout detected mid-job: pause job, run login recovery for specific profile
- Resume job after re-authentication

## W. Asyncio/Colab

```python
# Colab
loop = asyncio.get_running_loop()
WORKER_MAIN_TASK = loop.create_task(main())
WORKER_MAIN_TASK.add_done_callback(handle_exception)
```

Do NOT use `asyncio.run(main())` inside running notebook loop.

## X. Standalone Execution

```python
if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(main())
    except RuntimeError:
        asyncio.run(main())
```

## Y. Shutdown

- Catch `KeyboardInterrupt` / `SIGINT`
- Cancel `WORKER_MAIN_TASK`
- Gracefully `driver.quit()` all active profiles
- Release all `SingletonLock` files
- Close BullMQ Worker

## Z. Testing Strategy

1. **Dependency bootstrap test:** Verify missing packages install correctly
2. **Chrome-only test:** Verify no Edge references
3. **Colab event loop test:** Verify `loop.create_task(main())` works
4. **Standalone entrypoint test:** Verify `asyncio.run(main())` works
5. **First-Free Gemini test:** Verify release-order behavior
6. **Download GUID correlation test:** Verify GUID -> job_id mapping
7. **Failure isolation test:** Verify T0 crash doesn't kill T1-T3
8. **State machine test:** Verify all 19 states and transitions
9. **Static validation:** py_compile, AST validation, duplicate scan, secret scan, Edge scan, mojibake scan

**Mark as NOT RUNTIME TESTED** when real browser execution is unavailable.
Do NOT mark it PASS.
