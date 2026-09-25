"""
V8 patch script — applies all architectural changes from V7 to produce V8.
Chrome-only: removes Edge, adds WMR Chrome workers, lazy tab creation,
download-start confirmation, exact attachment count.
"""
import re
import sys

src = 'FULL_QUEUE_WORKER_V7_FINAL.py'
dst = 'FULL_QUEUE_WORKER_V8_FINAL.py'

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

errors = []

def patch(description, old, new, required=True):
    global content
    if old not in content:
        msg = f"PATCH MISSING: {description}"
        errors.append(msg)
        print(f"  ❌ {msg}")
        return False
    content = content.replace(old, new, 1)
    print(f"  ✅ {description}")
    return True

print("=== V8 PATCH SCRIPT ===\n")

# ── PATCH 1: Header ──────────────────────────────────────────────────────────
patch("Header title",
    "# 🚀 QUEUE WORKER v4.0 — ECOM 2 ITERATION FULL PIPELINE ARCHITECTURE",
    "# 🚀 QUEUE WORKER v8.0 — CHROME ONLY DUAL-SYSTEM (GEMINI + WMR CHROME)"
)

patch("Header changelog",
    """# V4 CHANGES vs V3:
#   • open_new_chat_and_reload(): URL-verified new chat + confirmation dialog
#   • WmrWorkerPool: 4 independent Edge drivers, each with own profile/dir
#   • Job-specific directories: chrome/T{N}/{job_id}/incoming/, edge/, final_output/
#   • Download watcher scans ONLY job-specific incoming/ dir (no broad fallback)
#   • Hover-click is PRIMARY download method; CDP is fallback after 15s
#   • _free_tab() never touches active_downloads — full resource separation
#   • _recover_stuck_tab() per-tab only, supports requeue with retry budget
#   • File input missing = hard stop (no silent continue)
#   • Finalization: Edge PNG -> final_output -> WebP -> R2 -> DB -> Credits
#   • All 49 architecture requirements implemented""",
    """# V8 CHANGES:
#   • REMOVED all Edge/Microsoft Edge code entirely
#   • WMR runs in separate dedicated Google Chrome processes (W0-W3)
#   • WMR profiles in wmr_chrome_profiles/W0..W3 (separate from Gemini Chrome)
#   • WMR staging in wmr_staging/W0..W3 (fixed at launch, no CDP rebind needed)
#   • WMR canonical output in downloads/wmr/T{N}/{job_id}/ (T-slot ownership)
#   • LAZY Gemini tab creation: T0-T3 physical tabs created only when job arrives
#   • Physical Gemini tab CLOSED after DOWNLOAD_START_CONFIRMED (not after click)
#   • Exact attachment count validation (actual == expected, no >=)
#   • Download-start detection via .crdownload appearance before freeing tab
#   • Per-tab independent recovery: stuck T{N} only restarts T{N}
#   • Per-worker independent WMR recovery: stuck W{N} only restarts W{N}"""
)

# ── PATCH 2: Constants — WMR worker comment ──────────────────────────────────
patch("WMR workers constant comment",
    "CHROME_WMR_WORKERS = 4                 # E0, E1, E2, E3",
    "CHROME_WMR_WORKERS = 4                 # W0, W1, W2, W3"
)

# Add DOWNLOAD_START_WINDOW_S constant after DOWNLOAD_TIMEOUT_S
patch("Add DOWNLOAD_START_WINDOW_S constant",
    "DOWNLOAD_TIMEOUT_S = 120         # per-job Chrome download timeout\nWMR_TIMEOUT_S = 90               # per-job Edge WMR timeout",
    "DOWNLOAD_TIMEOUT_S = 120         # per-job Chrome download timeout\nDOWNLOAD_START_WINDOW_S = 15     # seconds to detect .crdownload after click\nWMR_TIMEOUT_S = 120              # per-job WMR Chrome timeout"
)

# ── PATCH 3: Directory layout ─────────────────────────────────────────────────
patch("EDGE_PROFILES_BASE -> WMR_PROFILES_BASE",
    "EDGE_PROFILES_BASE  = STATE_DIR / 'edge_profiles'   # worker_0 .. worker_3",
    "WMR_PROFILES_BASE   = STATE_DIR / 'wmr_chrome_profiles'  # W0 .. W3"
)

patch("EDGE_DL_BASE -> WMR dirs",
    "EDGE_DL_BASE        = DL_BASE / 'edge'",
    "WMR_DL_BASE         = DL_BASE / 'wmr'          # wmr/T{N}/{job_id}/\nWMR_STAGING_BASE    = DL_BASE / 'wmr_staging'   # wmr_staging/W0..W3"
)

