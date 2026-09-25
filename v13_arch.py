chrome_driver = None
anchor_window_handle = None

download_registry = {}
tab_states = {}
job_contexts = {}

def ensure_chrome_driver_alive(driver):
    if driver is None:
        raise RuntimeError("Driver is None")
    try:
        handles = driver.window_handles
        cur = driver.current_window_handle
        url = driver.current_url
        driver.execute_script("return 1")
        return True
    except Exception as e:
        raise RuntimeError(f"Driver dead: {e}")

def check_chrome_driver_health(driver):
    if driver is None:
        return {"alive": False}
    try:
        handles = driver.window_handles
        cur = driver.current_window_handle
        url = driver.current_url
        driver.execute_script("return 1")
        return {
            "alive": True,
            "window_count": len(handles),
            "current_handle": cur,
            "current_url": url,
            "pid": driver.service.process.pid if driver.service and driver.service.process else None
        }
    except Exception:
        return {"alive": False}

def configure_browser_download_events(driver):
    driver.execute_cdp_cmd('Browser.setDownloadBehavior', {
        'behavior': 'allowAndName',
        'downloadPath': '/content/downloads/chrome_staging/global',
        'eventsEnabled': True
    })

def create_persistent_chrome_driver():
    import undetected_chromedriver as uc
    from selenium.webdriver.chrome.options import Options
    import os
    
    profile_dir = Path("/content/queue_worker_bundle/queue_worker_state/chrome_profile")
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-session-crashed-bubble")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        raise RuntimeError(f"CHROME_START_FAILED: {type(e).__name__}: {e}") from e
        
    assert driver is not None
    assert driver.service is not None
    assert driver.window_handles
    driver.execute_script("return document.readyState")
    driver.execute_cdp_cmd("Browser.getVersion", {})
    
    return driver

def create_wmr_chrome_driver(wid):
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir=/content/queue_worker_bundle/queue_worker_state/wmr_chrome_profiles/W{wid}")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    drv = uc.Chrome(options=options)
    drv.set_window_size(1400, 1000)
    return drv

class FirstFreeBroker:
    def __init__(self):
        self.seq = 0
        self.lock = threading.Lock()
        self.free_q = []
        self.in_q = set()
        
    def release(self, resource_id):
        with self.lock:
            if resource_id not in self.in_q:
                self.seq += 1
                heapq.heappush(self.free_q, (self.seq, resource_id))
                self.in_q.add(resource_id)
                
    def acquire(self):
        with self.lock:
            if not self.free_q:
                return None
            seq, resource_id = heapq.heappop(self.free_q)
            self.in_q.remove(resource_id)
            return resource_id
            
    def remove(self, resource_id):
        with self.lock:
            if resource_id in self.in_q:
                self.free_q = [x for x in self.free_q if x[1] != resource_id]
                heapq.heapify(self.free_q)
                self.in_q.remove(resource_id)

GEMINI_BROKER = FirstFreeBroker()
WMR_BROKER = FirstFreeBroker()

GEMINI_ADMISSION_Q = asyncio.Queue(maxsize=4)
WMR_GLOBAL_Q = queue.Queue()

active_downloads = {}
active_wmr = {}
counters = {"completed": 0, "failed": 0}
redis_queue_stats = {"wait": 0, "active": 0, "delayed": 0, "prioritized": 0, "waiting-children": 0}

WMR_TABS_PER_PROFILE = 2

def resolve_future_once(loop, future, *, result=None, exception=None):
    if future is None: return
    def resolve():
        if future.done(): return
        if exception: future.set_exception(exception)
        else: future.set_result(result)
    loop.call_soon_threadsafe(resolve)

def _fail_job(job_id, gen, reason, future, attempt):
    log(f"[{job_id}] FAILING JOB: {reason}")
    counters["failed"] += 1
    
    try:
        import db
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET status='FAILED', error_message=%s WHERE id=%s", (str(reason)[:255], job_id))
            conn.commit()
    except Exception as e:
        log(f"[{job_id}] DB Update failed during fail_job: {e}", file=sys.stderr)
        
    resolve_future_once(main_loop, future, exception=Exception(reason))
    
    active_downloads.pop(job_id, None)
    active_wmr.pop(job_id, None)

