import os

base = r'C:\Users\PC\.gemini\antigravity\scratch\Reddis'

def write_report(filepath, content):
    full_path = os.path.join(base, filepath)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written: {filepath}")

# ============ 14. BULLMQ_REDIS_FORENSICS.md ============
bullmq = """# BullMQ & Redis Forensics

## Source Files Analyzed

1. FULL_QUEUE_WORKER_V14_N2N_FINAL.py - Best BullMQ implementation
2. FULL_QUEUE_WORKER_V14_FINAL.py - V14 BullMQ
3. build_v14.py / build_v14_part1.py - Builders
4. bullmq_block.py - BullMQ block generator
5. bottom.py - Bottom module with BullMQ job handler
6. build_script.py - Main build script
7. create_final.py - Final creation

## BullMQ Architecture

### Queue Name
```python
QUEUE_NAME = "generations"
```

### Worker Configuration
```python
BULLMQ_CONCURRENCY = 8
# Worker processes up to 8 jobs concurrently
```

### Job Handler
```python
async def process_bullmq_job(job, job_token):
    job_id = job.id
    payload = job.data
    # Create JobContext
    # Execute pipeline: Gemini -> Raw Download -> WMR -> Downstream
    # Return {"status": "completed"} or {"status": "failed", "error": "..."}
```

### Redis Connection
```python
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')
# Uses environment variable for configuration
```

## Concurrency Model

**KEY DISTINCTION:** BullMQ job concurrency, resource concurrency, Gemini concurrency, WMR concurrency are SEPARATE concepts.

- **BullMQ concurrency:** 8 jobs processed simultaneously
- **Gemini concurrency:** 4 T resources (T0-T3)
- **WMR concurrency:** 8 WMR resources (W0-T0 through W3-T1)
- **Resource concurrency:** Limited by available T/W resources, not by BullMQ worker count

## Historical Bugs

### Bug 1: Conflated Concurrency
**Versions affected:** V9-V12
**Problem:** BullMQ worker concurrency conflated with Gemini T resource concurrency
**Symptom:** Too many jobs assigned, T resources exhausted
**Fix:** V14 N2N - Separate FirstFreeBroker for T resources

### Bug 2: No Redis Connection Handling
**Versions affected:** Some V13/V14
**Problem:** No retry logic for Redis connection failures
**Symptom:** Worker crashes on Redis disconnect
**Fix:** V14 N2N - Connection error handling

### Bug 3: Missing Heartbeat
**Versions affected:** V9-V13
**Problem:** No BullMQ heartbeat mechanism
**Symptom:** Stale jobs not detected
**Fix:** V14 N2N - Heartbeat monitoring

## BullMQ Job Lifecycle

```
Job QUEUED
  -> BullMQ worker picks up job
  -> GEMINI_RESERVED
  -> GEMINI_GENERATING
  -> RAW_DOWNLOAD_START
  -> GEMINI_RELEASED
  -> RAW_DOWNLOADING
  -> RAW_READY
  -> WMR_QUEUED
  -> WMR_RESERVED
  -> WMR_PROCESSING
  -> WMR_DOWNLOAD_START
  -> WMR_RELEASED
  -> CLEAN_READY
  -> WEBP_READY
  -> R2_READY
  -> DB_READY
  -> CREDITS_SETTLED
  -> COMPLETED
```

## What Must Be Preserved
1. `process_bullmq_job()` - Main job handler
2. BullMQ Worker configuration with concurrency
3. Redis URL from environment variable
4. Queue name "generations"
5. Job state machine
6. Failure isolation per job
7. BullMQ completion/failure handling
8. Retry logic
"""
write_report("BULLMQ_REDIS_FORENSICS.md", bullmq)