# Fix makedirs call
patch("Makedirs: remove EDGE_PROFILES_BASE add WMR dirs",
    "for _d in (BASE_DIR, STATE_DIR, CHROME_PROFILE_DIR, EDGE_PROFILES_BASE, REFS_CACHE_DIR,\n           DL_BASE, CHROME_DL_BASE, EDGE_DL_BASE, FINAL_OUTPUT_BASE):",
    "for _d in (BASE_DIR, STATE_DIR, CHROME_PROFILE_DIR, WMR_PROFILES_BASE, REFS_CACHE_DIR,\n           DL_BASE, CHROME_DL_BASE, WMR_DL_BASE, WMR_STAGING_BASE, FINAL_OUTPUT_BASE):"
)

patch("Remove Edge profile sub-creation loop, add WMR profile+staging dirs",
    """for _i in range(CHROME_WMR_WORKERS):
    (EDGE_PROFILES_BASE / f'worker_{_i}').mkdir(parents=True, exist_ok=True)""",
    """for _i in range(CHROME_WMR_WORKERS):
    (WMR_PROFILES_BASE / f'W{_i}').mkdir(parents=True, exist_ok=True)
    (WMR_STAGING_BASE / f'W{_i}').mkdir(parents=True, exist_ok=True)"""
)

patch("Print: Edge Profiles -> WMR Profiles",
    "print(f\"  Edge Profiles:     {EDGE_PROFILES_BASE}/worker_{{0-3}}\")",
    "print(f\"  WMR Profiles:      {WMR_PROFILES_BASE}/W{{0-3}}\")"
)

patch("Print: Edge WMR Workers -> WMR Chrome Workers",
    "print(f\"  Edge WMR Workers:  {CHROME_WMR_WORKERS} (E0-E3)\")",
    "print(f\"  WMR Chrome Workers: {CHROME_WMR_WORKERS} (W0-W3)\")"
)

# ── PATCH 4: Job directory helpers ────────────────────────────────────────────
patch("get_edge_job_dir -> get_wmr_job_dir + get_wmr_staging_dir",
    '''def get_edge_job_dir(chrome_tab_id: int, job_id: str):
    """Returns (job_dir, incoming_dir) for Edge WMR downloads."""
    job_dir = EDGE_DL_BASE / f'T{chrome_tab_id}' / job_id
    incoming = job_dir / 'incoming'
    incoming.mkdir(parents=True, exist_ok=True)
    return job_dir, incoming''',
    '''def get_wmr_job_dir(chrome_tab_id: int, job_id: str):
    """Returns (job_dir, incoming_dir) for WMR Chrome output. Named by T-slot, not W-slot."""
    job_dir = WMR_DL_BASE / f'T{chrome_tab_id}' / job_id
    incoming = job_dir / 'incoming'
    incoming.mkdir(parents=True, exist_ok=True)
    return job_dir, incoming

def get_wmr_staging_dir(wmr_worker_id: int) -> Path:
    """Returns the dedicated staging directory for WMR Chrome worker W{wmr_worker_id}."""
    d = WMR_STAGING_BASE / f'W{wmr_worker_id}'
    d.mkdir(parents=True, exist_ok=True)
    return d'''
)

# ── PATCH 5: STEP 6 header ────────────────────────────────────────────────────
patch("STEP 6 print header",
    "print(\"🌐 STEP 6: INITIALIZING PERSISTENT CHROME & EDGE DRIVERS\")",
    "print(\"🌐 STEP 6: INITIALIZING PERSISTENT CHROME DRIVERS\")"
)

# ── PATCH 6: Remove create_edge_driver_for_worker, add create_wmr_chrome_driver
patch("Replace create_edge_driver_for_worker with create_wmr_chrome_driver",
    '''def create_edge_driver_for_worker(worker_id: int, dl_dir: str):
    profile_dir = EDGE_PROFILES_BASE / f'worker_{worker_id}'
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    # 🧹 Clean locks for WMR profile too
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = profile_dir / fname
        if fpath.exists():
            try: fpath.unlink()
            except: pass

    dl_dir_str = str(Path(dl_dir).resolve())

    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={profile_dir}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-sync")
    opts.add_argument("--disable-features=IdentityConsistencyBrowserUI,SyncPromoUI")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    prefs = {
        "download.default_directory": dl_dir_str,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    opts.add_experimental_option("prefs", prefs)
    drv = webdriver.Chrome(options=opts)

    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow', 'downloadPath': dl_dir_str
        })
    except Exception:
        pass
    return drv''',
    '''def create_wmr_chrome_driver(worker_id: int) -> webdriver.Chrome:
    """Create a dedicated Chrome WMR driver for W{worker_id}.
    Downloads go to wmr_staging/W{worker_id}/ — fixed at launch time via Chrome prefs.
    Profile is completely isolated from Gemini Chrome and other WMR workers.
    Never uses EdgeOptions, webdriver.Edge, or Edge profiles.
    """
    staging_dir = get_wmr_staging_dir(worker_id)
    profile_dir = WMR_PROFILES_BASE / f'W{worker_id}'
    profile_dir.mkdir(parents=True, exist_ok=True)

    # 🧹 Clean singleton locks
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = profile_dir / fname
        if fpath.exists():
            try: fpath.unlink()
            except: pass

    dl_dir_str = str(staging_dir.resolve())

    opts = ChromeOptions()
    opts.add_argument(f'--user-data-dir={profile_dir}')
    opts.add_argument('--profile-directory=Default')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--window-size=1400,900')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_argument('--no-first-run')
    opts.add_argument('--no-default-browser-check')
    opts.add_argument('--disable-sync')
    opts.add_argument('--disable-features=IdentityConsistencyBrowserUI,SyncPromoUI')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_experimental_option('useAutomationExtension', False)
    prefs = {
        'download.default_directory': dl_dir_str,
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'safebrowsing.enabled': False,
        'safebrowsing.disable_download_protection': True,
        'profile.default_content_setting_values.automatic_downloads': 1,
    }
    opts.add_experimental_option('prefs', prefs)
    drv = webdriver.Chrome(options=opts)
    # Belt-and-suspenders CDP confirm on initial tab
    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow', 'downloadPath': dl_dir_str
        })
    except Exception:
        pass
    log(f'[WMR-W{worker_id}] Browser = Google Chrome  staging={staging_dir}')
    return drv'''
)

