
def resolve_future_once(loop, future, *, result=None, exception=None):
    def resolve():
        if future.done(): return
        if exception: future.set_exception(exception)
        else: future.set_result(result)
    loop.call_soon_threadsafe(resolve)

class WmrWorker:
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.staging_dir = get_wmr_staging_dir(worker_id)
        self.driver = None
        self.driver_lock = threading.Lock()
        self.state = "IDLE"
        self.current_job_id = None

    def start(self):
        import threading
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"WmrWorker-W{self.worker_id}"
        )
        self._thread.start()
        log(f"[WMR-W{self.worker_id}] Worker slot registered (LAZY)")

    def _ensure_driver(self):
        with self.driver_lock:
            if self.driver is None:
                log(f"[WMR-W{self.worker_id}] Launching Chrome for WMR...")
                self.driver = create_wmr_chrome_driver(self.worker_id)
            return self.driver

    def _run_loop(self):
        import sys
        while True:
            item = WMR_GLOBAL_Q.get()
            if item is None: break
            
            job_id, tid, raw_path, future, loop = item
            self.state = "PROCESSING"
            self.current_job_id = job_id
            prefix = f"[WMR-W{self.worker_id}][{job_id}]"

            try:
                clean_png, webp_path = self._process_job(job_id, tid, raw_path, prefix)
                resolve_future_once(loop, future, result=(clean_png, webp_path))
            except Exception as e:
                log(f"{prefix} FAILED: {e}", file=sys.stderr)
                resolve_future_once(loop, future, exception=e)
            finally:
                self.state = "IDLE"
                self.current_job_id = None
                WMR_GLOBAL_Q.task_done()

    def _process_job(self, job_id, tid, raw_path, prefix):
        drv = self._ensure_driver()
        raw_path = Path(raw_path)
        if not raw_path.exists():
            raise Exception(f"RAW_MISSING: {raw_path}")
            
        final_dir = get_final_output_dir(tid, job_id)
        clean_png = final_dir / f"{job_id}_clean.png"
        clean_webp = final_dir / f"{job_id}_clean.webp"
        
        drv.get("https://logo-remover-fawn.vercel.app/gemini")
        time.sleep(1)
        
        up_js = "var el = document.querySelector('input[type=file]'); if (el) { el.style.display = 'block'; return true; } return false;"
        if safe_execute_script(drv, up_js):
            drv.find_element(By.CSS_SELECTOR, "input[type=file]").send_keys(str(raw_path))
        else:
            raise Exception("UPLOAD_FAILED")
            
        time.sleep(2)
        ready = False
        for _ in range(WMR_TIMEOUT_S * 2):
            js = '''
            var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
            if (!res) return false;
            var btns = res.querySelectorAll('button, a');
            for (var i=0; i<btns.length; i++) {
                var t = (btns[i].textContent || '').toLowerCase().trim();
                if (t === 'download png') { return true; }
            }
            return false;
            '''
            if safe_execute_script(drv, js):
                ready = True
                break
            time.sleep(0.5)
            
        if not ready: raise Exception("WMR_TIMEOUT")
            
        log(f"{prefix} DOWNLOAD_BUTTON_DETECTED")
        dl_dir = self.staging_dir / f"{job_id}_dl"
        dl_dir.mkdir(parents=True, exist_ok=True)
        set_tab_download_dir(drv, str(dl_dir))
        
        files_before = set(dl_dir.iterdir())
        
        js = '''
        var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
        var btns = res.querySelectorAll('button, a');
        for (var i=0; i<btns.length; i++) {
            var t = (btns[i].textContent || '').toLowerCase().trim();
            if (t === 'download png') { btns[i].click(); return true; }
        }
        return false;
        '''
        if not safe_execute_script(drv, js):
            raise Exception("CLICK_FAILED")
            
        import shutil
        t0 = time.time()
        final_file = None
        while time.time() - t0 < 60:
            for f in set(dl_dir.iterdir()) - files_before:
                if f.name.endswith('.crdownload') or f.name.endswith('.tmp'):
                    continue
                if f.name.endswith('.png'):
                    s = f.stat().st_size
                    time.sleep(0.3)
                    if s == f.stat().st_size:
                        final_file = f
                        break
            if final_file: break
            time.sleep(0.5)
            
        if not final_file: raise Exception("FILE_MISSING")
            
        shutil.move(str(final_file), str(clean_png))
        shutil.rmtree(dl_dir, ignore_errors=True)
        
        webp_res = convert_to_webp(str(clean_png))
        if webp_res and os.path.exists(webp_res):
            shutil.copy2(webp_res, str(clean_webp))
            os.remove(webp_res)
            return str(clean_png), str(clean_webp)
            
        return str(clean_png), None