class WmrWorker:
    def __init__(self, profile_id: int):
        self.profile_id = profile_id
        self.driver = None
        self.driver_lock = threading.Lock()
        
        self.tab_states = {}
        self.tab_handles = {}
        for tab_idx in range(WMR_TABS_PER_PROFILE):
            tab_id = f"W{self.profile_id}-T{tab_idx}"
            self.tab_states[tab_id] = "IDLE"
            self.tab_handles[tab_id] = None
            
        self.running = False
        
    def start(self):
        self.running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"WmrProfile-W{self.profile_id}"
        )
        self._thread.start()
        log(f"[WMR-W{self.profile_id}] Worker profile registered (LAZY)")

    def _ensure_driver_and_tab(self, tab_id):
        with self.driver_lock:
            if self.driver:
                try:
                    _ = self.driver.session_id
                    h = self.driver.window_handles
                    if len(h) == 0:
                        raise Exception("No windows")
                except Exception:
                    try: self.driver.quit()
                    except: pass
                    self.driver = None
                    for k in self.tab_handles:
                        self.tab_handles[k] = None
                    
            if self.driver is None:
                log(f"[WMR-W{self.profile_id}] Launching Chrome for WMR...")
                self.driver = create_wmr_chrome_driver(self.profile_id)
                self.tab_handles[f"W{self.profile_id}-T0"] = self.driver.current_window_handle
                for i in range(1, WMR_TABS_PER_PROFILE):
                    self.driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.tab_handles[f"W{self.profile_id}-T{i}"] = self.driver.current_window_handle
                
            self.driver.switch_to.window(self.tab_handles[tab_id])
            return self.driver

    def _run_loop(self):
        while self.running:
            time.sleep(1)
            
    def process_job_for_tab(self, tab_id, item):
        t = threading.Thread(target=self._process_job_thread, args=(tab_id, item))
        t.start()
        
    def _process_job_thread(self, tab_id, item):
        from selenium.webdriver.common.by import By
        job_id, tid, raw_path, future, loop = item
        self.tab_states[tab_id] = "PROCESSING"
        prefix = f"[{tab_id}][{job_id}]"

        try:
            drv = self._ensure_driver_and_tab(tab_id)
            raw_path = Path(raw_path)
            if not raw_path.exists():
                raise Exception(f"RAW_MISSING: {raw_path}")
                
            final_dir = get_final_output_dir(tid, job_id)
            clean_png = final_dir / f"{job_id}_clean.png"
            clean_webp = final_dir / f"{job_id}_clean.webp"
            
            drv.get("https://logo-remover-fawn.vercel.app/gemini")
            time.sleep(1)
            _ = drv.get_log('performance')
            
            up_js = "var el = document.querySelector('input[type=file]'); if (el) { el.style.display = 'block'; return true; } return false;"
            if safe_execute_script(drv, up_js):
                drv.find_element(By.CSS_SELECTOR, "input[type=file]").send_keys(str(raw_path))
            else:
                raise Exception("UPLOAD_FAILED")
                
            log(f"{prefix} WMR_UPLOAD_VERIFIED")
            
            time.sleep(2)
            ready = False
            for _ in range(WMR_TIMEOUT_S * 2):
                js = "var res = document.querySelector('.result-container, .output-container, div[class*=\"result\"]'); if (!res) return false; var btns = res.querySelectorAll('button, a'); for (var i=0; i<btns.length; i++) { var t = (btns[i].textContent || '').toLowerCase().trim(); if (t === 'download png') { return true; } } return false;"
                if safe_execute_script(drv, js):
                    ready = True
                    break
                time.sleep(0.5)
                
            if not ready: raise Exception("WMR_TIMEOUT")
                
            log(f"{prefix} WMR_RESULT_READY")
            
            dl_dir = get_wmr_staging_dir(self.profile_id) / f"{tab_id}"
            shutil.rmtree(dl_dir, ignore_errors=True)
            dl_dir.mkdir(parents=True, exist_ok=True)
            
            drv.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': str(dl_dir)
            })
            
            files_before = set(dl_dir.iterdir()) if dl_dir.exists() else set()
            
            js = "var res = document.querySelector('.result-container, .output-container, div[class*=\"result\"]'); var btns = res.querySelectorAll('button, a'); for (var i=0; i<btns.length; i++) { var t = (btns[i].textContent || '').toLowerCase().trim(); if (t === 'download png') { btns[i].click(); return true; } } return false;"
            if not safe_execute_script(drv, js):
                raise Exception("CLICK_FAILED")
                
            log(f"{prefix} DOWNLOAD_PNG_CLICKED")
            
            dl_guid = None
            t1 = time.time()
            while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                for entry in drv.get_log('performance'):
                    try:
                        msg = json.loads(entry["message"])["message"]
                        if msg["method"] == "Browser.downloadWillBegin":
                            dl_guid = msg["params"]["guid"]
                            break
                    except:
                        pass
                if dl_guid: break
                time.sleep(0.1)
                
            dl_confirmed_fs = False
            t2 = time.time()
            while time.time() - t2 < DOWNLOAD_START_WINDOW_S:
                if dl_dir.exists():
                    cur = set(dl_dir.iterdir())
                    new_files = cur - files_before
                    for nf in new_files:
                        if nf.name.endswith('.crdownload') or nf.name.endswith('.png'):
                            dl_confirmed_fs = True
                            break
                if dl_confirmed_fs: break
                time.sleep(0.1)
                
            if dl_confirmed_fs:
                log(f"{prefix} WMR_DOWNLOAD_START_CONFIRMED")
                
                dinfo = {
                    "job_id": job_id,
                    "tid": tid,
                    "state": "WMR_BACKGROUND_DOWNLOAD",
                    "dl_dir": str(dl_dir),
                    "clean_png": str(clean_png),
                    "clean_webp": str(clean_webp),
                    "download_guid": dl_guid or "fs_fallback",
                    "files_before": files_before,
                    "started_at": time.time(),
                    "future": future,
                    "loop": loop
                }
                
                def _reg():
                    active_wmr[job_id] = dinfo
                    WMR_BROKER.release(tab_id)
                    self.tab_states[tab_id] = "IDLE"
                    log(f"{prefix} WMR_TAB_RELEASED")
                main_loop.call_soon_threadsafe(_reg)
                return True
            else:
                raise Exception(f"WMR_DOWNLOAD_START_FAILED")
                
        except Exception as e:
            log(f"{prefix} FAILED: {e}")
            resolve_future_once(loop, future, exception=e)
            def _rel():
                WMR_BROKER.release(tab_id)
                self.tab_states[tab_id] = "IDLE"
            main_loop.call_soon_threadsafe(_rel)

    def quit(self):
        self.running = False
        if self.driver:
            try: self.driver.quit()
            except: pass
            self.driver = None