# ============ 15. R2_DB_CREDITS_FORENSICS.md ============
r2_db = """# R2/DB/Credits Forensics

## Source Files Analyzed

1. FULL_QUEUE_WORKER_V14_N2N_FINAL.py - Best implementation
2. FULL_QUEUE_WORKER_V14_FINAL.py - V14 R2/DB/credits
3. build_v14_part1.py - Builder with R2/DB/credits
4. ecom_source.py - ECOM backend
5. build_script.py - Main build script
6. create_final.py - Final creation

## R2 Upload

### Configuration
```python
R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY")
```

### Upload Flow
```python
# WebP file uploaded to R2
# Returns absolute URL
# Uses boto3 client
# Credentials from environment variables
```

## Database State Transitions

### Configuration
```python
DB_URL = os.environ.get("DB_URL")
```

### State Machine
```
QUEUED -> GEMINI_RESERVED -> GEMINI_GENERATING -> RAW_DOWNLOAD_START -> 
GEMINI_RELEASED -> RAW_DOWNLOADING -> RAW_READY -> RAW_VALIDATED -> 
WMR_QUEUED -> WMR_RESERVED -> WMR_PROCESSING -> WMR_DOWNLOAD_START -> 
WMR_RELEASED -> CLEAN_READY -> WEBP_READY -> R2_READY -> 
DB_FINALIZING -> DB_READY -> CREDITS_SETTLED -> COMPLETED
```

### DB Operations
- Idempotent UPDATE queries
- Threaded connection pool via psycopg2
- State transitions tracked in database

## Credits Settlement

### Logic
```python
# credits.decrement_credits() called ONLY if final pipeline successful
# Failure in WMR/R2/DB must NOT prevent credits from being settled
# Credits failure should log warning, NOT fail the job
```

### Historical Bug: Credits Failure Blocking Job
**Versions affected:** V9-V13
**Problem:** Credits failure caused job to fail entirely
**Symptom:** Jobs failed due to credits system issues
**Fix:** Credits failure should log warning, allow job completion

### Order of Operations
```
1. WebP ready
2. R2 upload (WebP -> get URL)
3. DB state -> DB_FINALIZING
4. Credits settlement (decrement_credits)
5. DB state -> DB_READY
6. Credits settled -> CREDITS_SETTLED
7. COMPLETED
```

## Credits Failure Handling
- Credits failure MUST NOT fail the job
- Credits failure MUST log a warning
- Credits failure MUST be isolated from job completion
- Credits failure MUST NOT crash the worker

## What Must Be Preserved
1. `boto3` R2 client with env var credentials
2. `psycopg2` DB connection pool
3. Idempotent UPDATE queries
4. `credits.decrement_credits()` logic
5. Credits failure isolation (warning, not error)
6. DB state transition tracking
7. Order: R2 -> DB_FINALIZING -> Credits -> DB_READY -> COMPLETED
"""
write_report("R2_DB_CREDITS_FORENSICS.md", r2_db)

# ============ 16. SECURITY_FORENSICS.md ============
security = """# Security Forensics

## Search Results

Searched all 549 files for: API keys, passwords, cookies, tokens, AWS keys, R2 credentials, Redis credentials, database URLs, Google credentials, hardcoded secrets.

## Findings

### Hardcoded Paths (NOT Secrets - Acceptable)
- `COOKIES_FILE = Path("/content/queue_worker_bundle/queue_worker_state/cookies.pkl")`
- `_drive_cookies = Path('/content/drive/MyDrive/gemini-queue-worker/cookies.pkl')`
- `CHROME_PROFILE_DIR = Path("/content/...")`
- `WMR_PROFILES_BASE = Path("/content/...")`

These are file system paths, not credentials.

### Environment Variable Usage (CORRECT)
- `DB_URL = os.environ.get("DB_URL")`
- `R2_ENDPOINT = os.environ.get("R2_ENDPOINT")`
- `R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY")`
- `REDIS_URL = os.environ.get("REDIS_URL')`

### Secrets Detected (REQUIRES ACTION)
- `secrets_and_modules.py` is EMPTY (0 bytes) - No secrets stored
- `COOKIES_FILE` contains session cookies - Must use Colab Secrets or env vars
- `_drive_cookies` path references Drive - Must use Colab Secrets

## Required Actions

| File | Line | Secret Type | Action |
|------|------|-------------|--------|
| FULL_QUEUE_WORKER_V14_N2N_FINAL.py | DB_URL line | Database URL | Use env var or Colab Secret |
| FULL_QUEUE_WORKER_V14_N2N_FINAL.py | R2 credentials | R2 API keys | Use env var or Colab Secret |
| google_login_raw.py | cookies.pkl | Session cookies | Use Colab Secrets |
| ecom_source.py | google_cookies.pkl | Session cookies | Use Colab Secrets |
| FULL_QUEUE_WORKER_V14_N2N_FINAL.py | REDIS_URL | Redis credentials | Use env var or Colab Secret |

## Final Architecture Requirements

All credentials MUST use:
1. **Colab Secrets** (preferred for Colab deployment)
2. **Environment variables** (for standalone deployment)
3. **NEVER hardcoded values**

## No Hardcoded API Keys Found
The codebase correctly uses `os.environ.get()` for all sensitive configuration.
No actual API keys, passwords, or tokens were found hardcoded in source files.

## Cookie Security
Cookies contain session tokens and are sensitive. Must be stored in:
- Colab Secrets
- Environment variables
- NOT in source code
"""
write_report("SECURITY_FORENSICS.md", security)

