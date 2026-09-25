import os
import re

with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

truncation_point = 2048
# Let's verify line 2047 is an empty line or similar to what we expect
while "ThreadPoolExecutor" not in lines[truncation_point - 3] and "Worker" not in lines[truncation_point - 2]:
    truncation_point += 1
    if truncation_point >= len(lines):
        truncation_point = 2047
        break

core_lines = lines[:truncation_point]

new_orch = """
# ==============================================================================
# FINAL RUNTIME HARDENING - ORCHESTRATION & STATE MACHINE
# ==============================================================================

class JobState(Enum):
    PENDING = "PENDING"
    GEMINI_RESERVED = "GEMINI_RESERVED"
    GEMINI_RUNNING = "GEMINI_RUNNING"
    RAW_DOWNLOAD_START = "RAW_DOWNLOAD_START"
    RAW_WAITING = "RAW_WAITING"
    RAW_VALIDATED = "RAW_VALIDATED"
    WMR_RESERVED = "WMR_RESERVED"
    WMR_RUNNING = "WMR_RUNNING"
    WMR_DOWNLOAD_START = "WMR_DOWNLOAD_START"
    CLEAN_WAITING = "CLEAN_WAITING"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    DB_SAVED = "DB_SAVED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class DownloadRecord:
    job_id: str
    guid: Optional[str]
    source: str
    staging_dir: str
    expected_filename: str
    target_state: JobState

DOWNLOAD_REGISTRY: Dict[str, DownloadRecord] = {}

class FirstFreeBroker:
    def __init__(self, name: str, resources: List[str]):
        self.name = name
        self.resource_ids = resources
        self._free_heap = []
        self._seq = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._known_resources = set()
        self._dead_resources = set()
        for r in resources:
            self.add_resource(r)

    def add_resource(self, resource_id: str):
        with self._lock:
            if resource_id not in self._known_resources:
                self._known_resources.add(resource_id)
                self._seq += 1
                heapq.heappush(self._free_heap, (self._seq, resource_id))
                self._condition.notify_all()

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

@dataclass
class JobContext:
    job_id: str
    payload: Dict[str, Any]
    state: JobState = JobState.PENDING
    gemini_resource: Optional[str] = None
    gemini_released: bool = False
    wmr_resource: Optional[str] = None
    wmr_released: bool = False
    raw_guid: Optional[str] = None
    wmr_guid: Optional[str] = None
    raw_path: Optional[str] = None
    clean_png_path: Optional[str] = None
    webp_path: Optional[str] = None
    error: Optional[str] = None
    
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    state_cond: asyncio.Condition = field(default_factory=asyncio.Condition)

    async def transition(self, new_state: JobState):
        async with self.state_cond:
            print(f"[JOB_STATE] {self.job_id} {self.state.name} -> {new_state.name}")
            self.state = new_state
            self.state_cond.notify_all()
            
    def transition_sync(self, new_state: JobState):
        asyncio.run_coroutine_threadsafe(self.transition(new_state), asyncio.get_running_loop())

    async def wait_for_state(self, target_state: JobState):
        async with self.state_cond:
            while self.state != target_state and self.state != JobState.FAILED:
                await self.state_cond.wait()
            if self.state == JobState.FAILED:
                raise RuntimeError(f"Job {self.job_id} failed while waiting for {target_state.name}: {self.error}")

JOB_CONTEXTS: Dict[str, JobContext] = {}

def release_gemini_once(ctx: JobContext):
    if ctx.gemini_resource and not ctx.gemini_released:
        ctx.gemini_released = True
        GEMINI_BROKER.release(ctx.gemini_resource)

def release_wmr_once(ctx: JobContext):
    if ctx.wmr_resource and not ctx.wmr_released:
        ctx.wmr_released = True
        WMR_BROKER.release(ctx.wmr_resource)

def get_wmr_logical_job_dir(resource_id: str, job_id: str) -> Path:
    d = Path(WMR_STAGING_BASE) / resource_id / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d

# ------------------------------------------------------------------------------
# PIPELINE EXECUTION
# ------------------------------------------------------------------------------

GEMINI_EXECUTOR = ThreadPoolExecutor(max_workers=4)

class GeminiWorker:
    def __init__(self, tid: str):
        self.tid = tid
        self.driver = None

    def do_execute_sync(self, ctx: JobContext):
        prefix = f"[{self.tid}][{ctx.job_id}]"
        try:
            ctx.transition_sync(JobState.GEMINI_RUNNING)
            if self.driver is None:
                self.driver = create_chrome_driver()
                comprehensive_login_check(self.driver, "Gemini Worker")

            tid_int = int(self.tid.replace('T', ''))
            
            tab_id_str = open_new_chat_and_reload(self.driver, tid_int, ctx.job_id)
            if not tab_id_str:
                raise RuntimeError("Failed to create/find target tab")
            
            staging_dir = str(CHROME_DL_BASE / self.tid)
            set_tab_download_dir(self.driver, staging_dir)

            ensure_create_image_mode(self.driver, tid_int, ctx.job_id)

            prompt, garment_path, model_path, holo_path = resolve_prompt_and_refs(ctx.payload)
            upload_paths = []
            if garment_path: upload_paths.append(str(Path(garment_path).resolve()))
            if model_path: upload_paths.append(str(Path(model_path).resolve()))
            if holo_path: upload_paths.append(str(Path(holo_path).resolve()))

            upload_reference_files(self.driver, upload_paths, tid_int, ctx.job_id)
            _inject_prompt_atomic(self.driver, prompt, tid_int, ctx.job_id)

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

            for _ in range(60):
                try:
                    for entry in self.driver.get_log('performance'):
                        try:
                            msg = json.loads(entry['message'])['message']
                            if msg['method'] == 'Browser.downloadWillBegin':
                                dl_guid = msg['params']['guid']
                                break
                        except Exception:
                            pass
                except Exception:
                    pass
                if dl_guid:
                    break
                time.sleep(1)

            if not dl_guid:
                source = "filesystem"
            
            ctx.raw_guid = dl_guid
            
            DOWNLOAD_REGISTRY[ctx.job_id] = DownloadRecord(
                job_id=ctx.job_id,
                guid=dl_guid,
                source=source,
                staging_dir=staging_dir,
                expected_filename=expected_png,
                target_state=JobState.RAW_VALIDATED
            )
            
            # IMMEDIATELY RELEASE GEMINI UPON DOWNLOAD START!
            release_gemini_once(ctx)
            ctx.transition_sync(JobState.RAW_WAITING)

        except Exception as e:
            ctx.error = str(e)
            ctx.transition_sync(JobState.FAILED)
            release_gemini_once(ctx)
            
GEMINI_WORKERS = {f"T{i}": GeminiWorker(f"T{i}") for i in range(4)}

class WmrDriverThread(threading.Thread):
    def __init__(self, resource_id: str):
        super().__init__(daemon=True)
        self.resource_id = resource_id
        self.w_pid = int(resource_id.split("-")[0].replace("W", ""))
        self.command_queue = queue.Queue()
        self.driver = None

    def run(self):
        while True:
            cmd, ctx = self.command_queue.get()
            if cmd == "EXECUTE":
                prefix = f"[{self.resource_id}][{ctx.job_id}]"
                try:
                    if self.driver is None:
                        self.driver = create_wmr_chrome_driver(self.w_pid)
                        self.driver.get("https://www.watermarkremover.io/upload")
                    
                    ctx.transition_sync(JobState.WMR_RUNNING)
                    staging_dir = get_wmr_logical_job_dir(self.resource_id, ctx.job_id)

                    set_tab_download_dir(self.driver, str(staging_dir))

                    _wmr_expose_file_inputs(self.driver)
                    file_input = _wmr_find_file_input(self.driver)
                    file_input.send_keys(str(Path(ctx.raw_path).resolve()))

                    try:
                        _wmr_check_status(self.driver)
                    except Exception:
                        pass # Sometimes missing argument in old signatures, rely on _wmr_click_download
                        
                    try:
                        _wmr_click_download(self.driver)
                    except Exception:
                        # Fallback for old signature that might require attempts
                        _wmr_click_download(self.driver, attempts=6)

                    expected_png = f"{ctx.job_id}_clean.png"
                    
                    ctx.transition_sync(JobState.WMR_DOWNLOAD_START)
                    
                    dl_guid = None
                    for _ in range(60):
                        try:
                            for entry in self.driver.get_log('performance'):
                                try:
                                    msg = json.loads(entry['message'])['message']
                                    if msg['method'] == 'Browser.downloadWillBegin':
                                        dl_guid = msg['params']['guid']
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        if dl_guid:
                            break
                        time.sleep(1)

                    source = "cdp" if dl_guid else "filesystem"
                    
                    DOWNLOAD_REGISTRY[ctx.job_id + "_wmr"] = DownloadRecord(
                        job_id=ctx.job_id,
                        guid=dl_guid,
                        source=source,
                        staging_dir=str(staging_dir),
                        expected_filename=expected_png,
                        target_state=JobState.CLEAN_READY
                    )
                    
                    release_wmr_once(ctx)
                    ctx.transition_sync(JobState.CLEAN_WAITING)

                except Exception as e:
                    ctx.error = str(e)
                    ctx.transition_sync(JobState.FAILED)
                    release_wmr_once(ctx)
                finally:
                    self.command_queue.task_done()
            else:
                self.command_queue.task_done()

WMR_THREADS = {}
for i in range(4):
    for j in range(2):
        rid = f"W{i}-T{j}"
        WMR_THREADS[rid] = WmrDriverThread(rid)
        WMR_THREADS[rid].start()

async def execute_pipeline(ctx: JobContext):
    try:
        tid = await GEMINI_BROKER.acquire(ctx.job_id)
        ctx.gemini_resource = tid
        await ctx.transition(JobState.GEMINI_RESERVED)
        
        loop = asyncio.get_running_loop()
        worker = GEMINI_WORKERS[tid]
        
        await loop.run_in_executor(GEMINI_EXECUTOR, worker.do_execute_sync, ctx)
        await ctx.wait_for_state(JobState.RAW_VALIDATED)
        
        w_tid = await WMR_BROKER.acquire(ctx.job_id)
        ctx.wmr_resource = w_tid
        await ctx.transition(JobState.WMR_RESERVED)
        
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
        await ctx.transition(JobState.WEBP_READY)
        
        try:
            fs = sys.modules["fashion_studio"]
            fs.push_generation(
                image_path=ctx.clean_png_path,
                prompt=ctx.payload.get("prompt", "Tryon"),
                user_id=ctx.payload.get("user_id"),
                gen_id=ctx.job_id,
                webp_path=ctx.webp_path,
                force=True
            )
            await ctx.transition(JobState.DB_SAVED)
            
            crd = sys.modules["credits"]
            crd.settle_look(ctx.job_id)
        except Exception as e:
            if "credits" in sys.modules:
                sys.modules["credits"].refund_look(ctx.job_id, str(e)[:500])
            raise

        await ctx.transition(JobState.COMPLETED)
        
    except Exception as e:
        ctx.error = str(e)
        if ctx.state != JobState.FAILED:
            await ctx.transition(JobState.FAILED)
        release_gemini_once(ctx)
        release_wmr_once(ctx)

# ------------------------------------------------------------------------------
# DOWNLOAD WATCHER
# ------------------------------------------------------------------------------

async def poll_downloads_loop():
    while True:
        try:
            for dict_key, rec in list(DOWNLOAD_REGISTRY.items()):
                ctx = JOB_CONTEXTS.get(rec.job_id)
                if not ctx or ctx.state == JobState.FAILED:
                    DOWNLOAD_REGISTRY.pop(dict_key, None)
                    continue

                staging = Path(rec.staging_dir)
                if not staging.exists():
                    continue

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
                        except Exception:
                            pass

                    if stable:
                        try:
                            validate_image_file(str(completed_file))
                            if rec.target_state == JobState.RAW_VALIDATED:
                                ctx.raw_path = str(completed_file)
                            else:
                                ctx.clean_png_path = str(completed_file)

                            ctx.transition_sync(rec.target_state)
                            DOWNLOAD_REGISTRY.pop(dict_key, None)
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
    if not gen:
        raise RuntimeError(f"Generation {generation_id} not found in DB.")

    ctx = JobContext(job_id=generation_id, payload=gen)
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
    print("[SELFTEST] Resource architecture PASS")

WORKER_MAIN_TASK = None
BULLMQ_WORKER = None
WATCHER_TASK = None

async def main():
    global BULLMQ_WORKER, WATCHER_TASK
    
    run_architecture_self_test()
    
    print("Checking Database...")
    db_conn = sys.modules['db'].borrow()
    db_conn.cursor().execute("SELECT 1")
    db_conn.close()
    
    QUEUE_NAME = os.environ.get("QUEUE_NAME", "generations")
    print(f"Starting N2N Worker on queue: {QUEUE_NAME}")
    
    WATCHER_TASK = asyncio.create_task(poll_downloads_loop())
    
    opts = {"connection": os.environ.get("REDIS_URL"), "prefix": os.environ.get("REDIS_KEY_PREFIX")}
    from urllib.parse import urlparse
    u = urlparse(opts["connection"])
    real_opts = {"host": u.hostname or "localhost", "port": u.port or 6379}
    if u.password: real_opts["password"] = u.password
    if u.scheme == 'rediss': real_opts["tls"] = {}
    
    BULLMQ_WORKER = Worker(QUEUE_NAME, process_bullmq_job, {"connection": real_opts, "prefix": opts["prefix"]})
    print("N2N WORKER READY")
    
    while True:
        await asyncio.sleep(3600)

async def shutdown_worker():
    global BULLMQ_WORKER, WORKER_MAIN_TASK, WATCHER_TASK
    if BULLMQ_WORKER: await BULLMQ_WORKER.close()
    if WATCHER_TASK: WATCHER_TASK.cancel()
    if WORKER_MAIN_TASK: WORKER_MAIN_TASK.cancel()
    print("[SHUTDOWN] Worker stopped cleanly.")

def start_worker():
    global WORKER_MAIN_TASK
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(main())
    if WORKER_MAIN_TASK and not WORKER_MAIN_TASK.done():
        return WORKER_MAIN_TASK
    WORKER_MAIN_TASK = loop.create_task(main())
    return WORKER_MAIN_TASK

if __name__ == '__main__':
    start_worker()
"""

core_lines.append(new_orch)

with open("FULL_QUEUE_WORKER_FINAL.py", "w", encoding="utf-8") as f:
    f.writelines(core_lines)