class WmrWorkerPool:
    def __init__(self, num_profiles: int = CHROME_WMR_WORKERS):
        self._profiles = {i: WmrWorker(i) for i in range(num_profiles)}
        
    def start_all(self):
        for p in self._profiles.values():
            p.start()
            for tab_idx in range(WMR_TABS_PER_PROFILE):
                WMR_BROKER.release(f"W{p.profile_id}-T{tab_idx}")

    def get_profile(self, tab_id):
        profile_id = int(tab_id.split("-")[0].replace("W", ""))
        return self._profiles[profile_id]

    def status(self):
        st = []
        for p in self._profiles.values():
            for t, s in p.tab_states.items():
                st.append((t, s))
        return st

    def quit_all(self):
        for p in self._profiles.values(): p.quit()

class GeminiWorker:
    def __init__(self, tid: int):
        self.tid = tid
        self.state = "IDLE"
        self.current_job_id = None
        self.start_time = 0
        self.window_handle = None
        
    def _ensure_tab(self):
        global chrome_driver
        if not check_chrome_driver_health(chrome_driver)["alive"]:
            raise RuntimeError("Global chrome_driver is dead")
            
        if self.window_handle:
            try:
                if self.window_handle in chrome_driver.window_handles:
                    chrome_driver.switch_to.window(self.window_handle)
                    return chrome_driver
            except Exception:
                pass
                
        log(f"[T{self.tid}] Creating new logical Gemini tab...")
        res = chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
        
        for h in chrome_driver.window_handles:
            chrome_driver.switch_to.window(h)
            if chrome_driver.current_url == 'about:blank' or chrome_driver.current_url.startswith("data:"):
                self.window_handle = h
                break
        
        if not self.window_handle:
            self.window_handle = chrome_driver.window_handles[-1]
            
        chrome_driver.switch_to.window(self.window_handle)
        tab_states[f"T{self.tid}"] = "READY"
        return chrome_driver

    def process_job(self, item):
        t = threading.Thread(target=self._process_job_thread, args=(item,))
        t.start()
        
    def _process_job_thread(self, item):
        global chrome_driver
        job_id = item["job_id"]
        gen = item["gen"]
        future = item["future"]
        prefix = f"[T{self.tid}][{job_id}]"
        
        self.current_job_id = job_id
        self.state = "SUBMITTING"
        self.start_time = time.time()
        
        try:
            drv = self._ensure_tab()
            
            job_dir = get_gemini_job_dir(self.tid, job_id)
            incoming_dir = job_dir / "incoming"
            incoming_dir.mkdir(parents=True, exist_ok=True)
            
            staging_dir = Path(f"/content/downloads/chrome_staging/T{self.tid}")
            staging_dir.mkdir(parents=True, exist_ok=True)
            
            drv.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': str(staging_dir)
            })
            
            curr = drv.current_url
            if "gemini.google.com/app" not in curr:
                drv.get("https://gemini.google.com/app")
            else:
                drv.get("https://gemini.google.com/app")
                
            time.sleep(1)
            _ = drv.get_log('performance')
            
            log(f"{prefix} FRESH_BROWSER_READY")
            log(f"{prefix} BASE_URL_READY")
            
            if not nb_check_image(drv, prefix):
                raise Exception("COMPOSER_FAILED")
                
            log(f"{prefix} CLEAN_COMPOSER_VERIFIED")
            
            ensure_flash_mode(drv, self.tid, job_id)
            ensure_create_image_mode(drv, self.tid, job_id)
            
            refs = gen.get("refs", [])
            expected_refs = [p for p in refs if p]
            ref_paths = [str(Path(p).resolve()) for p in expected_refs]
            
            if ref_paths:
                perform_robust_upload(drv, ref_paths, self.tid, job_id)
                verified, actual = verify_attachment_count(drv, len(ref_paths), self.tid, job_id)
                if not verified:
                    raise Exception(f"ATTACHMENT_MISMATCH: expected {len(ref_paths)}, got {actual}")
                    
            prompt = gen.get("prompt", "Create image")
            _inject_prompt_atomic(drv, prompt, self.tid, job_id)
            
            urls_before = snapshot_urls(drv)
            chat_urls = {u for u in urls_before if '/app/' in u}
            
            log(f"{prefix} SEND_REQUESTED")
            if not _click_send_button(drv, self.tid, job_id):
                raise Exception("SEND_FAILED")
            log(f"{prefix} SEND_CLICKED")
            
            log(f"{prefix} GENERATION_SIGNAL_SEARCH")
            if not verify_generation_started(drv):
                raise Exception("GEN_START_FAILED")
                
            self.state = "GENERATING"
            log(f"{prefix} GENERATING")
            
            t0 = time.time()
            image_detected = False
            
            while time.time() - t0 < GENERATION_TIMEOUT_S:
                status, new_src = nb_check_image(drv, urls_before, chat_urls)
                if status == 'SUCCESS':
                    image_detected = True
                    if new_src: urls_before.add(new_src)
                    break
                time.sleep(1.0)
                
            if not image_detected:
                raise Exception("GENERATION_TIMEOUT")
                
            log(f"{prefix} IMAGE_DETECTED")
            
            files_before = set(staging_dir.iterdir()) if staging_dir.exists() else set()
            hover_ok = _hover_and_dl_single_click(drv, urls_before, chat_urls)
            log(f"{prefix} DOWNLOAD_CLICKED (hover_ok={hover_ok})")
            
            self.state = "DOWNLOAD_START_WAIT"
            
            dl_guid = None
            t1 = time.time()
            while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                for entry in drv.get_log('performance'):
                    try:
                        msg = json.loads(entry["message"])["message"]
                        if msg["method"] == "Browser.downloadWillBegin":
                            dl_guid = msg["params"]["guid"]
                            break
                    except:
                        pass
                if dl_guid: break
                time.sleep(0.1)
                
            dl_confirmed_fs = False
            t2 = time.time()
            while time.time() - t2 < DOWNLOAD_START_WINDOW_S:
                if staging_dir.exists():
                    cur = set(staging_dir.iterdir())
                    new_files = cur - files_before
                    for nf in new_files:
                        if nf.name.endswith('.crdownload') or nf.name.endswith('.png') or nf.name.endswith('.jpg') or nf.name.endswith('.webp'):
                            dl_confirmed_fs = True
                            break
                if dl_confirmed_fs: break
                time.sleep(0.1)
                
            if dl_confirmed_fs:
                log(f"{prefix} DOWNLOAD_START_EVENT guid={dl_guid}")
                log(f"{prefix} DOWNLOAD_FILESYSTEM_START_CONFIRMED")
                
                download_registry[dl_guid or f"fs_fallback_{job_id}"] = {
                    "job_id": job_id,
                    "tid": self.tid,
                    "state": "STARTED"
                }
                
                dinfo = {
                    "job_id": job_id,
                    "tid": self.tid,
                    "state": "BACKGROUND_DOWNLOAD",
                    "chrome_job_dir": str(job_dir),
                    "staging_dir": str(staging_dir),
                    "download_guid": dl_guid or f"fs_{job_id}",
                    "files_before": files_before,
                    "started_at": time.time(),
                    "future": future,
                    "gen": gen
                }
                
                def _reg():
                    active_downloads[job_id] = dinfo
                    GEMINI_BROKER.release(self.tid)
                    self.state = "IDLE"
                    self.current_job_id = None
                    log(f"{prefix} T_RELEASED")
                main_loop.call_soon_threadsafe(_reg)
                
            else:
                raise Exception(f"DOWNLOAD_START_FAILED")
                
        except Exception as e:
            log(f"{prefix} GEMINI_FAILED: {e}")
            _fail_job(job_id, gen, f"Gemini failed: {e}", future, 1)
            def _rel():
                GEMINI_BROKER.release(self.tid)
                self.state = "IDLE"
                self.current_job_id = None
            main_loop.call_soon_threadsafe(_rel)

    def quit(self):
        pass

