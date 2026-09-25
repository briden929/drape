
import os

bullmq_content = '''# BullMQ & Redis Forensics
This document details how this architecture integrates **BullMQ** and **Redis** for job queueing and orchestration.

## Enqueueing & Dequeueing Flow
- The worker uses the official Python `bullmq` library (`from bullmq import Worker, Queue`).
- A `Worker` is initialized using a Redis connection (`REDIS_TUNNEL_URL` or `REDIS_URL`) listening on a predefined `QUEUE_NAME` (with an optional `REDIS_KEY_PREFIX`). 
- Jobs are polled and handed to an `async def process_bullmq_job(job)` callback.

## Orchestration Strategy
1. **Per-Job Isolation:** 
   When `process_bullmq_job` receives a task, it doesn't block the BullMQ task worker continuously on CPU-bound logic.
   Instead, it immediately creates an `asyncio.Future()` wrapped in a `JobContext`.
   It schedules an asynchronous state machine: `asyncio.create_task(process_job_pipeline(ctx))`.
2. **State Machine (`process_job_pipeline`):**
   - The pipeline is an async loop that transitions the job across states (e.g., `QUEUED`, `GEMINI_ASSIGNED`, `WMR_QUEUED`, etc.).
   - Concurrency is bounded by custom semaphore logic (`GEMINI_BROKER.acquire()`, `WMR_BROKER.acquire()`).
3. **Execution Thread:**
   Once a slot in the `GeminiPool` is leased, the `GeminiWorker.process_job` is invoked.
   Crucially, this spawns a *dedicated daemon thread* (`_process_job_thread`) to safely run synchronous, blocking Selenium WebDriver operations outside the main asyncio loop.
4. **Completion:**
   - Eventual completion is awaited via `await asyncio.wait_for(fut, timeout=TOTAL_JOB_TIMEOUT_S)`. 
   - A `TimeoutError` correctly transitions the job context to `FAILED` and fails the BullMQ task.

## Strengths
- **Decoupled execution:** The architecture isolates slow, sync WebDriver code (in threads) from async lifecycle polling.
- **Fail-safe timeouts:** Strict timeouts are set against the global asyncio future.

## Weaknesses & Vulnerabilities
- Using infinite polling (`while True: await asyncio.sleep(...)`) in `process_job_pipeline` is suboptimal compared to `asyncio.Event` mechanics, leading to unnecessary CPU wakeups.
- Broker semaphores aren't strictly tied to `try-finally` structures in all edge cases around the pipeline loop, theoretically risking resource leaks if abrupt external cancellations occur on the tasks.
- Single thread handling `download_poller_loop` monitors all downloads sequentially based on `download_registry` iteration; this can cause delays if I/O checks (`st_size`) take too long.
'''

r2_db_content = '''# R2, DB & Credits Forensics

## Cloudflare R2 Upload Logic (`boto3`)
- Initialized in `_r2_client` utilizing `boto3.client('s3')` against Cloudflare R2 (`{ACCOUNT_ID}.r2.cloudflarestorage.com`).
- The method `upload_to_r2(png_path, webp_path, ...)` takes local paths and sequentially uploads them using `put_object(Body=f.read(), ContentType=...)`.
- On success, it synthesizes public URLs using the provided `R2_PUBLIC_URL` variable.
- Returns `(png_url, webp_url)`.
- If uploading throws a boto3 error, it does not retry (it catches `Exception as e` inside `upload_to_r2`, logs it, and returns `(None, None)`). The caller then raises an Exception which propagates up to `_finalize_job`, failing the job entirely.

## PostgreSQL DB Strategy (`psycopg2`)
- The pipeline uses `db.connection()` and `connection.cursor()` with context managers (`with db.connection() as conn:`).
- Inside `_finalize_job(ctx)`, once R2 is ready, it runs:
  `UPDATE generations SET output_url = %s, webp_url = %s, status = 'completed', updated_at = NOW() WHERE id = %s`
- **Fallback Logic:** If the initial DB query fails, there is a hardcoded 1-second `time.sleep(1)` followed by a single retry. 
- The DB operations are performed within an async task (under `await asyncio.to_thread(_finalize_job, ctx)`), ensuring DB latency does not block the asyncio main loop.

## Credits Settlement
- Following a successful R2 upload AND Database update, `credits.settle(ctx.user_id, ctx.generation_id)` is invoked.
- This invokes logic inside the `credits.py` module to finalize the financial ledger of the generation.
- **Vulnerability / Intentional Grace:** This call is wrapped in a generic `try-except`. If settlement fails (e.g. timeout or DB issue in the credits module), a warning is logged (`"Credits settle warning: ..."`), but the script *does not* revert the job or DB status. The user gets the image, but the ledger might drift.
'''

