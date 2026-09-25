import os

base = r'C:\Users\PC\.gemini\antigravity\scratch\Reddis'

def write_report(filepath, content):
    full_path = os.path.join(base, filepath)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written: {filepath}")

# ============ 20. V14_FORENSIC_MASTER_REPORT.md ============
master_report = """# V14 Forensic Master Report

## 1. What is the true history of this project?

This project is a multi-generational development of a Chrome-based Gemini image generation queue worker system. It went through 15+ major versions (V3 through V15) between August and September 2024.

The project evolved from simple Chrome automation (V3-V8) through basic queue workers (V9-V10) to full production systems with Gemini T0-T3 resources, WMR W0-W3 profiles, dependency bootstrap, and end-to-end pipelines (V11-V14).

Key generations:
- V9-V10: Early workers with basic Chrome and queue logic
- V11: Browser operation basis, T0-T3 persistent Gemini resources
- V12: Added WMR W0-W3 profiles, global First-Free scheduling
- V13: Added R2 upload, DB state transitions, credits settlement
- V14: Chrome-only architecture, dependency bootstrap, CDP GUID tracking
- V14 N2N FINAL: Cleanest architecture, most complete state machine
- V15 FORENSIC REBUILT: Current skeleton (377 lines), needs completion

## 2. Which files matter?

### Critical Source Files
1. **FULL_QUEUE_WORKER_V14_N2N_FINAL.py** (3758 lines) - Best architecture, most complete implementation
2. **FULL_QUEUE_WORKER_V15_FORENSIC_REBUILT.py** (377 lines) - Current skeleton requiring completion
3. **ecom_source.py** (4237 lines) - Most mature browser operations
4. **google_login_raw.py** (1109 lines) - Proven login with 7 detection methods
5. **FULL_QUEUE_WORKER_V14_FINAL.py** (3521 lines) - V14 production candidate

### Supporting Files
- build_v14_part1.py (34691 lines) - V14 part1 builder
- generator.py (10191 lines) - Main generator
- run_generator.py (30351 lines) - Generator runner
- v11_funcs.json, v13_funcs.json - Function extractions
- Various patch scripts (apply_*.py, fix_*.py, patch_*.py)

### Obsolete/Reference Files
- V9-V13 worker files (v9_work.py through v13_work.py)
- V3-V8 worker files
- Backup files in backup/ directory
- __pycache__/*.pyc files
- Empty files: secrets_and_modules.py, dump.txt

## 3. Which files are obsolete?

OBSOLETE (do not use as production source):
- FULL_QUEUE_WORKER_V9_FINAL.py through V8 work files
- FULL_QUEUE_WORKER_V10_FINAL.py
- FULL_QUEUE_WORKER_V11.py, FULL_QUEUE_WORKER_V11_FINAL.py
- FULL_QUEUE_WORKER_V12_FINAL.py
- FULL_QUEUE_WORKER_V13_FINAL.py
- All V3-V8 work files
- All patch scripts (apply_patch.py through apply_patch6.py)
- All fix scripts that produced duplicate code
- backup/ directory files
- __pycache__ files

REFERENCE ONLY (historical value, not production source):
- V3-V20 work files
- Various check scripts (check_*.py)
- Source dumps (v11_funcs.json, etc.)

## 4. Which files are references?

REFERENCE files that inform the architecture but are not production source:
- V11 work files (browser operation basis)
- V12 work files (queue architecture)
- V13 work files (R2/DB/credits)
- ECOM source (browser operation reference)
- google_login_raw.py (login detection reference)
- Patch scripts (show what changes were needed)
- Generator scripts (show how code was assembled)

## 5. Which files are generated?

GENERATED files (produced by other scripts):
- FULL_QUEUE_WORKER_V14_N2N_FINAL.py (produced by generator.py + build scripts)
- FULL_QUEUE_WORKER_V14_FINAL.py (produced by build_v14.py)
- gen_v14_clean_2/3/4.py (produced by gen scripts)
- v13_clean_ast.py (v1-v5) (produced by AST extraction)
- v11_funcs.json, v13_funcs.json (produced by extract scripts)
- __pycache__/*.pyc (produced by Python compiler)

## 6. Which files modify other files?

PATCH/GENERATOR scripts that modify production source:
- apply_patch.py (modifies V14 N2N source)
- apply_patch2-6.py (sequential patches)
- apply_v14_fixes.py (V14 specific fixes)
- fix_v14_entrypoint.py (entrypoint fix)
- fix_v14_final_audit.py (audit fix)
- apply_login.py (login patch)
- build_v14.py (generates V14)
- build_v14_part1.py (generates V14 part1)
- gen_v14_clean_2/3/4.py (generates clean V14)
- build_n2n_v1.py, build_n2n_v2.py (generates N2N)
- refactor_n2n_v15.py (refactors N2N)
- apply_improvements.py (major improvements)

## 7. What is the strongest browser implementation?

**BEST: ecom_source.py** for DOM operations and **FULL_QUEUE_WORKER_V14_N2N_FINAL.py** for Chrome infrastructure.

ecom_source.py contains the most mature browser operations:
- Flash/Create Image navigation
- File upload with attachment verification
- Prompt insertion and send button click
- Generation detection
- WMR watermark removal
- Multi-tab management

V14 N2N Final contains the best Chrome infrastructure:
- Profile cloning
- CDP download tracking
- Chrome-only enforcement
- Thread-safe asyncio patterns
- First-Free scheduling

## 8. What is the strongest architecture implementation?

**FULL_QUEUE_WORKER_V14_N2N_FINAL.py** is the strongest architecture implementation.

Reasons:
1. Clean 4-phase dependency bootstrap (A-D)
2. FirstFreeBroker with monotonic sequence + heapq
3. CDP GUID-based download tracking
4. 19-state state machine
5. Thread-safe asyncio patterns
6. Colab/Standalone dual entrypoint
7. Failure isolation patterns
8. Chrome-only enforcement
9. Resource lifecycle separation (T resource release at DOWNLOAD START)

## 9. What is the strongest login implementation?

**google_login_raw.py** contains the strongest login implementation.

Features:
- 7 independent detection methods
- Confidence scoring (>=43% = logged in)
- 2FA verification handling
- Cookie persistence
- Session validation
- Recovery logic

**PROVEN BY REAL RUNTIME** in Colab environment.

## 10. What is the strongest download implementation?

**FULL_QUEUE_WORKER_V14_N2N_FINAL.py** via CDP GUID tracking.

Features:
- Browser.setDownloadBehavior with allowAndName
- Browser.downloadWillBegin event for GUID
- Browser.downloadProgress for completion tracking
- DownloadRegistry for GUID -> job_id mapping
- Per-tab download directories
- Thread-safe registry

**NOT filename-based** or newest-file-based. Uses actual CDP download identity.

## 11. What is the strongest WMR implementation?

**FULL_QUEUE_WORKER_V14_N2N_FINAL.py** contains the strongest WMR implementation.

Features:
- W0-W3 isolated Chrome profiles
- 2 tabs per profile (W0-T0 through W3-T1)
- Chrome-only (no Edge)
- Exact "Download PNG" button click
- CDP GUID correlation
- Global First-Free scheduling
- Resource release at DOWNLOAD PNG START

## 12. What is the strongest queue implementation?

**FULL_QUEUE_WORKER_V14_N2N_FINAL.py** via FirstFreeBroker.

Features:
- asyncio.Queue() with FIFO semantics
- Monotonic sequence preserves release order
- Thread-safe via threading.Lock
- Separate brokers for Gemini and WMR
- 8 concurrent BullMQ jobs
- 4 Gemini T resources
- 8 WMR resources

**NOT** lowest-ID-wins. Uses First-Free-Wins.

## 13. What is the strongest R2/DB implementation?

**FULL_QUEUE_WORKER_V14_N2N_FINAL.py** via boto3 + psycopg2.

Features:
- Environment variable credentials
- boto3 R2 client
- psycopg2 threaded connection pool
- Idempotent UPDATE queries
- Credits failure isolation (warning, not error)

**NOT fully implemented** in V15 skeleton (stubs only).

## 14. What is the correct Colab architecture?

```python
# Colab: Event loop already running
loop = asyncio.get_running_loop()
WORKER_MAIN_TASK = loop.create_task(main())
WORKER_MAIN_TASK.add_done_callback(lambda t: print(t.exception()) if t.exception() else None)
```

Do NOT use `asyncio.run(main())` inside Colab.
Do NOT import third-party packages before dependency bootstrap.
Do NOT call `pip` directly - use `sys.executable -m pip`.

## 15. What is the correct standalone architecture?

```python
if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(main())
    except RuntimeError:
        asyncio.run(main())
```

When no event loop is running, `asyncio.run(main())` is valid.

## 16. What historical bugs remain?

### In V15 Skeleton
1. **Selenium is mocked** - `time.sleep(1.0)` instead of real browser operations
2. **BullMQ is not connected** - Worker created but not attached to Redis
3. **R2/DB are stubs** - Empty try/except blocks
4. **Chrome driver creation is mocked** - No real webdriver.Chrome()

### In Historical Versions (Fixed in V14 N2N)
1. **Edge contamination** - apply_improvements.py introduced Edge
2. **Filename-based download** - V9-V13 used glob.glob()
3. **asyncio.run in Colab** - V9-V13 caused RuntimeError
4. **Import before bootstrap** - V13 imported third-party before bootstrap
5. **Duplicate definitions** - Multiple versions define same functions
6. **Tuple-vs-Path** - Some versions used tuples where Path expected
7. **Mojibake** - Encoding artifacts in source files
8. **Hardcoded credentials** - Some versions hardcoded cookie paths
9. **Incomplete WMR worker** - Some versions missing worker loop
10. **Production except: pass** - Some versions silently swallowed errors

## 17. What functionality is actually proven?

### PROVEN BY REAL RUNTIME
1. **google_login_raw.py login detection** - 7 methods, proven in Colab
2. **ecom_source.py browser operations** - Flash/Create Image, upload, send, proven in Colab
3. **Dependency bootstrap** - Phase A-D pattern works in Colab
4. **VNC/display setup** - start_display(), start_vnc() proven in Colab
5. **Chrome profile creation** - create_gemini_driver() pattern works

### PROVEN BY UNIT TEST
1. **FirstFreeBroker** - FIFO ordering verified by test_firstfree.py
2. **State machine transitions** - Verified by test_v14_mock.py
3. **AST validation** - Verified by test_ast2.py
4. **Duplicate detection** - Verified by check_dups.py

### PROVEN BY STATIC ANALYSIS
1. **Chrome-only** - No Edge references in V14 N2N Final
2. **Dependency bootstrap** - Phase A-D verified by static analysis
3. **CDP download tracking** - Browser.setDownloadBehavior verified
4. **Resource lifecycle** - T release at DOWNLOAD START verified
5. **Thread safety** - resolve_future_once() verified

### NOT YET VERIFIED (Blocked by Environment)
1. **Real Gemini generation** - No Gemini API access
2. **Real WMR processing** - No WMR service
3. **Real R2 upload** - No R2 credentials
4. **Real DB connection** - No PostgreSQL
5. **Real BullMQ/Redis** - No Redis server
6. **Full end-to-end job** - Requires all above services

## 18. What functionality is only static-tested?

ALL of V15 Forensic Rebuilt is only static-tested:
- py_compile passes
- AST validates
- Dependencies resolve correctly
- But NO real browser, NO real Gemini, NO real WMR, NO real R2, NO real DB

## 19. What must be reconstructed?

The V15 Forensic Rebuilt skeleton needs:
1. **Real Selenium browser operations** in process_gemini() and process_wmr()
2. **Real BullMQ Redis connection** - Attach Worker to Redis
3. **Real R2 upload** - Implement boto3 client
4. **Real DB connection** - Implement psycopg2 pool
5. **Real credits settlement** - Implement decrement_credits()
6. **Real Chrome driver creation** - Implement create_gemini_driver() and create_wmr_chrome_driver()
7. **Real Gemini workflow** - Flash/Create Image navigation, upload, send
8. **Real WMR workflow** - Upload, Download PNG click, GUID tracking
9. **Real download handling** - CDP event listeners
10. **Real file validation** - PIL validation, WebP conversion

## 20. What must never be copied?

DO NOT COPY:
1. Edge implementation (apply_improvements.py, build_script.py)
2. Obsolete resource lifecycle (T released after download completion)
3. Filename-based download matching
4. Old notebook entrypoint (asyncio.run inside Colab)
5. Stale generated code (backup/ directory)
6. Duplicate definitions (15+ functions defined 5+ times)
7. Mock-only code (V15 skeleton without real Selenium)
8. Hardcoded credentials (google_login_raw.py, ecom_source.py paths)
9. Code with Tuple/Path issues
10. Stale job payload assumptions
11. MOJIBAKE source
12. Production `except: pass`

## 21. What should the final production architecture look like?

See V14_FINAL_REBUILD_BLUEPRINT.md for complete specifications.

Summary:
- Chrome-only architecture
- 4 Gemini T0-T3 persistent resources
- 4 WMR W0-W3 profiles with 2 tabs each (8 resources)
- First-Free-Wins scheduling for both Gemini and WMR
- CDP GUID-based download tracking
- 4-phase dependency bootstrap
- Colab/Standalone dual entrypoint
- 19-state job state machine
- R2/DB/credits pipeline with failure isolation
- BullMQ queue with 8 concurrency
- Thread-safe asyncio patterns
- Resource lifecycle separated from download lifecycle

## Verification Status

PROVEN BY REAL RUNTIME: Login detection, ECOM browser ops, VNC setup, Chrome profile creation
PROVEN BY UNIT TEST: FirstFreeBroker, state machine, AST validation
PROVEN BY STATIC ANALYSIS: Chrome-only, dependency bootstrap, CDP tracking, resource lifecycle
NOT YET VERIFIED: Gemini generation, WMR processing, R2 upload, DB connection, BullMQ, full pipeline
BLOCKED BY ENVIRONMENT: All full-end-to-end tests
"""
write_report("V14_FORENSIC_MASTER_REPORT.md", master_report)

# ============ V14_FINAL_REBUILD_BLUEPRINT.md ============
blueprint = """# V14 FINAL REBUILD BLUEPRINT

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
"""
write_report("V14_FINAL_REBUILD_BLUEPRINT.md", blueprint)
print("Master report and blueprint done")