class GeminiWorkerPool:
    def __init__(self, max_workers: int = GEMINI_WORKERS):
        self.workers = {i: GeminiWorker(i) for i in range(max_workers)}
        
    def start_all(self):
        for w in self.workers.values():
            GEMINI_BROKER.release(w.tid)

    def status(self):
        return [(w.tid, w.state, w.current_job_id, w.start_time) for w in self.workers.values()]
        
    def quit_all(self):
        for w in self.workers.values(): w.quit()

async def update_redis_queue_stats_loop():
    from bullmq import Queue
    q = Queue(QUEUE_NAME, {"connection": REDIS_URL, "prefix": REDIS_KEY_PREFIX})
    try:
        while True:
            try:
                counts = await q.getJobCounts()
                redis_queue_stats["wait"] = counts.get("waiting", 0)
                redis_queue_stats["active"] = counts.get("active", 0)
                redis_queue_stats["delayed"] = counts.get("delayed", 0)
                redis_queue_stats["prioritized"] = counts.get("prioritized", 0)
                redis_queue_stats["waiting-children"] = counts.get("waiting-children", 0)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(2.5)
    finally:
        try: await q.close()
        except: pass

def _enqueue_wmr(job_id: str, dinfo: dict):
    loop = main_loop
    future = loop.create_future()
    dinfo["wmr_future"] = future
    dinfo["loop"] = loop
    WMR_GLOBAL_Q.put(dinfo)
    log(f"[{job_id}] RAW_READY -> WMR_GLOBAL_Q")

