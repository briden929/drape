import asyncio
import threading
import queue
import time
import base64
import uuid
import traceback
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from bullmq import Worker, Job

# ============================================================================
# STEP 11 — RESOURCE BROKERS
# ============================================================================

class FirstFreeBroker:
    def __init__(self, name: str, resource_ids: list):
        self.name = name
        self.resource_ids = resource_ids
        self._q = asyncio.Queue()
        self.owners = {}
        for rid in resource_ids:
            self._q.put_nowait(rid)
            self.owners[rid] = None

    async def acquire(self, job_id: str) -> str:
        print(f"[BROKER][{self.name}] Job {job_id} waiting for resource...")
        rid = await self._q.get()
        self.owners[rid] = job_id
        print(f"[BROKER][{self.name}] ACQUIRE {rid} for job {job_id}")
        return rid

    def release(self, rid: str):
        job_id = self.owners.get(rid)
        if job_id is not None:
            self.owners[rid] = None
            self._q.put_nowait(rid)
            print(f"[BROKER][{self.name}] RELEASE {rid} (was job {job_id})")

GEMINI_BROKER = FirstFreeBroker("GEMINI", [f"T{i}" for i in range(4)])
WMR_BROKER = FirstFreeBroker("WMR", [f"W{i}-T{j}" for i in range(4) for j in range(2)])

# ============================================================================
# STEP 12 — DOWNLOAD MANAGER
# ============================================================================

class JobState(Enum):
    PENDING = "PENDING"
    GEMINI_RESERVED = "GEMINI_RESERVED"
    GEMINI_RUNNING = "GEMINI_RUNNING"
    RAW_WAITING = "RAW_WAITING"
    RAW_VALIDATED = "RAW_VALIDATED"
    WMR_RESERVED = "WMR_RESERVED"
    WMR_RUNNING = "WMR_RUNNING"
    CLEAN_WAITING = "CLEAN_WAITING"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    DB_SAVED = "DB_SAVED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobContext:
    def __init__(self, job_id: str, payload: dict):
        self.job_id = job_id
        self.payload = payload
        self.state = JobState.PENDING
        self.gemini_resource = None
        self.wmr_resource = None
        self.raw_png_path = None
        self.clean_png_path = None
        self.webp_path = None
        self.error = None
        self.state_event = asyncio.Event()
        self.completion_future = None
        
    def transition_sync(self, new_state: JobState):
        self.state = new_state
        print(f"[{self.job_id}] STATE -> {new_state.name}")
        self.state_event.set()
        
    async def wait_for_state(self, target_state: JobState, timeout=300):
        t0 = time.time()
        while self.state != target_state and self.state != JobState.FAILED:
            if time.time() - t0 > timeout:
                raise TimeoutError(f"Timeout waiting for state {target_state.name}")
            self.state_event.clear()
            await asyncio.wait_for(self.state_event.wait(), timeout=5.0)
        if self.state == JobState.FAILED:
            raise RuntimeError(f"Job failed while waiting for {target_state.name}: {self.error}")

class DownloadRecord:
    def __init__(self, job_id: str, guid: str, expected_filename: str, staging_dir: str, target_state: JobState, is_cdp: bool = False):
        self.job_id = job_id
        self.guid = guid
        self.expected_filename = expected_filename
        self.staging_dir = staging_dir
        self.target_state = target_state
        self.is_cdp = is_cdp

DOWNLOAD_REGISTRY = {}
JOB_CONTEXTS = {}