class WmrWorkerPool:
    def __init__(self, n: int = CHROME_WMR_WORKERS):
        self._max = n
        self._workers = [WmrWorker(i) for i in range(n)]

    def start_all(self):
        for w in self._workers: w.start()

    def submit_job(self, job_id: str, chrome_tab_id: int, raw_png_path: str, future, loop):
        WMR_GLOBAL_Q.put((job_id, chrome_tab_id, raw_png_path, future, loop))
        log(f"[WMR_GLOBAL] Enqueued job {job_id} (Q_depth={WMR_GLOBAL_Q.qsize()})")
        
    def status(self):
        return [(w.worker_id, w.state, w.current_job_id) for w in self._workers]

    def quit_all(self):
        for _ in range(self._max): WMR_GLOBAL_Q.put(None)


class GeminiWorker:
    def __init__(self, tid: int):
        self.tid = tid
        self.state = "IDLE"
        self.current_job_id = None
        self.start_time = 0
        self.driver = None
        self.current_window_handle = None
        import queue
        self.job_queue = queue.Queue(maxsize=1)

    def start(self):
        import threading
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"GeminiWorker-T{self.tid}"
        )
        self._thread.start()
        log(f"[T{self.tid}] Gemini worker slot registered (LAZY)")

    def _run_loop(self):
        import time, sys
        while True:
            item = self.job_queue.get()
            if item is None: break
            
            self.current_job_id = item["job_id"]
            self.state = "SUBMITTING"
            self.start_time = time.time()
            
            try:
                self._process_job(item)
            except Exception as e:
                log(f"[T{self.tid}][{self.current_job_id}] GEMINI_FAILED: {e}")
                _fail_job(self.current_job_id, item.get("gen"), f"Gemini failed: {e}", item.get("future"), 1)
            finally:
                if self.driver and self.current_window_handle:
                    try:
                        self.driver.switch_to.window(self.current_window_handle)
                        self.driver.close()
                    except Exception as ex:
                        log(f"[T{self.tid}] Failed to close tab: {ex}", file=sys.stderr)
                        try: self.driver.quit()
                        except: pass
                        self.driver = None
                        
                if self.driver:
                    try:
                        if len(self.driver.window_handles) == 0:
                            self.driver.quit()
                            self.driver = None
                    except:
                        try: self.driver.quit()
                        except: pass
                        self.driver = None

                self.state = "IDLE"
                self.current_job_id = None
                self.start_time = 0
                self.current_window_handle = None
                self.job_queue.task_done()

    def _process_job(self, item):
        job_id = item["job_id"]
        prompt = item["prompt"]
        refs = item["refs"]
        loop = item.get("loop") or asyncio.new_event_loop()
        future = item["future"]
        prefix = f"[T{self.tid}][{job_id}]"
        
        drv = self._ensure_driver()
        
        # 1. Fresh tab
        drv.switch_to.new_window('tab')
        drv.get("https://gemini.google.com/app")
        log(f"{prefix} FRESH_BROWSER_READY")
        log(f"{prefix} BASE_URL_READY")
        log(f"{prefix} NEW_CHAT_SKIPPED_FRESH_BROWSER")
        
        # Setup isolated download directory for this job
        chrome_job_dir, incoming_dir = get_chrome_job_dir(self.tid, job_id)
        set_tab_download_dir(drv, str(incoming_dir))
        
        # 2. Wait for composer
        _wait_for_composer(drv)
        log(f"{prefix} CLEAN_COMPOSER_VERIFIED")
        
        # 3. Flash mode
        ensure_flash_mode(drv, self.tid, job_id)
        
        # 4. Create Image mode
        ensure_create_image_mode(drv, self.tid, job_id)
        
        # 5. Upload files
        expected_refs = [p for p in refs if p]
        ref_paths = [str(Path(p).resolve()) for p in expected_refs]
        
        if ref_paths:
            perform_robust_upload(drv, ref_paths, self.tid, job_id)
            verified, actual = verify_attachment_count(drv, len(ref_paths), self.tid, job_id)
            if not verified:
                raise Exception(f"ATTACHMENT_MISMATCH: expected {len(ref_paths)}, got {actual}")
                
        # 6. Prompt
        _inject_prompt_atomic(drv, prompt, self.tid, job_id)
        
        urls_before = snapshot_urls(drv)
        chat_urls = set()
        
        # 7. Send
        log(f"{prefix} SEND_REQUESTED")
        if not _click_send_button(drv, self.tid, job_id):
            raise Exception("SEND_FAILED: Could not click send button")
        log(f"{prefix} SEND_CLICKED")
        
        # 8. Verify generation started
        log(f"{prefix} GENERATION_SIGNAL_SEARCH")
        if not verify_generation_started(drv):
            raise Exception("GEN_START_FAILED: No generation signal after Send")
            
        self.state = "GENERATING"
        log(f"{prefix} GENERATING ✅")
        
        # 9. Wait for image detection (Inline polling instead of global scheduler)
        t0 = time.time()
        image_detected = False
        hover_ok = False
        cdp_ok = False
        
        while time.time() - t0 < GENERATION_TIMEOUT_S:
            status, new_src = nb_check_image(drv, urls_before, chat_urls)
            if status == 'SUCCESS':
                image_detected = True
                if new_src:
                    urls_before.add(new_src)
                break
            time.sleep(1.0)
            
        if not image_detected:
            raise Exception("GENERATION_TIMEOUT")
            
        log(f"{prefix} IMAGE_DETECTED")
        
        # 10. Click Download
        hover_ok = _hover_and_dl_single_click(drv, urls_before, chat_urls)
        log(f"{prefix} DOWNLOAD_CLICKED (hover_ok={hover_ok})")
        
        raw_path = chrome_job_dir / f"{job_id}_raw.png"
        download_state = "DOWNLOAD_WAITING"
        
        if not hover_ok:
            cdp_ok = _direct_fetch_cdp(drv, str(raw_path), urls_before)
            if cdp_ok:
                log(f"{prefix} CDP_FALLBACK_CAPTURE ({raw_path.stat().st_size // 1024} KB)")
                download_state = "CHROME_RAW_READY"

        self.state = "DOWNLOAD_WAITING"
        
        # 11. Wait for .crdownload
        dl_confirmed = False
        
        if not cdp_ok:
            t1 = time.time()
            while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                if incoming_dir.exists():
                    cur = set(os.listdir(incoming_dir))
                    new_files = cur - files_before
                    if any(fn.endswith('.crdownload') or fn.lower().endswith(('.png','.jpg','.jpeg','.webp')) for fn in new_files):
                        dl_confirmed = True
                        break
                time.sleep(0.3)
                
            if not dl_confirmed:
                raise Exception("DOWNLOAD_START_FAILED")
                
            log(f"{prefix} DOWNLOAD_START_CONFIRMED")
        
        dinfo = {
            "gen": item.get("gen") or {"id": job_id},
            "tid": self.tid,
            "incoming_dir": incoming_dir,
            "chrome_job_dir": chrome_job_dir,
            "files_before": files_before,
            "started_at": time.time(),
            "state": download_state,
            "future": future,
            "attempt": 1,
            "loop": loop
        }
        
        # Register for background filesystem polling
        active_downloads[job_id] = dinfo
        
        if cdp_ok:
            _enqueue_wmr(job_id, dinfo)
        
        # 12. Close Tab & Release Worker
        try:
            
        except Exception:
            pass
            
        # Ensure we switch back to dummy tab so driver doesn't hang
        try:
            drv.switch_to.window(drv.window_handles[0])
        except Exception:
            pass
            
        log(f"{prefix} PHYSICAL_TAB_CLOSED")
        log(f"{prefix} T WORKER RELEASED")