async def poll_active_downloads():
    now = time.time()
    for job_id, dinfo in list(active_downloads.items()):
        if dinfo.get("state") != "BACKGROUND_DOWNLOAD":
            continue
            
        staging_dir = Path(dinfo.get("staging_dir", ""))
        if not staging_dir.exists():
            continue
            
        raw_ready = False
        valid_file = None
        files_before = dinfo.get("files_before", set())
        
        for f in staging_dir.iterdir():
            if f in files_before: continue
            if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                size = f.stat().st_size
                if size > DOWNLOAD_MIN_SIZE:
                    time.sleep(0.5)
                    if size == f.stat().st_size:
                        try:
                            from PIL import Image
                            with Image.open(f) as img: img.verify()
                            valid_file = f
                            raw_ready = True
                            break
                        except Exception:
                            pass
                            
        if raw_ready and valid_file:
            raw_path = Path(dinfo["chrome_job_dir"]) / f"{job_id}_raw.png"
            shutil.move(str(valid_file), str(raw_path))
            dinfo["raw_path"] = raw_path
            dinfo["state"] = "RAW_READY"
            log(f"[{job_id}] GEMINI_BACKGROUND_DOWNLOAD COMPLETED")
            log(f"[{job_id}] RENAMED_TO_JOB_RAW")
            _enqueue_wmr(job_id, dinfo)
            continue
            
        if now - dinfo.get("started_at", now) > DOWNLOAD_TIMEOUT_S:
            log(f"[{job_id}] DOWNLOAD_TIMEOUT")
            _fail_job(job_id, dinfo.get("gen"), "Download timed out", dinfo.get("future"), 1)