async def poll_downloads_loop():
    while True:
        try:
            for guid, rec in list(DOWNLOAD_REGISTRY.items()):
                ctx = JOB_CONTEXTS.get(rec.job_id)
                if not ctx or ctx.state == JobState.FAILED:
                    DOWNLOAD_REGISTRY.pop(guid, None)
                    continue
                    
                staging = Path(rec.staging_dir)
                if not staging.exists():
                    continue
                    
                completed_file = None
                
                # Check for completed file
                try:
                    for f in staging.iterdir():
                        if f.name == rec.expected_filename or f.name.startswith(rec.guid):
                            if not f.name.endswith(".crdownload"):
                                completed_file = f
                                break
                        if rec.is_cdp:
                            if not f.name.endswith(".crdownload"):
                                completed_file = f
                                break
                except Exception as e:
                    print(f"[DOWNLOAD_WATCHER] Error scanning directory for {guid}: {e}")
                    continue
                            
                if completed_file:
                    size_before = -1
                    stable = False
                    for _ in range(20):
                        try:
                            sz = completed_file.stat().st_size
                            if sz > 0 and sz == size_before:
                                stable = True
                                break
                            size_before = sz
                            await asyncio.sleep(0.1)
                        except Exception:
                            pass
                            
                    if stable:
                        try:
                            validate_image_file(str(completed_file))
                            print(f"[{rec.job_id}] DOWNLOAD_VALIDATED: {completed_file.name}")
                            if rec.target_state == JobState.RAW_VALIDATED:
                                ctx.raw_png_path = str(completed_file)
                            else:
                                ctx.clean_png_path = str(completed_file)
                                
                            ctx.transition_sync(rec.target_state)
                            DOWNLOAD_REGISTRY.pop(guid, None)
                        except Exception as e:
                            print(f"[{rec.job_id}] DOWNLOAD_VALIDATE_FAILED: {e}")
                            try:
                                completed_file.unlink(missing_ok=True)
                            except:
                                pass
        except Exception as e:
            print(f"[DOWNLOAD_WATCHER] Unhandled exception in loop: {e}")
        await asyncio.sleep(1.0)

# ============================================================================
# STEP 13 — GEMINI RESOURCE WORKERS
# ============================================================================

