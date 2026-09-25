# Preserve Logic

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