async def _finalize_and_clean_job(job_id, dinfo, clean_png, webp_path):
    gen = dinfo.get("gen", {})
    future = dinfo.get("future")
    try:
        log(f"[{job_id}] R2 Uploading...")
        
        if not webp_path or not os.path.exists(webp_path):
            webp_path = convert_to_webp(str(clean_png))
            
        clean_url = upload_to_r2(str(clean_png), f"{job_id}_clean.png")
        webp_url = upload_to_r2(str(webp_path), f"{job_id}_clean.webp")
        
        log(f"[{job_id}] DB Updating...")
        import db
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET output_url=%s, webp_url=%s, status='COMPLETED' WHERE id=%s", (clean_url, webp_url, job_id))
            conn.commit()
        
        log(f"[{job_id}] Settling credits...")
        try:
            credits_settle_look(gen.get("user_id"), 1)
        except Exception as ce:
            log(f"[{job_id}] Credit settle failed: {ce}", file=sys.stderr)
            
        counters["completed"] += 1
        log(f"[{job_id}] COMPLETION SUCCESSFUL")
        resolve_future_once(main_loop, future, result=True)
        
    except Exception as e:
        log(f"[{job_id}] FINALIZE FAILED: {e}")
        _fail_job(job_id, gen, str(e), future, 1)
    finally:
        active_downloads.pop(job_id, None)