class GeminiWorker:
    def __init__(self, tid: str):
        self.tid = tid
        self.driver = None
        self.profile_dir = f"/content/downloads/chrome_profile_{tid}"
        self.staging_dir = f"/content/downloads/chrome_staging/{tid}"
        os.makedirs(self.profile_dir, exist_ok=True)
        os.makedirs(self.staging_dir, exist_ok=True)

    def _ensure_driver(self):
        if self.driver is None:
            opts = ChromeOptions()
            opts.add_argument(f"--user-data-dir={self.profile_dir}")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1920,1080")
            self.driver = uc.Chrome(options=opts, driver_executable_path=None, browser_executable_path="/usr/bin/google-chrome-stable")
            dl_dir_str = os.path.abspath(self.staging_dir)
            try:
                self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": dl_dir_str})
                self.driver.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": dl_dir_str, "eventsEnabled": True})
            except:
                pass

    def do_execute_sync(self, ctx: JobContext):
        """Runs sequentially inside a thread pool, completely blocking for this job's DOM work."""
        self._ensure_driver()
        prefix = f"[{self.tid}][{ctx.job_id}]"
        ctx.transition_sync(JobState.GEMINI_RUNNING)
        
        # 1. New Chat
        print(f"{prefix} Opening new chat...")
        open_new_chat_and_reload(self.driver, prefix)
        ensure_flash_mode(self.driver, prefix)
        ensure_create_image_mode(self.driver, prefix)
        
        # 2. Upload
        gen = ctx.payload
        prompt, garment_path, model_path, holo_path = resolve_prompt_and_refs(gen)
        refs = [garment_path]
        if model_path: refs.append(model_path)
        if holo_path: refs.append(holo_path)
        
        print(f"{prefix} Uploading {len(refs)} references...")
        open_upload_drawer(self.driver)
        click_upload_files_in_drawer(self.driver, prefix)
        inp = find_file_input_strict(self.driver, prefix)
        upload_reference_files(self.driver, inp, refs, prefix)
        verify_attachment_count(self.driver, len(refs), prefix)
        
        # 3. Prompt & Send
        editor = get_quill_editor(self.driver, prefix)
        _inject_prompt_atomic(self.driver, editor, prompt, prefix)
        _click_send_button(self.driver, prefix)
        
        # 4. Wait for processing
        print(f"{prefix} Wait generation start...")
        verify_generation_started(self.driver, prefix)
        print(f"{prefix} Generating...")
        
        t_start = time.time()
        while time.time() - t_start < 240:
            if not _is_gemini_processing(self.driver):
                check_gemini_error(self.driver, prefix)
                check_text_error(self.driver, prefix)
                if _has_generated_image(self.driver):
                    break
            time.sleep(2)
        else:
            raise TimeoutError("Gemini generation timed out (240s)")
            
        print(f"{prefix} Generation complete. Hovering & downloading...")
        urls_before = snapshot_urls(self.driver)
        
        # 5. Download Interaction
        hover_ok = _hover_and_dl_single_click(self.driver, prefix)
        dl_guid = None
        is_cdp = False
        
        if hover_ok:
            # Capture GUID via CDP
            t_dl = time.time()
            while time.time() - t_dl < 15:
                for entry in self.driver.get_log('performance'):
                    try:
                        msg = json.loads(entry['message'])['message']
                        if msg['method'] == 'Browser.downloadWillBegin':
                            dl_guid = msg['params']['guid']
                            break
                    except:
                        pass
                if dl_guid:
                    break
                time.sleep(0.1)
                
            if dl_guid:
                print(f"{prefix} DOWNLOAD_WILL_BEGIN guid={dl_guid}")
            else:
                dl_guid = f"fs_fallback_{ctx.job_id}"
                print(f"{prefix} DOWNLOAD_WILL_BEGIN timeout, using fallback {dl_guid}")
        else:
            # CDP direct fallback
            print(f"{prefix} Hover DL failed, attempting direct CDP fallback...")
            fallback_path = os.path.join(self.staging_dir, f"cdp_direct_{ctx.job_id}.png")
            if _direct_fetch_cdp(self.driver, fallback_path, urls_before):
                dl_guid = f"cdp_direct_{ctx.job_id}"
                is_cdp = True
                print(f"{prefix} CDP_FALLBACK_CAPTURE successful")
            else:
                raise RuntimeError("Failed to download image (hover & CDP both failed)")
                
        # Register for download watcher
        expected_filename = f"{ctx.job_id}.png"
        rec = DownloadRecord(ctx.job_id, dl_guid, expected_filename, self.staging_dir, JobState.RAW_VALIDATED, is_cdp=is_cdp)
        DOWNLOAD_REGISTRY[dl_guid] = rec
        ctx.transition_sync(JobState.RAW_WAITING)

GEMINI_WORKERS = {f"T{i}": GeminiWorker(f"T{i}") for i in range(4)}
GEMINI_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="Gemini")

# ============================================================================
# STEP 14 — WMR OWNER THREADS
# ============================================================================