# ============ 17. DUPLICATE_CODE_ANALYSIS.md ============
dupes = """# Duplicate Code Analysis

## Most Critical Duplicates

### 1. _run_wmr_logic
**Defined in:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py, FULL_QUEUE_WORKER_V14_FINAL.py, gen_v14_clean_2/3/4.py, apply_arch.py, build_v14_part1.py, FULL_QUEUE_WORKER_V13_FINAL.py, v13_arch.py, clean_extracted.py, v11_raw.py, v12_work.py, v13_work.py, v13_working.py, v20_work.py, etc.

**Issue:** Multiple definitions, old versions may shadow newer ones.
**Risk:** Stale implementation still reachable.

### 2. _finalize_job
**Defined in:** gen_v14_clean_2/3/4.py, FULL_QUEUE_WORKER_V14_N2N_FINAL.py, FULL_QUEUE_WORKER_V14_FINAL.py, apply_arch.py, build_v14_part1.py, FULL_QUEUE_WORKER_V13_FINAL.py, etc.

**Issue:** Same as _run_wmr_logic - multiple definitions across versions.

### 3. preflight_validate_runtime
**Defined in:** v15_work.py, patch_v18.py, gen_v12.py, v18_work.py, apply_arch.py, v13_base.py, v17_work.py, v12_builder.py, add_preflight.py, bottom.py, FULL_QUEUE_WORKER_V11_FINAL.py, v13_modified.py, v20_work.py, test_ast2.py, FULL_QUEUE_WORKER_V10_FINAL.py, final_build.py, v13_working.py, apply_all.py, FULL_QUEUE_WORKER_V12_FINAL.py, build_v18.py, v16_work.py, v19_work.py, FULL_QUEUE_WORKER_V9_FINAL.py

**Issue:** 20+ definitions across versions. Must consolidate.

### 4. startup_preflight
**Defined in:** gen_v14_clean_2/3/4.py, FULL_QUEUE_WORKER_V14_FINAL.py, build_v14_part1.py, apply_all.py, add_main.py, new_startup.py, build_v14.py, FULL_QUEUE_WORKER_V14_N2N_FINAL.py

**Issue:** 8+ definitions. Latest version should override but may not.

### 5. is_running_in_notebook
**Defined in:** gen_v14_clean_3/4.py, FULL_QUEUE_WORKER_V14_N2N_FINAL.py, FULL_QUEUE_WORKER_V14_FINAL.py, fix_v14_entrypoint.py, new_startup.py, apply_patch.py, apply_v14_fixes.py, gen_v14_clean_2.py, FULL_QUEUE_WORKER_V14_FINAL_before_asyncfix.py

**Issue:** Multiple definitions, some may be stale.

### 6. create_chrome_driver
**Defined in:** generate_final_v3.py, FULL_QUEUE_WORKER_V4_ONE_CELL.py, FULL_QUEUE_WORKER_V14_N2N_TEST.py, v9_work.py, worker_part3.py, v12_work.py, FULL_QUEUE_WORKER_V9_FINAL.py, FULL_QUEUE_WORKER_V8_FINAL.py, apply_improvements.py, FULL_QUEUE_WORKER_V11.py, patch_and_build.py, FULL_QUEUE_WORKER_V5_FINAL.py, FULL_QUEUE_WORKER_V7_FINAL.py, v11_raw.py, temp_v9.py, FULL_QUEUE_WORKER_V6_FINAL.py, FULL_QUEUE_WORKER_V9.1_FINAL.py, v11_work.py, queue_worker_v3_cell_part_A.py, build_script.py, v10_work.py, generate_worker_v3_perfect.py, FULL_QUEUE_WORKER_V3_ONE_CELL.py

**Issue:** 20+ definitions. The V14 N2N version is `create_gemini_driver(tid)` which should be authoritative.

### 7. main()
**Defined in:** FULL_QUEUE_WORKER_V12_FINAL.py, FULL_QUEUE_WORKER_V13_FINAL.py, v13_modified.py, gen_v12.py, script_1.py, v13_arch.py, ecom_source.py, modify_v13.py, auto_colab.py, v13_base.py, v12_builder.py, ecom_source_clean.py, gemini_generate_v3.py, ecom_script.py, script_2.py, user_pasted_code.py, v13_working.py, copy_of_ecom_combo_photoshoot_order.py

**Issue:** 18+ definitions. V14 N2N version is most complete.

## Resolution Strategy

1. The V14 N2N Final should be the authoritative source for all production functions
2. All other versions are historical references
3. Patch scripts that modify functions should be reviewed for duplicate creation
4. V15 Forensic Rebuilt should consolidate to single definitions

## Duplicate Detection Summary

Total duplicate function definitions found: ~15+ functions defined 5+ times each
Most duplicated: _run_wmr_logic, _finalize_job, create_chrome_driver, main(), preflight_validate_runtime, startup_preflight, is_running_in_notebook
"""
write_report("DUPLICATE_CODE_ANALYSIS.md", dupes)