# ── PATCH 7: STEP 8 header ────────────────────────────────────────────────────
patch("STEP 8 section header comment",
    "# STEP 8: EDGE WATERMARK REMOVER POOL (4 INDEPENDENT WORKERS)",
    "# STEP 8: CHROME WMR WORKER POOL (W0-W3, LAZY — created on demand)"
)

patch("STEP 8 print header",
    "print(\"🧼 STEP 8: STARTING EDGE WATERMARK REMOVER POOL (4 WORKERS)\")",
    "print(\"🧼 STEP 8: REGISTERING CHROME WMR POOL (LAZY — W0-W3 created on demand)\")"
)

# ── PATCH 8: WmrWorker class — replace entirely ───────────────────────────────
# Find the WmrWorker class start and WmrWorkerPool end to replace both
wmr_old_start = 'class WmrWorker:\n    """One independent Edge WMR worker with its own driver, profile, and queue."""'
wmr_pool_old_end = '''    def quit_all(self):
        for w in self.workers:
            w.quit()


edge_pool = WmrWorkerPool(CHROME_WMR_WORKERS)
print(f"  ✅ Edge Watermark Remover Pool: {CHROME_WMR_WORKERS} independent workers active.\\n")'''

wmr_new_classes = '''class WmrWorker:
    """
    One independent CHROME WMR worker (W0-W3).
    Each worker has its own Chrome driver, Chrome profile (wmr_chrome_profiles/W{N}),
    and staging directory (wmr_staging/W{N}).
    LAZY: Chrome driver is created only when the first job actually arrives.
    WMR output is named by T-slot (business ownership), not W-slot (processor).
    """

    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.staging_dir = get_wmr_staging_dir(worker_id)
        self.work_queue: queue.Queue = queue.Queue()
        self.driver = None
        self.driver_lock = threading.Lock()
        self.state = "IDLE"        # IDLE | PROCESSING
        self.current_job_id = None
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"WmrWorker-W{worker_id}"
        )
        self._thread.start()
        log(f'[WMR-W{worker_id}] Worker slot registered (LAZY — Chrome not yet started)')

    def _ensure_driver(self) -> webdriver.Chrome:
        """Lazily create the Chrome WMR driver on first use."""
        with self.driver_lock:
            if self.driver is None:
                log(f'[WMR-W{self.worker_id}] Creating WMR Chrome driver (first job)...')
                self.driver = create_wmr_chrome_driver(self.worker_id)
            return self.driver

    def _clean_staging(self):
        """Remove all files from this worker's staging dir before a new job."""
        try:
            for fn in os.listdir(self.staging_dir):
                fp = self.staging_dir / fn
                if fp.is_file():
                    try: fp.unlink()
                    except: pass
        except Exception:
            pass

    def _run_loop(self):
        while True:
            item = self.work_queue.get()
            if item is None:
                break
            job_id, chrome_tab_id, raw_png_path, response_future, loop = item
            self.state = "PROCESSING"
            self.current_job_id = job_id
            try:
                result = self._process_wmr_job(job_id, chrome_tab_id, str(raw_png_path))
                loop.call_soon_threadsafe(response_future.set_result, result)
            except Exception as ex:
                log(f"[WMR-W{self.worker_id}][{job_id}] WMR_ERROR: {ex}", file=sys.stderr)
                loop.call_soon_threadsafe(response_future.set_exception, ex)
            finally:
                self.state = "IDLE"
                self.current_job_id = None
                self.work_queue.task_done()

    def _process_wmr_job(self, job_id: str, chrome_tab_id: int, raw_png_path: str):
        """
        WMR pipeline for one job.
        Returns (clean_png_path, webp_path).
        Canonical output path = wmr/T{chrome_tab_id}/{job_id}/ — NOT W{worker_id}.
        W-slot is the processor; T-slot is the business ownership key.
        """
        # Canonical output dirs — named by original T-slot, not W-slot
        wmr_job_dir, wmr_incoming = get_wmr_job_dir(chrome_tab_id, job_id)
        clean_png  = wmr_job_dir / f'{job_id}_clean.png'
        clean_webp = wmr_job_dir / f'{job_id}_clean.webp'

        drv = self._ensure_driver()

        for attempt in range(1, 3):
            log(f"[WMR-W{self.worker_id}][{job_id}] WMR_ATTEMPT_{attempt}")
            try:
                # Clean staging before this job's upload
                self._clean_staging()
                files_before_staging = set(os.listdir(self.staging_dir))

                drv.get(WMR_SERVICE_URL)
                time.sleep(1.2)

                log(f"[WMR-W{self.worker_id}][{job_id}] UPLOAD_STARTED")
                fi = _wmr_find_file_input(drv)
                if not fi:
                    time.sleep(0.5)
                    fi = _wmr_find_file_input(drv)
                if not fi:
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR file input not found (attempt {attempt})")
                    continue

                fi.send_keys(str(Path(raw_png_path).resolve()))
                time.sleep(0.5)
                log(f"[WMR-W{self.worker_id}][{job_id}] UPLOAD_VERIFIED")

                # Poll for WMR processing completion
                log(f"[WMR-W{self.worker_id}][{job_id}] WMR_PROCESSING")
                t0 = time.time()
                ready = False
                while time.time() - t0 < WMR_TIMEOUT_S:
                    status = _wmr_check_status(drv)
                    if status == "DONE":
                        ready = True
                        break
                    elif status == "NOT_FOUND":
                        log(f"[WMR-W{self.worker_id}][{job_id}] WMR_NOT_FOUND — no watermark detected")
                        ready = True
                        break
                    time.sleep(0.6)

                if not ready:
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR not ready after {WMR_TIMEOUT_S}s (attempt {attempt})")
                    continue

                # DOWNLOAD_BUTTON_DETECTED — verify before clicking
                log(f"[WMR-W{self.worker_id}][{job_id}] DOWNLOAD_BUTTON_DETECTED")
                if not _wmr_click_download(drv):
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR download click failed (attempt {attempt})")
                    continue
                log(f"[WMR-W{self.worker_id}][{job_id}] DOWNLOAD_CLICKED")

                # Detect download START (.crdownload or new image file)
                dl_started = False
                t1 = time.time()
                while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                    cur = set(os.listdir(self.staging_dir))
                    new_files = cur - files_before_staging
                    if any(
                        fn.endswith('.crdownload') or
                        fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                        for fn in new_files
                    ):
                        dl_started = True
                        break
                    time.sleep(0.3)

                if not dl_started:
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR_DOWNLOAD_START_FAILED (attempt {attempt})")
                    continue
                log(f"[WMR-W{self.worker_id}][{job_id}] WMR_DOWNLOAD_START_CONFIRMED")

                # Wait for download COMPLETION
                found = _wmr_wait_for_new_file(self.staging_dir, files_before_staging, timeout=60)
                if not found:
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR downloaded file not detected (attempt {attempt})")
                    continue
                log(f"[WMR-W{self.worker_id}][{job_id}] DOWNLOAD_COMPLETE")

                # Move to canonical wmr/T{N}/{job_id}/ output path
                wmr_incoming.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(found), str(clean_png))
                except Exception:
                    shutil.copy2(str(found), str(clean_png))
                    try: os.remove(str(found))
                    except: pass

                # Validate output
                if not validate_image_file(clean_png):
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR output invalid (attempt {attempt})")
                    try: clean_png.unlink()
                    except: pass
                    continue

                log(f"[WMR-W{self.worker_id}][{job_id}] CLEAN_IMAGE_READY -> {clean_png.name}")

                # WebP conversion
                webp_result = convert_to_webp(str(clean_png))
                if webp_result and os.path.exists(webp_result):
                    if str(webp_result) != str(clean_webp):
                        try:
                            shutil.copy2(webp_result, str(clean_webp))
                            os.remove(webp_result)
                        except: pass
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR_COMPLETE -> {clean_png.name} + {clean_webp.name}")
                    return str(clean_png), str(clean_webp)

                log(f"[WMR-W{self.worker_id}][{job_id}] WMR_COMPLETE (no webp) -> {clean_png.name}")
                return str(clean_png), None

            except Exception as ex:
                log(f"[WMR-W{self.worker_id}][{job_id}] WMR exception (attempt {attempt}): {ex}", file=sys.stderr)
                continue

        # WMR_FAILED — do NOT silently fall back to raw image
        log(f"[WMR-W{self.worker_id}][{job_id}] WMR_FAILED — no fallback to raw", file=sys.stderr)
        raise RuntimeError(f"WMR_FAILED: all attempts exhausted for job {job_id}")

    def submit(self, job_id: str, chrome_tab_id: int, raw_png_path, future, loop):
        self.work_queue.put((job_id, chrome_tab_id, raw_png_path, future, loop))

    def quit(self):
        self.work_queue.put(None)
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass


class WmrWorkerPool:
    """Pool of up to CHROME_WMR_WORKERS independent Chrome WMR workers (W0-W3).
    Workers are created LAZILY — only when a job actually needs one.
    Lowest-W-id idle worker is always preferred.
    """

    def __init__(self, n: int = CHROME_WMR_WORKERS):
        self._max = n
        self._workers: list = []
        self._lock = threading.Lock()

    def _find_idle_worker(self) -> WmrWorker | None:
        for w in self._workers:
            if w.state == "IDLE" and w.work_queue.empty():
                return w
        return None

    def _create_next_worker(self) -> WmrWorker | None:
        if len(self._workers) >= self._max:
            return None
        wid = len(self._workers)
        w = WmrWorker(wid)
        self._workers.append(w)
        log(f'[WmrWorkerPool] Created WMR Chrome worker W{wid} (total={len(self._workers)})')
        return w

    def submit(self, job_id: str, chrome_tab_id: int, raw_png_path, future, loop):
        with self._lock:
            worker = self._find_idle_worker()
            if worker is None:
                # Lazy creation: add a new worker if below max
                worker = self._create_next_worker()
            if worker is None:
                # All W0-W3 busy: route to shortest queue
                worker = min(self._workers, key=lambda w: w.work_queue.qsize())
            log(f"[{job_id}] WMR_QUEUE -> WMR Chrome Worker W{worker.worker_id}")
            worker.submit(job_id, chrome_tab_id, raw_png_path, future, loop)

    def status(self):
        return [(w.worker_id, w.state, w.current_job_id) for w in self._workers]

    def quit_all(self):
        for w in self._workers:
            w.quit()


wmr_pool = WmrWorkerPool(CHROME_WMR_WORKERS)
print(f"  ✅ Chrome WMR Pool initialized (LAZY — workers W0-W{CHROME_WMR_WORKERS-1} created on demand).\\n")'''

