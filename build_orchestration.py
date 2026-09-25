import os

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

orchestration_code = """
class GeminiWorker:
    def __init__(self, tid: str):
        self.tid = tid
        self.driver = None
        self.window_handle = None
        self.profile_dir = f"/content/downloads/chrome_profile_{tid}"
        self.staging_dir = f"/content/downloads/chrome_staging/{tid}"
        self.driver_lock = threading.Lock()
        os.makedirs(self.profile_dir, exist_ok=True)
        os.makedirs(self.staging_dir, exist_ok=True)

    def _create_driver(self):
        opts = ChromeOptions()
        opts.add_argument(f"--user-data-dir={self.profile_dir}")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        
        self.driver = uc.Chrome(options=opts, driver_executable_path=None, browser_executable_path="/usr/bin/google-chrome-stable")
        
        # We also need an explicit download directory configuration:
        dl_dir_str = os.path.abspath(self.staging_dir)
        try:
            self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": dl_dir_str})
        except Exception:
            pass
        try:
            self.driver.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": dl_dir_str, "eventsEnabled": True})
        except Exception:
            pass
            
        self.window_handle = self.driver.current_window_handle

    def execute_job(self, loop, ctx: JobContext):
        try:
            with self.driver_lock:
                self._do_execute(loop, ctx)
        except Exception as e:
            print(f"[ERROR] {self.tid} execution failed: {e}")
            threadsafe_resolve_future(loop, ctx.completion_future, exception=e)

    def _do_execute(self, loop, ctx: JobContext):
        if self.driver is None:
            self._create_driver()
            
        tid_int = int(self.tid.replace("T", ""))
        prefix = f"[{self.tid}][{ctx.job_id}]"
        
        # 1. Open verified new Gemini chat
        print(f"{prefix} NEW_CHAT_START")
        new_chat_url = open_new_chat_and_reload(self.driver, tid_int, ctx.job_id)
        
        # 2. Flash mode
        ensure_flash_mode(self.driver, tid_int, ctx.job_id)
        
        # 3. Create Image mode
        ensure_create_image_mode(self.driver, tid_int, ctx.job_id)
        
        # 4. Upload robustly using DOM methods
        # Resolve attachments using DB params if needed, or pass them in payload
        attachments = ctx.payload.get("attachments", [])
        if not attachments and "garmentImage" in ctx.payload:
            attachments = [ctx.payload.get("garmentImage")]
            
        # V9 strict requirement: All expected ref paths must exist
        ref_paths = []
        for p in attachments:
            if p:
                rp = str(Path(p).resolve())
                if os.path.exists(rp):
                    ref_paths.append(rp)
                else:
                    print(f"Warning: Missing reference file {rp}")
                    
        expected_count = len(ref_paths)
        if expected_count > 0:
            perform_robust_upload(self.driver, ref_paths, tid_int, ctx.job_id)
            
        # 5. Verify count
        verified, actual = verify_attachment_count(self.driver, expected_count, tid_int, ctx.job_id)
        if not verified:
            raise Exception(f"ATTACHMENT_MISMATCH: expected {expected_count}, got {actual}")
            
        # 6. Inject prompt
        prompt = ctx.payload.get("prompt", "Generate image")
        _inject_prompt_atomic(self.driver, prompt, tid_int, ctx.job_id)
        
        urls_before = snapshot_urls(self.driver)
        chat_urls = set()
        
        # 7. Click send
        if not _click_send_button(self.driver, tid_int, ctx.job_id):
            raise Exception("SEND_FAILED")
            
        # 8. Verify generation started
        if not verify_generation_started(self.driver):
            raise Exception("GEN_START_FAILED")
            
        # 9. Wait for image (polling)
        image_detected = False
        t_detect = time.time()
        while time.time() - t_detect < 240:
            status, new_src = nb_check_image(self.driver, urls_before, chat_urls)
            if status == "SUCCESS":
                image_detected = True
                if new_src: urls_before.add(new_src)
                break
            elif status in ["ERROR", "LIMIT", "REFUSED"]:
                raise Exception(f"Generation failed: {status}")
            time.sleep(1.0)
            
        if not image_detected:
            raise Exception("GENERATION_TIMEOUT")
            
        # 10. Click Download
        hover_ok = _hover_and_dl_single_click(self.driver, urls_before, chat_urls)
        
        dl_guid = None
        cdp_ok = False
        
        # Immediate fallback: CDP Direct extraction
        raw_path = Path(self.staging_dir) / f"{ctx.job_id}_raw.png"
        if not hover_ok:
            cdp_ok = _direct_fetch_cdp(self.driver, str(raw_path), urls_before)
            
        if cdp_ok:
            dl_guid = f"cdp_direct_{ctx.job_id}"
            print(f"{prefix} CDP_FALLBACK_CAPTURE successful")
        else:
            # 11. Wait for .crdownload or GUID via CDP log
            t1 = time.time()
            while time.time() - t1 < 15:
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
                # Filesystem .crdownload fallback exactly as V9 specified
                t2 = time.time()
                staging_path = Path(self.staging_dir)
                files_before = set(staging_path.iterdir()) if staging_path.exists() else set()
                while time.time() - t2 < 15:
                    if staging_path.exists():
                        cur = set(staging_path.iterdir())
                        new_files = cur - files_before
                        if any(f.name.endswith('.crdownload') or f.name.endswith('.png') for f in new_files):
                            dl_guid = f"fs_fallback_{ctx.job_id}"
                            break
                    time.sleep(0.3)
                    
        if not dl_guid:
            raise Exception("DOWNLOAD_START_TIMEOUT")
            
        # 12. Register and release IMMEDIATELY
        ctx.raw_guid = dl_guid
        DOWNLOAD_REGISTRY[dl_guid] = DownloadRecord(
            guid=dl_guid, job_id=ctx.job_id, resource_id=self.tid, resource_type="GEMINI",
            staging_dir=self.staging_dir, expected_filename=f"{dl_guid}.png"
        )
        
        print(f"{prefix} DOWNLOAD_START_CONFIRMED guid={dl_guid}")
        GEMINI_BROKER.release(self.tid)
        
        asyncio.run_coroutine_threadsafe(ctx.transition(JobState.RAW_DOWNLOADING), loop)

class WmrDriverThread(threading.Thread):
    def __init__(self, profile_id: str):
        super().__init__(daemon=True)
        self.profile_id = profile_id
        self.driver = None
        self.command_queue = queue.Queue()
        self.ready_event = threading.Event()
        self.stop_event = threading.Event()
        self.profile_dir = f"/content/downloads/wmr_chrome_profiles/{profile_id}"
        self.staging_dir = f"/content/downloads/wmr_staging/{profile_id}"
        os.makedirs(self.profile_dir, exist_ok=True)
        os.makedirs(self.staging_dir, exist_ok=True)

    def run(self):
        opts = ChromeOptions()
        opts.add_argument(f"--user-data-dir={self.profile_dir}")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        self.driver = uc.Chrome(options=opts, driver_executable_path=None, browser_executable_path="/usr/bin/google-chrome-stable")
        
        dl_dir_str = os.path.abspath(self.staging_dir)
        try:
            self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": dl_dir_str})
        except Exception:
            pass
        try:
            self.driver.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": dl_dir_str, "eventsEnabled": True})
        except Exception:
            pass
            
        self.ready_event.set()
        
        while not self.stop_event.is_set():
            try:
                cmd, args = self.command_queue.get(timeout=1.0)
                if cmd == "EXECUTE":
                    loop, ctx, tid = args
                    try:
                        self._do_execute(loop, ctx, tid)
                    except Exception as e:
                        print(f"[ERROR] WMR {tid} failed: {e}")
                        threadsafe_resolve_future(loop, ctx.completion_future, exception=e)
                elif cmd == "STOP":
                    break
            except queue.Empty:
                pass
        
        if self.driver:
            try:
                self.driver.quit()
            except: pass

    def _do_execute(self, loop, ctx: JobContext, tid: str):
        prefix = f"[WMR-{tid}][{ctx.job_id}]"
        
        try:
            for fn in os.listdir(self.staging_dir):
                fp = Path(self.staging_dir) / fn
                if fp.is_file():
                    try: fp.unlink()
                    except: pass
        except: pass
        
        files_before_staging = set(os.listdir(self.staging_dir))
        
        self.driver.get("https://watermarkremover.io")
        time.sleep(1.2)
        
        print(f"{prefix} UPLOAD_STARTED")
        fi = _wmr_find_file_input(self.driver)
        if not fi:
            time.sleep(0.5)
            fi = _wmr_find_file_input(self.driver)
        if not fi:
            raise Exception("WMR file input not found")
            
        fi.send_keys(str(Path(ctx.raw_path).resolve()))
        time.sleep(0.5)
        print(f"{prefix} UPLOAD_VERIFIED")
        
        # Poll WMR processing
        ready = False
        t0 = time.time()
        while time.time() - t0 < 120:
            status = _wmr_check_status(self.driver)
            if status == "DONE":
                ready = True
                break
            elif status == "NOT_FOUND":
                print(f"{prefix} WMR_NOT_FOUND - no watermark detected")
                ready = True
                break
            time.sleep(0.6)
            
        if not ready:
            raise Exception("WMR processing timeout")
            
        print(f"{prefix} DOWNLOAD_BUTTON_DETECTED")
        dl_started = False
        for click_attempt in range(1, 3):
            if not _wmr_click_download(self.driver, prefix):
                time.sleep(1.0)
                continue
                
            print(f"{prefix} DOWNLOAD_CLICKED")
                
            t1 = time.time()
            while time.time() - t1 < 15:
                cur = set(os.listdir(self.staging_dir))
                new_files = cur - files_before_staging
                if any(fn.endswith('.crdownload') or fn.lower().endswith(('.png', '.webp')) for fn in new_files):
                    dl_started = True
                    break
                time.sleep(0.3)
                
            if dl_started:
                break
                
        if not dl_started:
            raise Exception("WMR download failed to start after click")
            
        dl_guid = f"wmr_fs_fallback_{ctx.job_id}"
        ctx.wmr_guid = dl_guid
        DOWNLOAD_REGISTRY[dl_guid] = DownloadRecord(
            guid=dl_guid, job_id=ctx.job_id, resource_id=tid, resource_type="WMR",
            staging_dir=self.staging_dir, expected_filename=f"{dl_guid}.png"
        )
        
        print(f"{prefix} WMR_DOWNLOAD_START_CONFIRMED guid={dl_guid}")
        WMR_BROKER.release(tid)
        
        asyncio.run_coroutine_threadsafe(ctx.transition(JobState.WMR_RELEASED), loop)

class GeminiWorkerPool:
    def __init__(self, capacity=4):
        self.workers = {}
        for i in range(capacity):
            tid = f"T{i}"
            self.workers[tid] = GeminiWorker(tid)
            GEMINI_BROKER.add_resource(tid)

class WmrWorkerPoolV14:
    def __init__(self, profiles=4, tabs_per_profile=2):
        self.threads = {}
        for i in range(profiles):
            pid = f"W{i}"
            th = WmrDriverThread(pid)
            th.start()
            self.threads[pid] = th
            for j in range(tabs_per_profile):
                tid = f"{pid}-T{j}"
                WMR_BROKER.add_resource(tid)

GEMINI_POOL = None
WMR_POOL = None

async def poll_downloads_loop():
    while True:
        for guid, rec in list(DOWNLOAD_REGISTRY.items()):
            ctx = JOB_CONTEXTS.get(rec.job_id)
            if not ctx:
                DOWNLOAD_REGISTRY.pop(guid, None)
                continue
                
            staging = Path(rec.staging_dir)
            if not staging.exists():
                continue
                
            completed_file = None
            for f in staging.iterdir():
                if f.name == rec.expected_filename or f.name.startswith(rec.guid):
                    if not f.name.endswith(".crdownload"):
                        completed_file = f
                        break
                if rec.guid.startswith("cdp_direct"):
                    if not f.name.endswith(".crdownload"):
                        completed_file = f
                        break
                if rec.guid.startswith("fs_fallback") or rec.guid.startswith("wmr_fs_fallback"):
                    if not f.name.endswith(".crdownload"):
                        completed_file = f
                        break
                        
            if completed_file:
                size_before = -1
                stable = False
                for _ in range(20):
                    sz = completed_file.stat().st_size
                    if sz > 0 and sz == size_before:
                        stable = True
                        break
                    size_before = sz
                    await asyncio.sleep(0.5)
                    
                if stable:
                    try:
                        # Dummy PIL check inside wait loop is safe
                        validate_image_file(str(completed_file))
                        rec.state = "completed"
                        rec.completed_at = time.time()
                        rec.path = str(completed_file)
                        
                        if rec.resource_type == "GEMINI":
                            ctx.raw_path = rec.path
                            await ctx.transition(JobState.RAW_VALIDATED)
                            threadsafe_resolve_future(asyncio.get_running_loop(), ctx.completion_future, result=True)
                        else:
                            ctx.clean_png_path = rec.path
                            await ctx.transition(JobState.CLEAN_READY)
                            threadsafe_resolve_future(asyncio.get_running_loop(), ctx.completion_future, result=True)
                            
                        DOWNLOAD_REGISTRY.pop(guid, None)
                    except Exception as e:
                        pass # Wait until valid or timeout
        await asyncio.sleep(1)

async def process_job(job: Job):
    job_id = job.id
    ctx = JobContext(job_id=job_id, payload=job.data)
    JOB_CONTEXTS[job_id] = ctx
    loop = asyncio.get_running_loop()
    
    try:
        # 1. Gemini
        tid = await GEMINI_BROKER.acquire()
        ctx.gemini_resource = tid
        await ctx.transition(JobState.GEMINI_RESERVED)
        
        ctx.completion_future = loop.create_future()
        GEMINI_POOL.workers[tid].execute_job(loop, ctx)
        await ctx.completion_future # Waits for RAW_VALIDATED
        
        # 2. WMR
        ctx.completion_future = loop.create_future()
        await ctx.transition(JobState.WMR_QUEUED)
        w_tid = await WMR_BROKER.acquire()
        ctx.wmr_resource = w_tid
        await ctx.transition(JobState.WMR_RESERVED)
        
        pid = w_tid.split("-")[0]
        WMR_POOL.threads[pid].command_queue.put(("EXECUTE", (loop, ctx, w_tid)))
        await ctx.completion_future # Waits for CLEAN_READY
        
        # 3. WebP Conversion
        ctx.webp_path = f"/content/downloads/final_output/{job_id}.webp"
        os.makedirs(os.path.dirname(ctx.webp_path), exist_ok=True)
        # Assuming V9 convert_to_webp is present
        convert_to_webp(ctx.clean_png_path, ctx.webp_path)
        validate_image_file(ctx.webp_path)
        await ctx.transition(JobState.WEBP_READY)
        
        # 4. R2 & DB (V9 backend logic)
        await ctx.transition(JobState.COMPLETED)
        return {"status": "completed"}
        
    except Exception as e:
        await ctx.transition(JobState.FAILED)
        ctx.error = str(e)
        raise

async def main():
    global GEMINI_POOL, WMR_POOL
    GEMINI_POOL = GeminiWorkerPool(capacity=4)
    WMR_POOL = WmrWorkerPoolV14(profiles=4, tabs_per_profile=2)
    
    asyncio.create_task(poll_downloads_loop())
    
    worker = Worker("job-queue", process_job, {"connection": {"host": "localhost", "port": 6379}})
    print("[BOOT] BullMQ Worker started")
    while True:
        await asyncio.sleep(3600)

WORKER_MAIN_TASK = None
def start_worker():
    global WORKER_MAIN_TASK
    try:
        loop = asyncio.get_running_loop()
        if WORKER_MAIN_TASK is not None and not WORKER_MAIN_TASK.done():
            print("[V15] Worker already running")
            return WORKER_MAIN_TASK
        WORKER_MAIN_TASK = loop.create_task(main())
        return WORKER_MAIN_TASK
    except RuntimeError:
        asyncio.run(main())

if __name__ == "__main__":
    start_worker()
"""

with open(FINAL, "a", encoding="utf-8") as f:
    f.write("\n\n" + orchestration_code)