class GeminiWorkerPool:
    def __init__(self, max_workers: int = MAX_CONCURRENT_TABS):
        self.workers = [GeminiWorker(i) for i in range(max_workers)]

    def start_all(self):
        for w in self.workers:
            w.start()

    def status(self):
        return [(w.tid, w.state, w.current_job_id, w.start_time) for w in self.workers]

redis_queue_stats = {
    "wait": 0, "active": 0, "delayed": 0, "prioritized": 0, "waiting-children": 0,
}

async def update_redis_queue_stats_loop():
    from bullmq import Queue
    q = Queue(QUEUE_NAME, {"connection": REDIS_URL, "prefix": REDIS_KEY_PREFIX})
    try:
        while True:
            try:
                counts = await q.getJobCounts()
                redis_queue_stats.update({k: counts.get(k, 0) for k in redis_queue_stats.keys()})
            except asyncio.CancelledError:
                raise
            except Exception as e:
                import sys
                log(f"Redis stats update failed: {e}", file=sys.stderr)
            await asyncio.sleep(2.5)
    finally:
        try:
            await q.close()
        except Exception:
            pass

def _enqueue_wmr(job_id: str, dinfo: dict):
    loop = main_loop
    future = loop.create_future()
    dinfo["wmr_future"] = future
    active_wmr[job_id] = dinfo
    wmr_pool.submit_job(
        job_id,
        dinfo["tid"],
        str(dinfo["raw_path"]),
        future,
        loop
    )
    log(f"[{job_id}] WMR_QUEUE -> WMR_GLOBAL_Q")