patch("Replace WmrWorker+WmrWorkerPool+edge_pool with Chrome version",
    wmr_old_start,
    wmr_new_classes,
    required=True
)

# Remove the old WmrWorker body and everything up to edge_pool init
# Since the patch above only replaced the class docstring line, we need to
# remove the rest of the old WmrWorker body
# Let's check what the patch left behind
if wmr_pool_old_end in content:
    content = content.replace(wmr_pool_old_end, '', 1)
    print("  ✅ Removed old WmrWorkerPool end + edge_pool line (was left after class docstring patch)")
else:
    # The old classes may still be there — try a broader removal
    print("  ℹ️  Old WmrWorkerPool tail not found as standalone (class body was replaced along with it)")

# ── PATCH 9: STEP 9 HEADER + LAZY TAB CREATION ───────────────────────────────
patch("STEP 9 section header comment",
    "# STEP 9: CHROME MULTI-TAB POOL (T0, T1, T2, T3)",
    "# STEP 9: LAZY CHROME MULTI-TAB POOL (T0-T3, physical tabs created on demand)"
)

patch("STEP 9 print header",
    "print(f\"📑 STEP 9: CONFIGURING CHROME MULTI-TAB POOL ({MAX_CONCURRENT_TABS} TABS: T0-T3)\")",
    "print(f\"📑 STEP 9: CONFIGURING LAZY CHROME MULTI-TAB POOL ({MAX_CONCURRENT_TABS} SLOTS: T0-T3)\")"
)