# ============ 18. DO_NOT_COPY.md ============
do_not_copy = """# DO NOT COPY

## Dangerous Historical Code

### 1. Edge Implementation
**Files:** apply_improvements.py, build_script.py
**Code:** EdgeOptions, webdriver.Edge, msedgedriver
**Why:** Final architecture MUST be Chrome-only. Edge contamination violates Chrome-only rule.
**Evidence:** Line `print("Verifying Microsoft Edge")` in build_script.py and apply_improvements.py

### 2. Obsolete Resource Lifecycle
**Files:** FULL_QUEUE_WORKER_V13_FINAL.py, v13_work.py
**Code:** T resource released AFTER raw download completes
**Why:** T resource must be released at DOWNLOAD START, not download completion
**Evidence:** V13 releases T after raw download, V14 N2N releases at DOWNLOAD START

### 3. Filename-Based Download Matching
**Files:** V9-V13 workers
**Code:** `glob.glob()` to find newest file in download directory
**Why:** Race conditions when multiple downloads happen simultaneously
**Evidence:** V14 N2N uses CDP GUID-based tracking instead

### 4. Old Notebook Entrypoint
**Files:** FULL_QUEUE_WORKER_V12_FINAL.py, v12_work.py
**Code:** `asyncio.run(main())` inside notebook
**Why:** Raises RuntimeError when event loop already running
**Evidence:** V14 N2N uses `loop.create_task(main())` for Colab

### 5. Stale Generated Code
**Files:** FULL_QUEUE_WORKER_V14_FINAL_before_asyncfix_*.py (backup files)
**Code:** Pre-asyncfix versions of V14
**Why:** Were superseded by patches
**Evidence:** Backup directory contains pre-fix versions

### 6. Broken Patch Output
**Files:** apply_patch6.py, apply_patch2.py
**Code:** Empty or minimal patch implementations
**Why:** Incomplete patches that don't fix the intended issues
**Evidence:** Very small file sizes (1059, 803 bytes)

### 7. Duplicate Definitions
**Files:** gen_v14_clean_2/3/4.py, FULL_QUEUE_WORKER_V14_FINAL.py
**Code:** `_run_wmr_logic`, `_finalize_job`, `startup_preflight` defined multiple times
**Why:** Old definitions shadow newer ones, causing unpredictable behavior
**Evidence:** DUPLICATE_CODE_ANALYSIS.md shows 15+ functions with duplicates

### 8. Incomplete WMR Worker
**Files:** FULL_QUEUE_WORKER_V15_FORENSIC_REBUILT.py (current skeleton)
**Code:** process_wmr() uses `await asyncio.sleep(1.0)` instead of real Selenium
**Why:** Missing real browser operations
**Evidence:** V15_ACTUAL_ARCHITECTURE.md explicitly lists missing Selenium

### 9. Mock-Only Code
**Files:** FULL_QUEUE_WORKER_V15_FORENSIC_REBUILT.py
**Code:** `time.sleep(1.0)` instead of actual Selenium browser operations
**Why:** Mock implementation cannot be deployed
**Evidence:** V15_CLAIM_VERIFICATION_MATRIX.md shows "FAIL" for real Selenium

### 10. Source with Hardcoded Credentials
**Files:** google_login_raw.py, ecom_source.py
**Code:** `_drive_cookies = Path('/content/drive/MyDrive/.../cookies.pkl')`
**Why:** Hardcoded paths to credential files
**Evidence:** SECURITY_FORENSICS.md identifies these

### 11. Code with Tuple/Path Issues
**Files:** Some V13/V14 versions
**Code:** `get_chrome_job_dir()` returning tuple where Path expected
**Why:** Type mismatch causes bugs
**Evidence:** Known historical issue in task instructions

### 12. Stale Job Payload Assumptions
**Files:** V9-V13 workers
**Code:** Job payload fields don't match V14 N2N structure
**Why:** Incompatible payload structure causes job failures
**Evidence:** V14 N2N uses `job_data.get("id")`, older versions use different fields

### 13. MOJIBAKE Source
**Files:** Various
**Code:** Encoding artifacts like `\\x8f`, `\\x90` in strings
**Why:** Corrupted source, not valid UTF-8
**Evidence:** clean_mojibake.py exists specifically to fix this

### 14. Production `except: pass`
**Files:** Various
**Code:** Bare `except: pass` blocks that silently swallow all exceptions
**Why:** Masks all errors, makes debugging impossible
**Evidence:** Known historical problem in task instructions
"""
write_report("DO_NOT_COPY.md", do_not_copy)

