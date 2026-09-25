blueprint = """# V14 FINAL REBUILD BLUEPRINT

This blueprint specifies the intended, strictly evidence-based architecture for the final End-to-End (N2N) rebuilt production worker (`FULL_QUEUE_WORKER_V15_FORENSIC_REBUILT.py`), replacing the fragmented V11/V12/V13/V14 patches.

## A. Startup Sequence
1. **Dependency Bootstrap:** Minimal imports only. Run `sys.executable -m pip install` for missing packages.
2. **Environment Preflight:** Detect Colab vs Standalone. Verify directories and xvfb/vnc dependencies.
3. **Third-Party Imports:** `selenium`, `bullmq`, `psycopg2`, `boto3`, etc.
4. **Backend Connections:** Init Redis, Supabase DB pool, Boto3 R2 client.
5. **Worker Pools Initialization:** Init `GeminiWorkerPool` (T0-T3) and `WmrWorkerPool` (W0-W3).
6. **BullMQ Worker:** Attach worker to event loop.

## B. Dependency Bootstrap
- **Rule:** Do not import `selenium`, `PIL`, or `bullmq` at the top of the file.
- **Execution:** Check `importlib.util.find_spec`. If missing, `subprocess.run([sys.executable, "-m", "pip", "install", ...])`.
- **Cache:** `importlib.invalidate_caches()` before performing real imports.

## C. Environment Preflight
- Create structured job directories (`/content/downloads/chrome/T[0-3]`, `/content/downloads/wmr/W[0-3]`, etc.).
- Ensure Google Chrome binary is installed (do NOT install Microsoft Edge).
- Clear stale `SingletonLock` ONLY if no live Chrome process holds them.

## D. Chrome Initialization
- **Chrome Only:** Absolutely no Microsoft Edge.
- **Arguments:** `--user-data-dir`, `--no-sandbox`, `--disable-dev-shm-usage`.
- **CDP Tracking:** Attach CDP for download tracking via `Browser.setDownloadBehavior` (allowAndName).

## E. Gemini T0-T3 Initialization
- **Lazy Creation:** T profiles are generated when first assigned.
- **Persistence:** The Chrome window and Gemini application tab stay open indefinitely.
- **Profile:** Independent `chrome_profile/T[0-3]` dirs.

## F. WMR W0-W3 Initialization
- **Profiles:** 4 independent WMR profiles (`W0-W3`).
- **Persistence:** Shared across multiple WMR tasks.
- **Thread Safety:** A dedicated background thread is assigned per WMR driver. Async tasks communicate via thread-safe queues.

## G. WMR Tabs
- **Count:** 2 logical tabs per WMR profile (e.g., `W0-T0`, `W0-T1`).
- **Total Capacity:** 8 concurrent WMR physical processes.

## H. First-Free Brokers
- **Algorithm:** Real "First-Free-Wins" ordered sequence via `asyncio.Queue` or Monotonic Sequence tracker.
- **Gemini:** `T0`, `T1`, `T2`, `T3` released in order of download start.
- **WMR:** `W0-T0` through `W3-T1` released in order of download start.
- **Never:** Search by lowest ID first if it violates release order.

## I. BullMQ Admission
- Job enters worker. Payload extracted (`prompt`, `job_id`, `attachments`).
- Job isolated in `JobContext`.

## J. Job State Machine
- `QUEUED` -> `GEMINI_RESERVED` -> `GEMINI_GENERATING` -> `RAW_DOWNLOAD_START` -> `GEMINI_RELEASED` -> `RAW_DOWNLOADING` -> `RAW_READY` -> `RAW_VALIDATED` -> `WMR_QUEUED` -> `WMR_RESERVED` -> `WMR_PROCESSING` -> `WMR_DOWNLOAD_START` -> `WMR_RELEASED` -> `CLEAN_READY` -> `WEBP_READY` -> `R2_READY` -> `DB_FINALIZING` -> `DB_READY` -> `CREDITS_SETTLED` -> `COMPLETED`.

## K. Download Registry
- **Global dict/registry:** Maps `GUID -> JobContext`.
- **Never use:** `newest_file` or `glob.glob` correlation. Only GUID.

## L. CDP Event Flow
- Intercept `Browser.downloadWillBegin`. Extract `guid`, `suggestedFilename`.
- Intercept `Browser.downloadProgress`. Extract `state` (`completed`, `inProgress`).

## M. Raw Download Pipeline
- Once `Browser.downloadWillBegin` fires in Gemini -> Fire event -> Release `T` resource.
- Wait for `guid` state to reach `completed`.
- Validate file size stability + PIL Validation.

## N. WMR Pipeline
- Acquire `WMR` tab.
- Upload validated RAW image. Verify DOM processing.
- Click exact WMR "Download PNG".
- Wait for CDP `downloadWillBegin` -> Release `WMR` resource.

## O. WebP
- `PIL.Image.open(clean_png_path).convert("RGB").save(webp_path, "WEBP", quality=90)`.
- Validate bytes post-save.

## P. R2
- Uses `boto3` injected via `os.environ` secrets. Uploads WebP payload. Returns absolute URL.

## Q. DB
- Uses `psycopg2` threaded connection pool. Idempotent `UPDATE` queries for completion.

## R. Credits
- Run Postgres `decrement_credits` only if final pipeline stage is successful. Do NOT settle if WMR fails.

## S. BullMQ Completion
- Only returns `return {"status": "completed"}` after Credits and DB are fully committed.

## T. Failure Isolation
- Error in Job A MUST NOT crash Worker.
- Error in T0 MUST NOT kill T1, T2, T3.

## U. Browser Recovery
- Health check ping on `driver`. If `WebDriverException`, gracefully `quit()` and recreate ONLY that T driver.

## V. Login Recovery
- Implement State Machine Auth (Google Auth Check + Gemini App Check).
- If challenge/logout detected mid-job, pause job, run `google login.py` logic for that specific T profile, resume.

## W. Asyncio/Colab
- Prevent `RuntimeError: asyncio.run() cannot be called from a running event loop`.
- Use `WORKER_MAIN_TASK = loop.create_task(main())` in Notebooks. Add `done_callback` for exception surfacing.

## X. Standalone Execution
- Standard `asyncio.run(main())` block if `__name__ == "__main__"` outside Jupyter.

## Y. Shutdown
- Catch `KeyboardInterrupt` / `SIGINT`. Cancel `WORKER_MAIN_TASK`. Gracefully `driver.quit()` all active profiles to release `SingletonLock`s.

## Z. Testing Strategy
- Unit test auth state machine (False Positives on generic URL).
- Mock CDP download to verify immediate resource release.
- End-to-End Chrome launch in staging environment before prod release.
"""

with open(r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\V14_FINAL_REBUILD_BLUEPRINT.md", "w", encoding="utf-8") as f:
    f.write(blueprint)