class WmrDriverThread(threading.Thread):
    def __init__(self, pid: str):
        super().__init__(name=pid)
        self.pid = pid
        self.command_queue = queue.Queue()
        self.driver = None
        self.daemon = True
        
    def _ensure_driver(self):
        if self.driver is None:
            self.driver = create_wmr_chrome_driver(self.pid)
            self.driver.get("https://www.watermarkremover.io/upload")
            ensure_wmr_session(self.driver)

    def run(self):
        while True:
            cmd, ctx, w_tid = self.command_queue.get()
            if cmd == "EXECUTE":
                try:
                    self._do_execute(ctx, w_tid)
                except Exception as e:
                    print(f"[{w_tid}][{ctx.job_id}] WMR execution failed: {e}")
                    ctx.error = e
                    ctx.transition_sync(JobState.FAILED)
                finally:
                    WMR_BROKER.release(w_tid)

    def _do_execute(self, ctx: JobContext, w_tid: str):
        self._ensure_driver()
        prefix = f"[{w_tid}][{ctx.job_id}]"
        ctx.transition_sync(JobState.WMR_RUNNING)
        
        staging_dir = get_wmr_staging_dir(self.pid)
        
        _wmr_expose_file_inputs(self.driver)
        file_input = _wmr_find_file_input(self.driver)
        file_input.send_keys(os.path.abspath(ctx.raw_png_path))
        print(f"{prefix} Uploaded RAW to WMR")
        
        _wmr_check_status(self.driver, prefix)
        
        # Click download and detect GUID
        _wmr_click_download(self.driver, prefix)
        dl_guid = None
        t_dl = time.time()
        while time.time() - t_dl < 15:
            for entry in self.driver.get_log('performance'):
                try:
                    msg = json.loads(entry['message'])['message']
                    if msg['method'] == 'Browser.downloadWillBegin':
                        dl_guid = msg['params']['guid']
                        break
                except:
                    pass
            if dl_guid:
                break
            time.sleep(0.1)
            
        if not dl_guid:
            dl_guid = f"wmr_fs_fallback_{ctx.job_id}"
            
        print(f"{prefix} WMR_DOWNLOAD_START_CONFIRMED guid={dl_guid}")
        
        expected_filename = f"{ctx.job_id}_clean.png"
        rec = DownloadRecord(ctx.job_id, dl_guid, expected_filename, staging_dir, JobState.CLEAN_READY)
        DOWNLOAD_REGISTRY[dl_guid] = rec
        ctx.transition_sync(JobState.CLEAN_WAITING)
        
        # Cleanup DOM for next upload
        try:
            self.driver.execute_script("document.querySelectorAll('.upload-card').forEach(e => e.remove());")
        except:
            pass

WMR_THREADS = {}
for i in range(4):
    pid = f"W{i}"
    t = WmrDriverThread(pid)
    t.start()
    WMR_THREADS[pid] = t

# ============================================================================
# STEP 15 — PIPELINE SCHEDULER
# ============================================================================

async def execute_pipeline(ctx: JobContext):
    try:
        # 1. Gemini Phase
        tid = await GEMINI_BROKER.acquire(ctx.job_id)
        ctx.gemini_resource = tid
        ctx.transition_sync(JobState.GEMINI_RESERVED)
        
        loop = asyncio.get_running_loop()
        worker = GEMINI_WORKERS[tid]
        
        try:
            await loop.run_in_executor(GEMINI_EXECUTOR, worker.do_execute_sync, ctx)
            await ctx.wait_for_state(JobState.RAW_VALIDATED)
        finally:
            GEMINI_BROKER.release(tid)
            
        # 2. WMR Phase
        w_tid = await WMR_BROKER.acquire(ctx.job_id)
        ctx.wmr_resource = w_tid
        ctx.transition_sync(JobState.WMR_RESERVED)
        
        pid = w_tid.split("-")[0]
        WMR_THREADS[pid].command_queue.put(("EXECUTE", ctx, w_tid))
        
        await ctx.wait_for_state(JobState.CLEAN_READY)
        
        # 3. Post-Processing Phase
        ctx.webp_path = f"/content/downloads/final_output/{ctx.job_id}.webp"
        os.makedirs(os.path.dirname(ctx.webp_path), exist_ok=True)
        import subprocess
        subprocess.run(['cwebp', '-q', '80', ctx.clean_png_path, '-o', ctx.webp_path], capture_output=True)
        if not os.path.exists(ctx.webp_path):
            from PIL import Image
            with Image.open(ctx.clean_png_path) as img:
                img.save(ctx.webp_path, "WEBP", quality=80)
        validate_image_file(ctx.webp_path)
        ctx.transition_sync(JobState.WEBP_READY)
        
        # 4. Save to DB
        import sys
        target_user_id = ctx.payload.get("userId", "system")
        if "fashion_studio" in sys.modules:
            fs = sys.modules["fashion_studio"]
            res = fs.upload_and_record(
                image_path=ctx.clean_png_path,
                webp_path=ctx.webp_path,
                user_id=target_user_id,
                generation_id=ctx.job_id,
                model_id=ctx.payload.get('model_id'),
                catalogue_item_id=ctx.payload.get('catalogue_item_id')
            )
            credits_settle_look(target_user_id, ctx.payload.get('credits_cost', 0))
            print(f"[{ctx.job_id}] Upload successful: {res}")
        
        ctx.transition_sync(JobState.COMPLETED)
        if ctx.completion_future:
            ctx.completion_future.set_result(True)
            
    except Exception as e:
        print(f"[{ctx.job_id}] PIPELINE FAILED: {traceback.format_exc()}")
        ctx.error = e
        ctx.transition_sync(JobState.FAILED)
        try:
            record_dead_letter(ctx.payload, str(e), 1, 1, traceback.format_exc())
            credits_refund_look(ctx.payload.get("userId", "system"), ctx.payload.get("credits_cost", 0))
        except Exception as dle:
            print(f"[{ctx.job_id}] Failed to record dead letter: {dle}")
            
        if ctx.completion_future:
            ctx.completion_future.set_exception(e)