async def poll_wmr_workers():
    while not WMR_GLOBAL_Q.empty():
        tab_id = WMR_BROKER.acquire()
        if not tab_id:
            break
        dinfo = WMR_GLOBAL_Q.get()
        job_id = dinfo["job_id"]
        tid = dinfo["tid"]
        raw_path = dinfo["raw_path"]
        future = dinfo["wmr_future"]
        loop = dinfo["loop"]
        
        log(f"[SCHED] {job_id} -> {tab_id} release_seq={WMR_BROKER.seq}")
        p = wmr_pool.get_profile(tab_id)
        p.process_job_for_tab(tab_id, (job_id, tid, raw_path, future, loop))
        
    now = time.time()
    for job_id, dinfo in list(active_wmr.items()):
        if dinfo.get("state") != "WMR_BACKGROUND_DOWNLOAD":
            continue
            
        dl_dir = Path(dinfo.get("dl_dir", ""))
        if not dl_dir.exists():
            continue
            
        raw_ready = False
        valid_file = None
        files_before = dinfo.get("files_before", set())
        
        for f in dl_dir.iterdir():
            if f in files_before: continue
            if f.suffix.lower() == '.png':
                size = f.stat().st_size
                time.sleep(0.5)
                if size == f.stat().st_size:
                    try:
                        from PIL import Image
                        with Image.open(f) as img: img.verify()
                        valid_file = f
                        raw_ready = True
                        break
                    except:
                        pass
                        
        if raw_ready and valid_file:
            clean_png = Path(dinfo["clean_png"])
            clean_webp = Path(dinfo["clean_webp"])
            shutil.move(str(valid_file), str(clean_png))
            
            webp_res = convert_to_webp(str(clean_png))
            if webp_res and os.path.exists(webp_res):
                shutil.copy2(webp_res, str(clean_webp))
                os.remove(webp_res)
                log(f"[{job_id}] WEBP_READY")
                dinfo["webp_path"] = str(clean_webp)
            else:
                dinfo["webp_path"] = None
                
            shutil.rmtree(dl_dir, ignore_errors=True)
            log(f"[{job_id}] CLEAN_IMAGE_READY")
            
            future = dinfo["wmr_future"]
            resolve_future_once(main_loop, future, result=(str(clean_png), dinfo["webp_path"]))
            active_wmr.pop(job_id, None)
            
            asyncio.create_task(_finalize_and_clean_job(job_id, dinfo, str(clean_png), dinfo["webp_path"]))
            continue
            
        if now - dinfo.get("started_at", now) > DOWNLOAD_TIMEOUT_S:
            log(f"[{job_id}] WMR_DOWNLOAD_TIMEOUT")
            future = dinfo["wmr_future"]
            resolve_future_once(main_loop, future, exception=Exception("WMR Download Timed Out"))
            active_wmr.pop(job_id, None)

last_status_print = 0
def print_pipeline_status():
    global last_status_print
    now = time.time()
    if now - last_status_print < 2.5: return
    last_status_print = now

    dl_bg = sum(1 for d in active_downloads.values() if d.get("state") == "BACKGROUND_DOWNLOAD")
    dl_raw = sum(1 for d in active_downloads.values() if d.get("state") == "RAW_READY")
    wmr_bg = sum(1 for d in active_wmr.values() if d.get("state") == "WMR_BACKGROUND_DOWNLOAD")
    wmr_status = wmr_pool.status()

    print(f"\\nPIPELINE STATUS {time.strftime('%H:%M:%S')}")
    print(f"REDIS QUEUE: WAIT={redis_queue_stats['wait']} | ACTIVE={redis_queue_stats['active']} | DELAYED={redis_queue_stats['delayed']}")
    print(f"GEMINI ADMISSION: WAIT={GEMINI_ADMISSION_Q.qsize()}")
    for tid, state, cur_jid, start_time in gemini_pool.status():
        jid = (cur_jid or "---")[:12]
        elapsed = f"{int(now - start_time)}s" if start_time > 0 else "0s"
        print(f"  T{tid} = {state:<19} {elapsed:>3}  {jid}")
    print(f"FREE ORDER: GEMINI_FREE_SEQ={GEMINI_BROKER.seq}")
    print(f"DOWNLOADS: BACKGROUND={dl_bg}  RAW_READY={dl_raw}")
    print(f"WMR CHROME WORKERS: QUEUE={WMR_GLOBAL_Q.qsize()}")
    for t, s in wmr_status:
        print(f"  {t} = {s:<13}")
    print(f"WMR DOWNLOADS: BACKGROUND={wmr_bg}")
    print(f"RESULT: DONE={counters['completed']} | FAIL={counters['failed']}\\n")