async def poll_active_downloads():
    now = time.time()
    for job_id, dinfo in list(active_downloads.items()):
        if dinfo.get("state") != "DOWNLOAD_WAITING":
            continue
            
        incoming_dir = Path(dinfo.get("incoming_dir", ""))
        if not incoming_dir.exists():
            continue
            
        raw_ready = False
        valid_file = None
        
        for f in incoming_dir.iterdir():
            if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                size = f.stat().st_size
                if size > 1024:
                    time.sleep(0.5)
                    if size == f.stat().st_size:
                        try:
                            from PIL import Image
                            with Image.open(f) as img:
                                img.verify()
                            valid_file = f
                            raw_ready = True
                            break
                        except Exception:
                            pass
                            
        if raw_ready and valid_file:
            raw_path = Path(dinfo["chrome_job_dir"]) / f"{job_id}_raw.png"
            import shutil
            shutil.move(str(valid_file), str(raw_path))
            dinfo["raw_path"] = raw_path
            dinfo["state"] = "CHROME_RAW_READY"
            _enqueue_wmr(job_id, dinfo)
            continue
            
        if now - dinfo.get("started_at", now) > 60:
            log(f"[{job_id}] DOWNLOAD_TIMEOUT")
            _fail_job(job_id, dinfo.get("gen"), "Download timed out", dinfo.get("future"), 1)
            active_downloads.pop(job_id, None)