INTERNAL_JOB_QUEUE = asyncio.Queue()

async def central_scheduler_loop():
    while True:
        ctx = await INTERNAL_JOB_QUEUE.get()
        asyncio.create_task(execute_pipeline(ctx))

# ============================================================================
# STEP 16 — BULLMQ WORKER
# ============================================================================

async def process_bullmq_job(job: Job, job_token: str):
    job_id = job.id
    print(f"\n[{job_id}] ======================================================")
    print(f"[{job_id}] BULLMQ JOB RECEIVED")
    print(f"[{job_id}] ======================================================\n")
    
    gen = fetch_generation(job_id)
    if not gen:
        raise ValueError(f"Generation {job_id} not found in DB")
        
    ctx = JobContext(job_id=job_id, payload=gen)
    JOB_CONTEXTS[job_id] = ctx
    
    loop = asyncio.get_running_loop()
    ctx.completion_future = loop.create_future()
    
    await INTERNAL_JOB_QUEUE.put(ctx)
    return await ctx.completion_future

# ============================================================================
# STEP 18 — COLAB RUNTIME SUPERVISOR
# ============================================================================

async def main():
    asyncio.create_task(poll_downloads_loop())
    asyncio.create_task(central_scheduler_loop())
    
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    queue_name = os.environ.get('QUEUE_NAME', 'vastralook-queue')
    prefix = os.environ.get('REDIS_KEY_PREFIX', 'vastralook:')
    
    from urllib.parse import urlparse
    u = urlparse(redis_url)
    opts = {"host": u.hostname or "localhost", "port": u.port or 6379}
    if u.password:
        opts["password"] = u.password
    if u.scheme == 'rediss':
        opts["tls"] = {}
        
    worker = Worker(queue_name, process_bullmq_job, {"connection": opts, "prefix": prefix})
    print(f"\n[BOOT] BullMQ Worker started on {queue_name} (Prefix: {prefix})\n")
    
    # Block forever so Colab doesn't exit
    while True:
        await asyncio.sleep(3600)

def start_worker():
    print("\n" + "="*70)
    print("🚀 N2N WORKER INITIALIZATION (V15 ARCHITECTURE)")
    print("="*70 + "\n")
    try:
        loop = asyncio.get_running_loop()
        # In Jupyter, this just schedules the task. To actually keep it alive,
        # we would typically await it, but Jupyter manages the loop.
        loop.create_task(main())
        print("[BOOT] Worker task scheduled in Colab Event Loop.")
    except RuntimeError:
        asyncio.run(main())

if __name__ == "__main__":
    start_worker()