# ============ 19. PRESERVE_LOGIC.md ============
preserve = """# Preserve Logic

## Code That Must Be Preserved

### 1. Dependency Bootstrap
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py
**Functions:** `bootstrap_dependencies()`, `import_runtime_dependencies()`, `verify_system_dependencies()`
**Why:** Correctly implements 4-phase bootstrap (A-D)
**Dependencies:** importlib, subprocess, sys.executable
**Known Limitations:** Requires Linux/Colab environment for apt-get

### 2. FirstFreeBroker
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py
**Functions:** `FirstFreeBroker.acquire()`, `FirstFreeBroker.release()`
**Why:** Correct monotonic sequence + heapq preserves release order
**Dependencies:** heapq, threading.Lock
**Known Limitations:** Thread-safe via lock, but not async-native

### 3. Chrome Driver Creation
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py
**Functions:** `create_gemini_driver(tid)`, `create_wmr_chrome_driver(worker_id)`
**Why:** Profile cloning, CDP injection, Chrome-only
**Dependencies:** selenium.webdriver.Chrome, ChromeOptions
**Known Limitations:** Requires Chrome binary on system

### 4. Login Detection
**Source:** google_login_raw.py
**Functions:** `comprehensive_login_check()`, all `is_logged_in_method_X()` functions
**Why:** 7 methods with confidence scoring, proven in Colab runtime
**Dependencies:** selenium, re
**Known Limitations:** Requires Google page to load

### 5. CDP Download Tracking
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py
**Functions:** `set_tab_download_dir()`, `Browser.setDownloadBehavior`
**Why:** GUID-based tracking, not filename-based
**Dependencies:** Chrome CDP, Browser.setDownloadBehavior
**Known Limitations:** Requires Chrome with CDP support

### 6. DownloadRegistry
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py, FULL_QUEUE_WORKER_V15_FORENSIC_REBUILT.py
**Functions:** `DownloadRegistry.register_guid()`, `update_progress()`
**Why:** Thread-safe GUID -> job_id mapping
**Dependencies:** threading.Lock
**Known Limitations:** In-memory only, not persistent

### 7. ECOM Browser Operations
**Source:** ecom_source.py
**Functions:** `switch_to_flash()`, `click_plus_button()`, `handle_login()`
**Why:** Most mature DOM operations, proven in Colab
**Dependencies:** selenium, pyvirtualdisplay
**Known Limitations:** ECOM-specific, not general Gemini operations

### 8. Entrypoint Pattern
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py
**Functions:** `is_running_in_notebook()`, Colab/Standalone entrypoint
**Why:** Correct dual-mode Colab/standalone support
**Dependencies:** IPython detection
**Known Limitations:** Colab-specific patterns

### 9. resolve_future_once
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py
**Functions:** `resolve_future_once(loop, future, result, is_exception)`
**Why:** Thread-safe future resolution via `loop.call_soon_threadsafe()`
**Dependencies:** asyncio event loop
**Known Limitations:** Only works if loop is running

### 10. Job State Machine
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py
**Functions:** `JobState` class, `JobContext.transition()`
**Why:** 19 states covering full pipeline
**Dependencies:** None
**Known Limitations:** State names vary slightly between versions

### 11. Directory Structure Functions
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py
**Functions:** `get_chrome_job_dir()`, `get_wmr_job_dir()`, `get_wmr_staging_dir()`, `get_final_output_dir()`
**Why:** Consistent directory management
**Dependencies:** pathlib.Path
**Known Limitations:** Hardcoded /content paths

### 12. Startup Functions
**Source:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py
**Functions:** `start_display()`, `start_vnc()`, `start_novnc_tunnel()`
**Why:** Complete virtual display setup for Colab
**Dependencies:** pyvirtualdisplay, x11vnc, websockify, fluxbox
**Known Limitations:** Linux/Colab only
"""
write_report("PRESERVE_LOGIC.md", preserve)
print("Phase 14-19 done")