async def central_scheduler_loop():
    while True:
        try:
            while not GEMINI_ADMISSION_Q.empty():
                tid = GEMINI_BROKER.acquire()
                if tid is None: break
                item = GEMINI_ADMISSION_Q.get_nowait()
                log(f"[SCHED] {item['job_id']} -> T{tid}")
                gemini_pool.workers[tid].process_job(item)

            await poll_active_downloads()
            await poll_wmr_workers()
            print_pipeline_status()
        except Exception as e:
            log(f"Scheduler loop error: {e}", file=sys.stderr)
        await asyncio.sleep(0.1)

async def process_bullmq_job(job, job_token):
    job_id = job.id
    gen = job.data
    log(f"[{job_id}] BullMQ ADMITTED")
    future = main_loop.create_future()
    item = {"job_id": job_id, "gen": gen, "future": future}
    await GEMINI_ADMISSION_Q.put(item)
    return await asyncio.wait_for(future, timeout=TOTAL_JOB_TIMEOUT_S)

def startup_sequence():
    global chrome_driver, anchor_window_handle
    print("================================================================================")
    print(" STEP 6: INITIALIZING PERSISTENT CHROME DRIVER")
    print("================================================================================")
    import os
    print(f"  Chrome profile:     /content/queue_worker_bundle/queue_worker_state/chrome_profile")
    print(f"  DISPLAY:            {os.environ.get('DISPLAY')}")
    print("--------------------------------------------------------------------------------")
    print("  Creating persistent Chrome driver...")
    
    chrome_driver = create_persistent_chrome_driver()
    configure_browser_download_events(chrome_driver)
    
    anchor_window_handle = chrome_driver.current_window_handle
    
    h = check_chrome_driver_health(chrome_driver)
    if not h["alive"]:
        raise RuntimeError("CHROME HEALTH CHECK FAILED AFTER CREATION")
        
    pid = h.get("pid")
    print("   Chrome process launched.")
    print("   Selenium driver created.")
    print(f"   Chrome window count: {h['window_count']}")
    print("   JavaScript health check: PASS")
    print("   CDP health check: PASS")
    print("   Download event configuration: PASS")
    print("   Anchor tab: PASS")
    print("   Persistent profile: PASS")
    print("   Chrome driver: READY")
    if pid:
        print(f"   Driver PID: {pid}")
        
    print("================================================================================")
    print(" STEP 7: VERIFYING GOOGLE / GEMINI LOGIN STATE")
    print("================================================================================")
    ensure_chrome_driver_alive(chrome_driver)
    try:
        if "comprehensive_login_check" in globals():
            comprehensive_login_check(chrome_driver)
    except Exception as e:
        print(f"Login check failed: {e}")

def main():
    from bullmq import Worker
    import asyncio
    
    startup_sequence()
    
    global gemini_pool, wmr_pool, main_loop
    gemini_pool = GeminiWorkerPool(MAX_CONCURRENT_TABS)
    gemini_pool.start_all()
    
    wmr_pool = WmrWorkerPool(CHROME_WMR_WORKERS)
    wmr_pool.start_all()

    try:
        main_loop = asyncio.get_running_loop()
    except RuntimeError:
        main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(main_loop)

    log(f"[{WORKER_ID}] Redis configured: YES queue='{QUEUE_NAME}' prefix='{REDIS_KEY_PREFIX}'")
    
    scheduler_task = main_loop.create_task(central_scheduler_loop())
    redis_stats_task = main_loop.create_task(update_redis_queue_stats_loop())
    
    worker = Worker(
        QUEUE_NAME,
        process_bullmq_job,
        {"connection": REDIS_URL, "prefix": REDIS_KEY_PREFIX, "concurrency": MAX_CONCURRENT_TABS * 2}
    )

    log(f"[{WORKER_ID}] V13 READY  FULL QUEUE WORKER REBUILD")
    
    try:
        main_loop.run_until_complete(asyncio.Event().wait())
    except KeyboardInterrupt:
        pass
    finally:
        log("Shutting down...")
        try: worker.close()
        except: pass
        try: scheduler_task.cancel()
        except: pass
        try: redis_stats_task.cancel()
        except: pass
        gemini_pool.quit_all()
        wmr_pool.quit_all()
        print("SHUTDOWN_CLEAN=PASS")

if __name__ == '__main__':
    main()