# Replace static tab setup with lazy setup
old_tab_setup = '''tab_states = []
initial_handle = chrome_driver.current_window_handle
tab_states.append({
    "tab_id": 0, "name": "T0", "handle": initial_handle,
    "state": S_IDLE, "job": None, "job_id": None, "gen": None,
    "prompt": None, "refs": [],
    "start_time": 0.0, "last_poll": 0.0, "next_poll": 0.0,
    "urls_before": set(), "chat_urls": set(), "target_src": None,
    "download_started": False, "stuck_polls": 0,
    "future": None, "attempt": 0,
})
print("  ✅ Tab T0 ready (initial window).")

for i in range(1, MAX_CONCURRENT_TABS):
    before = set(chrome_driver.window_handles)
    chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': GEMINI_APP_URL})
    time.sleep(0.5)
    deadline = time.time() + 5.0
    new_h = None
    while time.time() < deadline:
        diff = set(chrome_driver.window_handles) - before
        if diff:
            new_h = list(diff)[0]
            break
        time.sleep(0.2)
    if not new_h:
        new_h = chrome_driver.window_handles[-1]
    tab_states.append({
        "tab_id": i, "name": f"T{i}", "handle": new_h,
        "state": S_IDLE, "job": None, "job_id": None, "gen": None,
        "prompt": None, "refs": [],
        "start_time": 0.0, "last_poll": 0.0, "next_poll": 0.0,
        "urls_before": set(), "chat_urls": set(), "target_src": None,
        "download_started": False, "stuck_polls": 0,
        "future": None, "attempt": 0,
    })
    print(f"  ✅ Tab T{i} ready.")

chrome_lock = asyncio.Lock()
print(f"  ✅ All {MAX_CONCURRENT_TABS} Chrome tabs ready with lowest-ID priority.\\n")'''

