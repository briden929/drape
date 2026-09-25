# DO NOT COPY

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
**Code:** Encoding artifacts like `\x8f`, `\x90` in strings
**Why:** Corrupted source, not valid UTF-8
**Evidence:** clean_mojibake.py exists specifically to fix this

### 14. Production `except: pass`
**Files:** Various
**Code:** Bare `except: pass` blocks that silently swallow all exceptions
**Why:** Masks all errors, makes debugging impossible
**Evidence:** Known historical problem in task instructions