guid_content = '''# Download Ownership Analysis

This project integrates Chrome's native downloads (from headless Selenium tabs driving Gemini and Pixelcut) using the Chrome DevTools Protocol (`Page.setDownloadBehavior`). 

## GUID Lifecycle
1. The framework sets the base download path to a dedicated, thread/pool-isolated folder (e.g. `/content/downloads/chrome_staging/T0` or `/content/downloads/wmr_staging/W1`).
2. Prior to clicking a download button inside a tab, the system takes an inventory of the folder (`files_before = set(staging_dir.iterdir())`).
3. After the click, it hooks into CDP performance logs looking for the `Browser.downloadWillBegin` event to parse the structural **GUID** of the download. 
4. The framework concurrently monitors the filesystem for new files using generic masking (`endswith('.crdownload')` or image extensions).
5. On detection, it injects a tracking object into the global `download_registry` containing: `guid` (from CDP or a fallback string), `ctx` (JobContext), and `files_before`.

## Downloader Resolution & The Poller
The asynchronous poller `poll_active_downloads` scans `download_registry`. 
Instead of operating strictly upon specific downloaded filenames linked to the CDP GUID, the logic employs a **diffing approach**:
```python
cur = set(staging_dir.iterdir())
new_files = cur - files_before
```
It looks for any file inside `new_files` lacking `.crdownload`.
It checks completion by comparing file sizes half a second apart (`sz1 == sz2`).

## Identified Weaknesses & Failure Modes

1. **Filename Matching over GUID tracking:** 
   The most glaring flaw is that the system parses the `dl_guid` from Chrome but completely discards its utility on the filesystem side. It *registers* under the GUID logic (`download_registry[dl_guid]`), but the poller resolves completion solely via `set() - files_before` diffing. If an unrelated file drops into the staging directory concurrently, it might prematurely trigger validation or steal the focus.
2. **Race condition with Fallback IDs:** 
   If the `Browser.downloadWillBegin` event is missed in the CDP logs (they cycle fast), it defaults to `f'fs_fallback_{job_id}'`. Multiple fallbacks could theoretically collide or mask failures if job IDs are not perfectly unique per worker space.
3. **Ghost Files (Unfinished crdownloads):**
   If a download actually fails halfway through (Chrome drops it) but the `.crdownload` renames to a partial `.png`, the framework only validates against a `.stat().st_size` check between 0.5s ticks. It delegates the true corruption test to `validate_image_file()`, which might fail and crash the job context abruptly. 
4. **Staging Directory Isolation Failure:**
   The `files_before` subtraction relies purely on the assumption that nothing else will write to `staging_dir`.
5. **No Cleanup on Timeout:** 
   If a download times out (checked via `time.time() - dinfo['started_at'] > DOWNLOAD_TIMEOUT_S`), it transitions the job state to `FAILED`, removes the GUID from the registry, but leaves the orphaned partial files cluttering the staging directory forever.
'''

with open("C:/Users/PC/.gemini/antigravity/scratch/Reddis/BULLMQ_REDIS_FORENSICS.md", "w", encoding="utf-8") as f:
    f.write(bullmq_content)

with open("C:/Users/PC/.gemini/antigravity/scratch/Reddis/R2_DB_CREDITS_FORENSICS.md", "w", encoding="utf-8") as f:
    f.write(r2_db_content)

with open("C:/Users/PC/.gemini/antigravity/scratch/Reddis/DOWNLOAD_OWNERSHIP_ANALYSIS.md", "w", encoding="utf-8") as f:
    f.write(guid_content)