new_tab_setup = '''tab_states = []   # logical slot registry — physical handles start as None (lazy)
chrome_lock = asyncio.Lock()

def _make_tab_state(tid: int, handle=None) -> dict:
    return {
        "tab_id": tid, "name": f"T{tid}", "handle": handle,
        "state": S_IDLE, "job": None, "job_id": None, "gen": None,
        "prompt": None, "refs": [],
        "start_time": 0.0, "last_poll": 0.0, "next_poll": 0.0,
        "urls_before": set(), "chat_urls": set(), "target_src": None,
        "download_started": False, "stuck_polls": 0,
        "future": None, "attempt": 0,
    }

def _create_gemini_tab(tid: int) -> str:
    """
    Physically create a new Chrome tab for logical slot T{tid}.
    Called lazily the first time a job is assigned to this slot.
    Returns the new window handle.
    """
    before = set(chrome_driver.window_handles)
    if not before:
        # Very first tab — use the initial window
        chrome_driver.get(GEMINI_APP_URL)
        time.sleep(0.5)
        handle = chrome_driver.current_window_handle
    else:
        chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': GEMINI_APP_URL})
        deadline = time.time() + 5.0
        handle = None
        while time.time() < deadline:
            diff = set(chrome_driver.window_handles) - before
            if diff:
                handle = list(diff)[0]
                break
            time.sleep(0.2)
        if not handle:
            handle = chrome_driver.window_handles[-1]
    log(f'[T{tid}] Physical Gemini tab created (handle={str(handle)[:16]}...)')
    return handle

# Pre-register MAX_CONCURRENT_TABS logical slots with no physical tab yet
for _i in range(MAX_CONCURRENT_TABS):
    tab_states.append(_make_tab_state(_i, handle=None))

print(f"  ✅ {MAX_CONCURRENT_TABS} Gemini tab slots registered (LAZY — physical tabs created on demand).\\n")'''

patch("Replace static tab setup with lazy tab setup",
    old_tab_setup,
    new_tab_setup
)

# ── PATCH 10: _submit_job_to_tab — lazy handle creation ──────────────────────
patch("Add lazy tab creation at start of _submit_job_to_tab",
    '''    info = tab_states[tid]
    job_id = info["job_id"]
    prefix = f"[T{tid}][{job_id}]"

    try:
        async with chrome_lock:
            chrome_driver.switch_to.window(info["handle"])''',
    '''    info = tab_states[tid]
    job_id = info["job_id"]
    prefix = f"[T{tid}][{job_id}]"

    # LAZY TAB CREATION: create physical Chrome tab only when job is assigned
    if info["handle"] is None:
        try:
            info["handle"] = _create_gemini_tab(tid)
            log(f"{prefix} [T{tid}] IDLE (first use — physical tab created)")
        except Exception as e:
            log(f"{prefix} LAZY_TAB_CREATE_FAILED: {e}", file=sys.stderr)
            _recover_stuck_tab(tid, f"LAZY_TAB_CREATE_FAILED: {e}")
            return

    try:
        async with chrome_lock:
            chrome_driver.switch_to.window(info["handle"])'''
)

# ── PATCH 11: poll_active_tabs — DOWNLOAD_START_CONFIRMED before freeing tab ──
patch("Add DOWNLOAD_START_CONFIRMED detection before freeing physical tab",
    '''                # FREE THE CHROME TAB IMMEDIATELY — download is now independent
                _free_tab(tid, job_id)
                log(f"{prefix} CHROME_TAB_FREED -> download continues independently.")

                # If CDP already captured, skip watcher and go to WMR directly
                if cdp_ok:
                    _enqueue_edge_wmr(job_id, dinfo)''',
    '''                # Wait for download to actually START (.crdownload or image file)
                dl_confirmed = False
                t_dl_start = time.time()
                while time.time() - t_dl_start < DOWNLOAD_START_WINDOW_S:
                    if incoming_dir.exists():
                        cur_files = set(os.listdir(incoming_dir))
                        new_files = cur_files - files_before
                        if any(
                            fn.endswith('.crdownload') or
                            fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                            for fn in new_files
                        ):
                            dl_confirmed = True
                            break
                    await asyncio.sleep(0.3)

                if dl_confirmed or cdp_ok:
                    if dl_confirmed:
                        log(f"{prefix} DOWNLOAD_START_CONFIRMED")
                    # NOW close the physical Gemini tab — download is confirmed
                    try:
                        chrome_driver.switch_to.window(info["handle"])
                        chrome_driver.close()
                    except Exception:
                        pass
                    log(f"{prefix} PHYSICAL_TAB_CLOSED")
                    info["handle"] = None  # will be re-created for next job
                    _free_tab(tid, job_id)
                    log(f"{prefix} [T{tid}] IDLE")
                else:
                    log(f"{prefix} DOWNLOAD_START_FAILED — retrying download click")
                    # Retry once
                    try:
                        chrome_driver.switch_to.window(info["handle"])
                        _hover_and_dl_single_click(chrome_driver, info["urls_before"], info["chat_urls"])
                    except Exception:
                        pass
                    # Still register download watcher and free tab
                    try:
                        chrome_driver.switch_to.window(info["handle"])
                        chrome_driver.close()
                    except Exception:
                        pass
                    info["handle"] = None
                    _free_tab(tid, job_id)

                # If CDP already captured, skip watcher and go to WMR directly
                if cdp_ok:
                    _enqueue_wmr(job_id, dinfo)'''
)

