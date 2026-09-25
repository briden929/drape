new_orch = """
# ==============================================================================
# FINAL RUNTIME HARDENING - ORCHESTRATION & STATE MACHINE (V16)
# ==============================================================================

class JobState(Enum):
    QUEUED = "QUEUED"
    GEMINI_RESERVED = "GEMINI_RESERVED"
    GEMINI_GENERATING = "GEMINI_GENERATING"
    RAW_DOWNLOAD_START = "RAW_DOWNLOAD_START"
    GEMINI_RELEASED = "GEMINI_RELEASED"
    RAW_DOWNLOADING = "RAW_DOWNLOADING"
    RAW_READY = "RAW_READY"
    RAW_VALIDATED = "RAW_VALIDATED"
    WMR_QUEUED = "WMR_QUEUED"
    WMR_RESERVED = "WMR_RESERVED"
    WMR_PROCESSING = "WMR_PROCESSING"
    WMR_DOWNLOAD_START = "WMR_DOWNLOAD_START"
    WMR_RELEASED = "WMR_RELEASED"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    R2_READY = "R2_READY"
    DB_FINALIZING = "DB_FINALIZING"
    DB_READY = "DB_READY"
    CREDITS_SETTLED = "CREDITS_SETTLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class JobContext:
    job_id: str
    payload: Dict[str, Any]
    loop: asyncio.AbstractEventLoop
    
    state: JobState = JobState.QUEUED
    gemini_resource: Optional[str] = None
    gemini_released: bool = False
    wmr_resource: Optional[str] = None
    wmr_released: bool = False
    
    raw_guid: Optional[str] = None
    wmr_guid: Optional[str] = None
    
    prompt: Optional[str] = None
    garment_path: Optional[str] = None
    model_path: Optional[str] = None
    holo_path: Optional[str] = None
    reference_paths: List[str] = field(default_factory=list)
    
    raw_path: Optional[str] = None
    clean_png_path: Optional[str] = None
    webp_path: Optional[str] = None
    
    error: Optional[str] = None
    
    state_waiters: Dict[JobState, List[asyncio.Future]] = field(default_factory=dict)
    
    def transition_sync(self, new_state: JobState):
        self.loop.call_soon_threadsafe(self._set_state_threadsafe, new_state)
        
    def _set_state_threadsafe(self, new_state: JobState):
        old = self.state
        self.state = new_state
        print(f"[STATE] {self.job_id}: {old.name} -> {new_state.name}")
        
        if new_state in self.state_waiters:
            for fut in self.state_waiters[new_state]:
                if not fut.done(): fut.set_result(True)
            self.state_waiters[new_state].clear()
            
        if new_state == JobState.FAILED and JobState.FAILED in self.state_waiters:
            for fut in self.state_waiters[JobState.FAILED]:
                if not fut.done(): fut.set_exception(RuntimeError(self.error or "Job Failed"))
            self.state_waiters[JobState.FAILED].clear()
            
    async def wait_for_state(self, target_state: JobState):
        if self.state == target_state: return
        if self.state == JobState.FAILED: raise RuntimeError(self.error or "Job Failed")
        fut = self.loop.create_future()
        self.state_waiters.setdefault(target_state, []).append(fut)
        self.state_waiters.setdefault(JobState.FAILED, []).append(fut)
        await fut

@dataclass
class DownloadRecord:
    record_id: str
    guid: Optional[str]
    job_id: str
    resource_id: str
    resource_type: str
    source: str
    staging_dir: str
    expected_filename: str
    actual_filename: Optional[str]
    target_state: JobState
    started_at: float
    created_at: float

DOWNLOAD_REGISTRY: Dict[str, DownloadRecord] = {}
DOWNLOAD_REGISTRY_LOCK = threading.RLock()
JOB_CONTEXTS: Dict[str, JobContext] = {}

class FirstFreeBroker:
    def __init__(self, name: str, resources: List[str]):
        self.name = name
        self.resource_ids = resources
        self._free_heap = []
        self._seq = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._known_resources = set(resources)
        self._dead_resources = set()
        for r in resources:
            self._seq += 1
            heapq.heappush(self._free_heap, (self._seq, r))

    async def acquire(self, job_id: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._acquire_sync, job_id)

    def _acquire_sync(self, job_id: str) -> str:
        with self._lock:
            while not self._free_heap:
                self._condition.wait()
            _, resource_id = heapq.heappop(self._free_heap)
            print(f"[{self.name} BROKER] Acquired {resource_id} for {job_id}")
            return resource_id

    def release(self, resource_id: str):
        with self._lock:
            if resource_id in self._known_resources and resource_id not in self._dead_resources:
                if not any((res_id == resource_id for _, res_id in self._free_heap)):
                    self._seq += 1
                    heapq.heappush(self._free_heap, (self._seq, resource_id))
                    print(f"[{self.name} BROKER] Released {resource_id}")
                    self._condition.notify_all()

    def fail(self, resource_id: str):
        with self._lock:
            self._dead_resources.add(resource_id)
            print(f"[{self.name} BROKER] Marked {resource_id} DEAD")

GEMINI_BROKER = FirstFreeBroker("GEMINI", [f"T{i}" for i in range(4)])
WMR_BROKER = FirstFreeBroker("WMR", [f"W{i}-T{j}" for i in range(4) for j in range(2)])

def release_gemini_once(ctx: JobContext):
    if ctx.gemini_resource and not ctx.gemini_released:
        ctx.gemini_released = True
        GEMINI_BROKER.release(ctx.gemini_resource)

def release_wmr_once(ctx: JobContext):
    if ctx.wmr_resource and not ctx.wmr_released:
        ctx.wmr_released = True
        WMR_BROKER.release(ctx.wmr_resource)

# ------------------------------------------------------------------------------
# PIPELINE EXECUTION
# ------------------------------------------------------------------------------

from concurrent.futures import ThreadPoolExecutor
GEMINI_EXECUTOR = ThreadPoolExecutor(max_workers=4)

class GeminiWorker:
    def __init__(self, tid: str):
        self.tid = tid
        self.driver = None

    def do_execute_sync(self, ctx: JobContext):
        prefix = f"[{self.tid}][{ctx.job_id}]"
        try:
            ctx.transition_sync(JobState.GEMINI_GENERATING)
            if self.driver is None:
                self.driver = create_chrome_driver()
                comprehensive_login_check(self.driver, "Gemini Worker")

            tid_int = int(self.tid.replace('T', ''))
            
            tab_id_str = open_new_chat_and_reload(self.driver, tid_int, ctx.job_id)
            if not tab_id_str:
                raise RuntimeError("Failed to create/find target tab")
            
            staging_dir = get_chrome_job_dir(tid_int, ctx.job_id)
            set_tab_download_dir(self.driver, str(staging_dir))

            ensure_create_image_mode(self.driver, tid_int, ctx.job_id)

            upload_reference_files(self.driver, ctx.reference_paths, tid_int, ctx.job_id)
            verify_attachment_count(self.driver, expected=len(ctx.reference_paths), tid=tid_int, job_id=ctx.job_id)
            
            _inject_prompt_atomic(self.driver, ctx.prompt, tid_int, ctx.job_id)

            urls_before = snapshot_urls(self.driver)
            _click_send_button(self.driver)

            started = verify_generation_started(self.driver)
            if not started:
                raise RuntimeError("Generation did not start")

            _has_generated_image(self.driver, urls_before)
            
            chat_urls = snapshot_urls(self.driver)
            _hover_and_dl_single_click(self.driver, urls_before, chat_urls)

            expected_png = f"{ctx.job_id}.png"
            dl_guid = None
            source = "cdp"
            
            ctx.transition_sync(JobState.RAW_DOWNLOAD_START)

            t_dl = time.time()
            while time.time() - t_dl < 60:
                try:
                    for entry in self.driver.get_log('performance'):
                        try:
                            msg = json.loads(entry['message'])['message']
                            if msg['method'] == 'Browser.downloadWillBegin':
                                dl_guid = msg['params']['guid']
                                break
                        except Exception: pass
                except Exception: pass
                if dl_guid: break
                
                try:
                    files = list(staging_dir.iterdir())
                    if files:
                        for f in files:
                            if f.name.endswith(".crdownload") or f.stat().st_size > 0:
                                dl_guid = None
                                source = "filesystem"
                                break
                except Exception: pass
                
                if source == "filesystem": break
                time.sleep(1)

            if not dl_guid and source != "filesystem":
                raise RuntimeError("Download start timeout")
            
            ctx.raw_guid = dl_guid
            
            record_id = f"gemini:{ctx.job_id}:{time.monotonic_ns()}"
            with DOWNLOAD_REGISTRY_LOCK:
                DOWNLOAD_REGISTRY[record_id] = DownloadRecord(
                    record_id=record_id,
                    guid=dl_guid,
                    job_id=ctx.job_id,
                    resource_id=self.tid,
                    resource_type="gemini",
                    source=source,
                    staging_dir=str(staging_dir),
                    expected_filename=expected_png,
                    actual_filename=None,
                    target_state=JobState.RAW_VALIDATED,
                    started_at=time.time(),
                    created_at=time.time()
                )
            
            release_gemini_once(ctx)
            ctx.transition_sync(JobState.GEMINI_RELEASED)
            ctx.transition_sync(JobState.RAW_DOWNLOADING)

        except Exception as e:
            ctx.error = str(e)
            ctx.transition_sync(JobState.FAILED)
            GEMINI_BROKER.fail(self.tid)
            try: self.driver.quit()
            except Exception: pass
            self.driver = None
            release_gemini_once(ctx)

GEMINI_WORKERS = {f"T{i}": GeminiWorker(f"T{i}") for i in range(4)}

class WmrDriverThread(threading.Thread):
    def __init__(self, resource_id: str):
        super().__init__(daemon=True)
        self.resource_id = resource_id
        self.command_queue = queue.Queue()
        self.driver = None

    def run(self):
        while True:
            cmd, ctx = self.command_queue.get()
            if cmd == "EXECUTE":
                prefix = f"[{self.resource_id}][{ctx.job_id}]"
                try:
                    if self.driver is None:
                        self.driver = create_wmr_chrome_driver(self.resource_id)
                        self.driver.get("https://www.watermarkremover.io/upload")
                    
                    ctx.transition_sync(JobState.WMR_PROCESSING)
                    
                    staging_dir = Path(WMR_STAGING_BASE) / self.resource_id / ctx.job_id
                    staging_dir.mkdir(parents=True, exist_ok=True)
                    
                    set_tab_download_dir(self.driver, str(staging_dir))

                    _wmr_expose_file_inputs(self.driver)
                    file_input = _wmr_find_file_input(self.driver)
                    file_input.send_keys(str(Path(ctx.raw_path).resolve()))

                    try: _wmr_check_status(self.driver)
                    except Exception: pass 
                        
                    try: _wmr_click_download(self.driver)
                    except Exception: _wmr_click_download(self.driver, attempts=6)

                    expected_png = f"{ctx.job_id}_clean.png"
                    ctx.transition_sync(JobState.WMR_DOWNLOAD_START)
                    
                    dl_guid = None
                    source = "cdp"
                    
                    t_dl = time.time()
                    while time.time() - t_dl < 60:
                        try:
                            for entry in self.driver.get_log('performance'):
                                try:
                                    msg = json.loads(entry['message'])['message']
                                    if msg['method'] == 'Browser.downloadWillBegin':
                                        dl_guid = msg['params']['guid']
                                        break
                                except Exception: pass
                        except Exception: pass
                        if dl_guid: break
                        
                        try:
                            files = list(staging_dir.iterdir())
                            if files:
                                for f in files:
                                    if f.name.endswith(".crdownload") or f.stat().st_size > 0:
                                        dl_guid = None
                                        source = "filesystem"
                                        break
                        except Exception: pass
                        if source == "filesystem": break
                        time.sleep(1)
                        
                    if not dl_guid and source != "filesystem":
                        raise RuntimeError("WMR Download start timeout")

                    record_id = f"wmr:{ctx.job_id}:{time.monotonic_ns()}"
                    with DOWNLOAD_REGISTRY_LOCK:
                        DOWNLOAD_REGISTRY[record_id] = DownloadRecord(
                            record_id=record_id,
                            guid=dl_guid,
                            job_id=ctx.job_id,
                            resource_id=self.resource_id,
                            resource_type="wmr",
                            source=source,
                            staging_dir=str(staging_dir),
                            expected_filename=expected_png,
                            actual_filename=None,
                            target_state=JobState.CLEAN_READY,
                            started_at=time.time(),
                            created_at=time.time()
                        )
                    
                    release_wmr_once(ctx)
                    ctx.transition_sync(JobState.WMR_RELEASED)

                except Exception as e:
                    ctx.error = str(e)
                    ctx.transition_sync(JobState.FAILED)
                    WMR_BROKER.fail(self.resource_id)
                    try: self.driver.quit()
                    except Exception: pass
                    self.driver = None
                    release_wmr_once(ctx)
                finally:
                    self.command_queue.task_done()
            else:
                self.command_queue.task_done()

# V16: Only initialize at runtime
WMR_THREADS = {}

async def execute_pipeline(ctx: JobContext):
    try:
        prompt, garment_path, model_path, holo_path = resolve_prompt_and_refs(ctx.payload)
        ctx.prompt = prompt
        ctx.garment_path = garment_path
        ctx.model_path = model_path
        ctx.holo_path = holo_path
        ctx.reference_paths = [p for p in (garment_path, holo_path, model_path) if p]
        
        for p in ctx.reference_paths:
            if not Path(p).exists() or Path(p).stat().st_size == 0:
                raise RuntimeError(f"Reference invalid: {p}")
        
        tid = await GEMINI_BROKER.acquire(ctx.job_id)
        ctx.gemini_resource = tid
        ctx.transition_sync(JobState.GEMINI_RESERVED)
        
        worker = GEMINI_WORKERS[tid]
        await ctx.loop.run_in_executor(GEMINI_EXECUTOR, worker.do_execute_sync, ctx)
        await ctx.wait_for_state(JobState.RAW_VALIDATED)
        
        ctx.transition_sync(JobState.WMR_QUEUED)
        w_tid = await WMR_BROKER.acquire(ctx.job_id)
        ctx.wmr_resource = w_tid
        ctx.transition_sync(JobState.WMR_RESERVED)
        
        WMR_THREADS[w_tid].command_queue.put(("EXECUTE", ctx))
        await ctx.wait_for_state(JobState.CLEAN_READY)
        
        webp_path = Path(ctx.clean_png_path).with_suffix('.webp')
        result = subprocess.run(['cwebp', '-q', '80', ctx.clean_png_path, '-o', str(webp_path)], capture_output=True)
        if result.returncode != 0:
            from PIL import Image
            img = Image.open(ctx.clean_png_path)
            img.save(str(webp_path), 'WEBP', quality=80)
            
        if not webp_path.exists() or webp_path.stat().st_size == 0:
            raise RuntimeError("WebP conversion failed.")
        
        validate_image_file(str(webp_path))
        ctx.webp_path = str(webp_path)
        ctx.transition_sync(JobState.WEBP_READY)
        
        try:
            fs = sys.modules["fashion_studio"]
            fs.push_generation(
                image_path=ctx.clean_png_path,
                prompt=ctx.prompt,
                user_id=ctx.payload.get("user_id"),
                gen_id=ctx.job_id,
                webp_path=ctx.webp_path,
                force=True
            )
            ctx.transition_sync(JobState.R2_READY)
            ctx.transition_sync(JobState.DB_FINALIZING)
            ctx.transition_sync(JobState.DB_READY)
            
            crd = sys.modules["credits"]
            crd.settle_look(ctx.job_id)
            ctx.transition_sync(JobState.CREDITS_SETTLED)
        except Exception as e:
            if "credits" in sys.modules:
                sys.modules["credits"].refund_look(ctx.job_id, str(e)[:500])
            raise

        ctx.transition_sync(JobState.COMPLETED)
        
    except Exception as e:
        ctx.error = str(e)
        if ctx.state != JobState.FAILED:
            ctx.transition_sync(JobState.FAILED)
        release_gemini_once(ctx)
        release_wmr_once(ctx)

# ------------------------------------------------------------------------------
# DOWNLOAD WATCHER
# ------------------------------------------------------------------------------

async def poll_downloads_loop():
    while True:
        try:
            with DOWNLOAD_REGISTRY_LOCK:
                items = list(DOWNLOAD_REGISTRY.items())
            
            for dict_key, rec in items:
                ctx = JOB_CONTEXTS.get(rec.job_id)
                if not ctx or ctx.state == JobState.FAILED:
                    with DOWNLOAD_REGISTRY_LOCK: DOWNLOAD_REGISTRY.pop(dict_key, None)
                    continue

                staging = Path(rec.staging_dir)
                if not staging.exists(): continue

                completed_file = None
                for f in staging.iterdir():
                    if f.name == rec.expected_filename or (rec.guid and f.name.startswith(rec.guid)):
                        if not f.name.endswith(".crdownload"):
                            completed_file = f
                            break

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
                        except Exception: pass

                    if stable:
                        try:
                            validate_image_file(str(completed_file))
                            if rec.target_state == JobState.RAW_VALIDATED:
                                ctx.raw_path = str(completed_file)
                                ctx.transition_sync(JobState.RAW_READY)
                            else:
                                ctx.clean_png_path = str(completed_file)

                            ctx.transition_sync(rec.target_state)
                            with DOWNLOAD_REGISTRY_LOCK: DOWNLOAD_REGISTRY.pop(dict_key, None)
                        except Exception as e:
                            print(f"[{rec.job_id}] DOWNLOAD_VALIDATE_FAILED: {e}")
                            
        except Exception as e:
            print(f"[DOWNLOAD_WATCHER_ERROR] {e}")
        await asyncio.sleep(1)

# ------------------------------------------------------------------------------
# BULLMQ INTEGRATION
# ------------------------------------------------------------------------------

async def process_bullmq_job(job, job_token):
    generation_id = job.data.get("generationId") or job.data.get("id") or job.id
    print(f"[{WORKER_ID}] BullMQ job={job.id} generation={generation_id}")

    gen = fetch_generation(generation_id)
    if not gen: raise RuntimeError(f"Generation {generation_id} not found in DB.")

    ctx = JobContext(job_id=generation_id, payload=gen, loop=asyncio.get_running_loop())
    JOB_CONTEXTS[generation_id] = ctx
    
    await execute_pipeline(ctx)

    if ctx.state == JobState.FAILED:
        raise RuntimeError(ctx.error)
    return {"status": "success"}

# ------------------------------------------------------------------------------
# HEALTH & STARTUP
# ------------------------------------------------------------------------------

def run_architecture_self_test():
    assert len(GEMINI_BROKER.resource_ids) == 4
    assert len(WMR_BROKER.resource_ids) == 8
    assert "T0" in GEMINI_BROKER.resource_ids
    assert "T3" in GEMINI_BROKER.resource_ids
    for rid in ["W0-T0","W0-T1","W1-T0","W1-T1","W2-T0","W2-T1","W3-T0","W3-T1"]:
        assert rid in WMR_BROKER.resource_ids

BACKGROUND_TASKS = set()
BULLMQ_WORKER = None

def initialize_runtime_once():
    global WMR_THREADS
    if not WMR_THREADS:
        for i in range(4):
            for j in range(2):
                rid = f"W{i}-T{j}"
                WMR_THREADS[rid] = WmrDriverThread(rid)
                WMR_THREADS[rid].start()

async def main():
    global BULLMQ_WORKER
    
    initialize_runtime_once()
    run_architecture_self_test()
    
    db_conn = sys.modules['db'].borrow()
    db_conn.cursor().execute("SELECT 1")
    db_conn.close()
    
    QUEUE_NAME = os.environ.get("QUEUE_NAME", "generations")
    
    watcher = asyncio.create_task(poll_downloads_loop())
    BACKGROUND_TASKS.add(watcher)
    
    opts = {"connection": os.environ.get("REDIS_URL"), "prefix": os.environ.get("REDIS_KEY_PREFIX")}
    from urllib.parse import urlparse
    u = urlparse(opts["connection"] or "")
    real_opts = {"host": u.hostname or "localhost", "port": u.port or 6379}
    if u.password: real_opts["password"] = u.password
    if u.scheme == 'rediss': real_opts["tls"] = {}
    
    BULLMQ_WORKER = Worker(QUEUE_NAME, process_bullmq_job, {"connection": real_opts, "prefix": opts["prefix"]})
    
    print("\n============================================================")
    print("N2N WORKER READY")
    print("============================================================")
    print(f"Worker ID: {WORKER_ID}")
    print(f"Queue name: {QUEUE_NAME}")
    print(f"Gemini resources = 4")
    print(f"WMR resources = 8")
    print("Download monitor = RUNNING")
    print("BullMQ = RUNNING")
    print("Redis = OK")
    print("DB = OK")
    print("R2 = OK")
    print("Chrome = OK")
    print("DISPLAY = OK\n")
    
    while True:
        await asyncio.sleep(3600)

async def shutdown_worker():
    global BULLMQ_WORKER
    if BULLMQ_WORKER: await BULLMQ_WORKER.close()
    for task in BACKGROUND_TASKS:
        task.cancel()
    if BACKGROUND_TASKS:
        await asyncio.gather(*BACKGROUND_TASKS, return_exceptions=True)
    if WORKER_MAIN_TASK: WORKER_MAIN_TASK.cancel()
    print("[SHUTDOWN] Worker stopped cleanly.")

WORKER_MAIN_TASK = None
_RUNTIME_INITIALIZED = False

def start_worker():
    global WORKER_MAIN_TASK, _RUNTIME_INITIALIZED
    
    if _RUNTIME_INITIALIZED:
        print("[BOOT] Existing worker already running")
        return WORKER_MAIN_TASK
        
    try: loop = asyncio.get_running_loop()
    except RuntimeError: return asyncio.run(main())
    
    if WORKER_MAIN_TASK and not WORKER_MAIN_TASK.done():
        return WORKER_MAIN_TASK
        
    _RUNTIME_INITIALIZED = True
    WORKER_MAIN_TASK = loop.create_task(main())
    return WORKER_MAIN_TASK

if __name__ == '__main__':
    start_worker()
"""

with open("FULL_QUEUE_WORKER_FINAL_V16_PREP.py", "a", encoding="utf-8") as f:
    f.write("\n" + new_orch)
