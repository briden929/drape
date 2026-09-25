# Source Lineage

## Version History Graph

```
V3 (2024-08)
  |
  v
V4 -> V5 -> V6 -> V7 -> V8 (2024-09)
  |
  v
V9 (2024-09) -> V9.1
  |
  v
V10 (2024-09)
  |
  v
V11 (2024-09) -- Browser operation basis, T0-T3 Gemini
  |
  v
V12 (2024-09) -- Added queue logic, WMR W0-W3
  |
  v
V13 (2024-09) -- Added R2, DB, credits pipeline
  |
  v
V14 (2024-09-24) -- Chrome-only, dependency bootstrap
  |
  +---> V14 FINAL (3521 lines) -- Full production candidate
  |         - 4-phase bootstrap (A-D)
  |         - FirstFreeBroker with heapq
  |         - CDP download tracking
  |         - BullMQ/R2/DB/credits pipeline
  |         - Asyncio/Colab support
  |         - Duplicate function issues
  |
  +---> V14 N2N FINAL (3758 lines) -- Refactored N2N
            - Cleanest architecture
            - Most complete state machine
            - FirstFreeBroker with seq+heapq
            - CDP setDownloadBehavior (allowAndName)
            - Resource lifecycle separation
            - Thread-safe asyncio patterns
  |
  v
V15 FORENSIC REBUILT (377 lines) -- Current skeleton
  - Dependency bootstrap: COMPLETE
  - FirstFreeBroker: COMPLETE
  - DownloadRegistry: COMPLETE
  - JobContext/JobState: COMPLETE
  - Real Selenium: MISSING (mock)
  - BullMQ connection: MISSING
  - R2/DB/credits: MISSING (stubs)
  - Chrome driver creation: MISSING (mock)
```

## Feature Introduction Timeline

### V9
- Chrome-only architecture (initial)
- Basic worker pool concept
- Simple download handling

### V10
- Added queue logic
- BullMQ integration attempt
- Redis connection

### V11
- Gemini T0-T3 persistent browser resources
- First-Free scheduling concept
- Chrome profile management
- Cookie persistence

### V12
- WMR W0-W3 profiles introduced
- 2 tabs per profile
- Global First-Free scheduling
- Download registry concept

### V13
- R2 upload pipeline
- Database state transitions
- Credits settlement
- Clean AST extraction

### V14
- 4-phase dependency bootstrap
- CDP `Browser.setDownloadBehavior` with `allowAndName`
- Download GUID correlation via `Browser.downloadWillBegin`
- Chrome-only enforcement
- Thread-safe asyncio patterns
- `resolve_future_once` for thread-safe future resolution
- State machine with 19 states

### V14 N2N FINAL (Best Architecture)
- Clean 4-phase bootstrap (A-D)
- `FirstFreeBroker` with `heapq` + `threading.Lock` + monotonic sequence
- `JobContext` with `future` parameter for async resolution
- `resolve_future_once` for thread-safe future resolution
- CDP download tracking with `Browser.setDownloadBehavior`
- `set_tab_download_dir` for per-tab download directories
- `create_gemini_driver` with profile cloning
- `create_wmr_chrome_driver` with isolated profiles
- `get_chrome_job_dir`, `get_wmr_job_dir`, `get_wmr_staging_dir`, `get_final_output_dir`
- `start_display`, `start_vnc`, `start_novnc_tunnel`
- `startup_preflight`, `is_running_in_notebook`
- Complete state machine from QUEUED to COMPLETED
- `process_bullmq_job` as main job handler
- Failure isolation patterns

### V15 FORENSIC REBUILT (Current Skeleton)
- `bootstrap_dependencies()`: Complete Phase A-C bootstrap
- `FirstFreeBroker`: Complete with `asyncio.Queue()`
- `DownloadRegistry`: Complete GUID mapping
- `JobContext`: Complete with 19 state transitions
- `process_gemini()`: Skeleton (mock, needs real Selenium)
- `process_wmr()`: Skeleton (mock, needs real Selenium)
- `process_downstream()`: Stubs (needs real R2/DB/credits)
- Entrypoint: Colab/Standalone routing

## Source Lineage Proof

The V14 N2N Final was produced from:
1. V11 source (`v11_raw.py`, `v11_work.py`) via `build_v11.py`
2. V13 extraction (`v13_clean_ast.py`, `v13_clean_top.py`) via `gen_v14_clean_2/3/4.py`
3. N2N rebuild via `build_n2n_v1.py` -> `build_n2n_v2.py` -> `refactor_n2n_v15.py`
4. Final assembly via `create_final.py`

Patches applied to V14 N2N:
- `apply_patch.py` (main patch framework)
- `apply_v14_fixes.py` (V14 specific fixes)
- `apply_login.py` (login patch)
- Various `fix_*.py` scripts

The V15 Forensic Rebuilt was produced from:
1. V14 N2N architecture analysis
2. `V14_FINAL_REBUILD_BLUEPRINT.md` specifications
3. `write_chunks.py` to produce chunk-based assembly
4. `FULL_QUEUE_WORKER_V15_FORENSIC_REBUILT_PHASE12_BASELINE.py` as intermediate