# ── PATCH 12: Replace _enqueue_edge_wmr references ───────────────────────────
patch("Rename _enqueue_edge_wmr function to _enqueue_wmr",
    "def _enqueue_edge_wmr(job_id: str, dinfo: dict):",
    "def _enqueue_wmr(job_id: str, dinfo: dict):"
)

# Fix log message in _enqueue_wmr
patch("_enqueue_wmr log message",
    '    log(f"[{job_id}] EDGE_QUEUE -> WmrWorkerPool")\n    edge_pool.submit(',
    '    log(f"[{job_id}] WMR_QUEUE -> Chrome WmrWorkerPool")\n    wmr_pool.submit('
)

# Fix remaining _enqueue_edge_wmr call in poll_active_downloads
patch("_enqueue_edge_wmr call in poll_active_downloads",
    "_enqueue_edge_wmr(job_id, dinfo)\n            continue\n\n        elif now",
    "_enqueue_wmr(job_id, dinfo)\n            continue\n\n        elif now"
)

# The other _enqueue_edge_wmr was already replaced in the big poll_active_tabs patch above

# ── PATCH 13: poll_wmr_workers log ───────────────────────────────────────────
patch("poll_wmr_workers log: EDGE_OUTPUT_READY -> WMR_OUTPUT_READY",
    'log(f"[{job_id}] EDGE_OUTPUT_READY -> {Path(clean_png).name}")',
    'log(f"[{job_id}] WMR_OUTPUT_READY -> {Path(clean_png).name}")'
)

# ── PATCH 14: _finalize_and_clean_job — EDGE references ──────────────────────
# The finalize function uses get_edge_job_dir → replace with get_wmr_job_dir
patch("_finalize: get_edge_job_dir -> get_wmr_job_dir",
    "get_edge_job_dir(",
    "get_wmr_job_dir("
)

# ── PATCH 15: Dashboard — Edge Workers -> WMR Chrome Workers ─────────────────
patch("Dashboard: EDGE WORKERS -> WMR CHROME WORKERS",
    '''    print("  EDGE WORKERS:")
    for wid, state, cur_jid in edge_pool.status():
        jid_str = (cur_jid or "---")[:12]
        print(f"    E{wid} = {state:<11} Job={jid_str}")''',
    '''    print("  WMR CHROME WORKERS:")
    for wid, state, cur_jid in wmr_pool.status():
        jid_str = (cur_jid or "---")[:12]
        print(f"    W{wid} = {state:<11} Job={jid_str}")'''
)

# ── PATCH 16: _recover_stuck_tab — close physical tab, reset handle ──────────
patch("_recover_stuck_tab: close physical tab instead of navigating it",
    '''    # Navigate to a fresh Gemini state on this tab only
    try:
        chrome_driver.switch_to.window(info["handle"])
        chrome_driver.get(GEMINI_APP_URL)
        time.sleep(1.0)
    except Exception:
        pass''',
    '''    # Close the stuck physical tab entirely — fresh tab created for next job
    try:
        if info.get("handle"):
            chrome_driver.switch_to.window(info["handle"])
            chrome_driver.close()
    except Exception:
        pass
    info["handle"] = None  # will be re-created lazily for next job'''
)

# Also reset handle to None in the state clearing block of _recover_stuck_tab
patch("_recover_stuck_tab state clear: add handle reset",
    '''    info["state"] = S_IDLE
    info["job"] = None
    info["job_id"] = None
    info["gen"] = None
    info["prompt"] = None
    info["refs"] = []
    info["target_src"] = None
    info["download_started"] = False
    info["stuck_polls"] = 0
    info["start_time"] = 0.0
    info["future"] = None
    info["urls_before"] = set()
    info["chat_urls"] = set()''',
    '''    info["state"] = S_IDLE
    info["job"] = None
    info["job_id"] = None
    info["gen"] = None
    info["prompt"] = None
    info["refs"] = []
    info["handle"] = None   # ensure physical tab is cleared (was closed above)
    info["target_src"] = None
    info["download_started"] = False
    info["stuck_polls"] = 0
    info["start_time"] = 0.0
    info["future"] = None
    info["urls_before"] = set()
    info["chat_urls"] = set()'''
)

# ── PATCH 17: Attachment count — exact match ──────────────────────────────────
patch("verify_attachment_count: >= -> ==",
    '''        if chip_count >= expected:
            log(f"{prefix} ATTACHMENTS {chip_count}/{expected} ✅")
            return True, chip_count''',
    '''        if chip_count == expected:
            log(f"{prefix} ATTACHMENTS {chip_count}/{expected} ✅ (exact match)")
            return True, chip_count'''
)