async def _finalize_and_clean_job(job_id, dinfo, clean_png, webp_path):
    gen = dinfo.get("gen", {})
    future = dinfo.get("future")
    try:
        log(f"[{job_id}] R2 Uploading...")
        import os
        from backend.r2 import upload_to_r2, ensure_webp
        
        if not webp_path or not os.path.exists(webp_path):
            webp_path = ensure_webp(str(clean_png))
            
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
            from backend.credits import credit_settle
            credit_settle(gen.get("user_id"), 1)
        except Exception as ce:
            log(f"[{job_id}] Credit settle failed: {ce}", file=sys.stderr)
        
        if future and not future.done():
            future.set_result(True)
            
        counters["completed"] += 1
        log(f"[{job_id}] COMPLETION SUCCESSFUL")
        
    except Exception as e:
        log(f"[{job_id}] FINALIZE FAILED: {e}")
        _fail_job(job_id, gen, str(e), future, 1)
    finally:
        active_downloads.pop(job_id, None)

async def poll_wmr_workers():
    for job_id, dinfo in list(active_wmr.items()):
        future = dinfo.get("wmr_future")
        if future is None or not future.done():
            continue
            
        active_wmr.pop(job_id, None)
        
        if future.exception():
            log(f"[{job_id}] WMR_FAILED: {future.exception()}")
            _fail_job(job_id, dinfo.get("gen"), str(future.exception()), dinfo.get("future"), 1)
        else:
            clean_png, webp_path = future.result()
            log(f"[{job_id}] WMR_OUTPUT_READY")
            import asyncio
            asyncio.create_task(_finalize_and_clean_job(job_id, dinfo, clean_png, webp_path))

last_status_print = 0
def print_pipeline_status():
    import time
    global last_status_print
    now = time.time()
    if now - last_status_print < 2.5: return
    last_status_print = now

    dl_waiting = sum(1 for d in active_downloads.values() if d.get("state") == "DOWNLOAD_WAITING")
    dl_raw = sum(1 for d in active_downloads.values() if d.get("state") == "CHROME_RAW_READY")
    wmr_status = wmr_pool.status()

    print("\n====================================================================")
    print(f"PIPELINE STATUS {time.strftime('%H:%M:%S')}")
    print("====================================================================")
    print("\nREDIS QUEUE")
    print(f"  WAIT={redis_queue_stats['wait']} | ACTIVE={redis_queue_stats['active']} | DELAYED={redis_queue_stats['delayed']} | PRIORITY={redis_queue_stats['prioritized']} | WAIT_CHILD={redis_queue_stats['waiting-children']}")
    print("\nGEMINI ADMISSION")
    print(f"  WAIT={GEMINI_ADMISSION_Q.qsize()}")
    print("\nGEMINI T-SLOTS")
    for tid, state, cur_jid, start_time in gemini_pool.status():
        jid = (cur_jid or "---")[:12]
        elapsed = f"{int(now - start_time)}s" if start_time > 0 else "0s"
        print(f"  T{tid} = {state:<13} {elapsed:>3}  {jid}")
    print("\nDOWNLOADS")
    print(f"  START_WAIT={dl_waiting}  RAW_READY={dl_raw}")
    print("\nWMR CHROME WORKERS")
    print(f"  QUEUE={WMR_GLOBAL_Q.qsize()}")
    for wid, state, cur_jid in wmr_status:
        print(f"  W{wid} = {state:<13}  Job={(cur_jid or '---')[:12]}")
    print("\nRESULT")
    print(f"  DONE={counters['completed']} | FAIL={counters['failed']}")
    print("====================================================================\n")

async def central_scheduler_loop():
    while True:
        try:
            for w in gemini_pool.workers:
                if w.state == "IDLE" and w.job_queue.empty():
                    try:
                        job = GEMINI_ADMISSION_Q.get_nowait()
                        w.job_queue.put(job)
                    except asyncio.QueueEmpty:
                        break

            await poll_active_downloads()
            await poll_wmr_workers()
            print_pipeline_status()
        except Exception as e:
            import sys
            log(f"Scheduler loop error: {e}", file=sys.stderr)
        await asyncio.sleep(0.1)