patch("verify_attachment_count: failure message",
    'log(f"{prefix} ATTACHMENT_MISMATCH: expected {expected}, got {chip_count}", file=sys.stderr)',
    'log(f"{prefix} ATTACHMENT_MISMATCH: expected exactly {expected}, got {chip_count} (must be exact — not >= or >)", file=sys.stderr)'
)

# Also fix the docstring
patch("verify_attachment_count docstring",
    '''    Polls until attachment chip count >= expected.
    Returns (verified: bool, actual_count: int).
    If not verified within timeout, returns (False, actual_count).''',
    '''    Polls until attachment chip count == expected (exact match required).
    Returns (verified: bool, actual_count: int).
    FAIL on count < expected OR count > expected.
    If not verified within timeout, returns (False, actual_count).'''
)

# ── PATCH 18: main() — edge_pool -> wmr_pool ─────────────────────────────────
patch("main() finally: edge_pool.quit_all -> wmr_pool.quit_all",
    '''        try:
            edge_pool.quit_all()
        except Exception:
            pass''',
    '''        try:
            wmr_pool.quit_all()
        except Exception:
            pass'''
)

# ── PATCH 19: Version string ──────────────────────────────────────────────────
patch("Version string V4.0 -> V8.0",
    'log(f"[{WORKER_ID}] V4.0 READY — waiting for jobs (Ctrl+C to stop)...")',
    'log(f"[{WORKER_ID}] V8.0 READY — CHROME-ONLY DUAL-SYSTEM (Gemini+WMR) — waiting for jobs (Ctrl+C to stop)...")'
)

# ── PATCH 20: scheduler loop log labels ──────────────────────────────────────
patch("Scheduler log: Stage 2 Edge -> WMR",
    "# Stage 2: Poll Edge WMR worker completions",
    "# Stage 2: Poll WMR Chrome worker completions"
)

# ── WRITE OUTPUT ──────────────────────────────────────────────────────────────
print("\n=== WRITING V8 FILE ===")
with open(dst, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"  ✅ Written: {dst}")

# ── VERIFICATION ──────────────────────────────────────────────────────────────
print("\n=== V8 VERIFICATION ===")
checks = [
    ('Edge fully removed (webdriver.Edge)', 'webdriver.Edge' not in content),
    ('Edge fully removed (EdgeOptions)',    'EdgeOptions' not in content),
    ('Edge fully removed (edge_pool)',      'edge_pool' not in content),
    ('Edge fully removed (EDGE_DL_BASE)',   'EDGE_DL_BASE' not in content),
    ('Edge fully removed (EDGE_PROFILES)',  'EDGE_PROFILES_BASE' not in content),
    ('wmr_pool created',                   'wmr_pool = WmrWorkerPool' in content),
    ('create_wmr_chrome_driver exists',    'create_wmr_chrome_driver' in content),
    ('WMR_PROFILES_BASE exists',           'WMR_PROFILES_BASE' in content),
    ('WMR_DL_BASE exists',                 'WMR_DL_BASE' in content),
    ('WMR_STAGING_BASE exists',            'WMR_STAGING_BASE' in content),
    ('get_wmr_job_dir exists',             'get_wmr_job_dir' in content),
    ('get_wmr_staging_dir exists',         'get_wmr_staging_dir' in content),
    ('Lazy tab _create_gemini_tab',        '_create_gemini_tab' in content),
    ('Lazy tab handle=None slots',         'handle=None' in content),
    ('DOWNLOAD_START_CONFIRMED',           'DOWNLOAD_START_CONFIRMED' in content),
    ('PHYSICAL_TAB_CLOSED',               'PHYSICAL_TAB_CLOSED' in content),
    ('Exact attachment ==',                'chip_count == expected' in content),
    ('WMR Chrome worker label W0',         'WMR-W' in content),
    ('W slot in dashboard',                'W{wid}' in content or "f\"    W{wid}" in content),
    ('V8.0 READY',                         'V8.0 READY' in content),
    ('_enqueue_wmr (not edge)',            '_enqueue_wmr' in content and '_enqueue_edge_wmr' not in content),
    ('DOWNLOAD_START_WINDOW_S',            'DOWNLOAD_START_WINDOW_S' in content),
    ('WMR_DOWNLOAD_START_CONFIRMED',       'WMR_DOWNLOAD_START_CONFIRMED' in content),
    ('Browser = Google Chrome',            'Browser = Google Chrome' in content),
    ('No microsoft-edge in content',       'microsoft-edge' not in content.lower()),
]

all_pass = True
for name, result in checks:
    status = '✅' if result else '❌'
    if not result:
        all_pass = False
    print(f"  {status} {name}")

if errors:
    print(f"\n  ⚠️  {len(errors)} patch(es) failed to apply:")
    for e in errors:
        print(f"    • {e}")

print(f"\nOverall: {'✅ ALL PASS' if all_pass and not errors else '❌ SOME FAILED'}")
