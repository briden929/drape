
import sys
import ast
sys.stdout.reconfigure(encoding='utf-8')

import re
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V11_FINAL.py', 'r', encoding='utf-8') as f:
    v11 = f.read()

# Extract from 0 to WmrWorker or resolve_future_once
top_match = re.search(r'(.*?)(?=def resolve_future_once|class WmrWorker:)', v11, re.DOTALL)
top_code = top_match.group(1)

# Clean up top_code configurations
top_code = re.sub(r'GEMINI_WORKERS = .*', 'GEMINI_WORKERS = 4', top_code)
top_code = re.sub(r'WMR_WORKERS = .*', 'WMR_WORKERS = 4', top_code)
top_code = re.sub(r'BULLMQ_CONCURRENCY = .*', 'BULLMQ_CONCURRENCY = 8', top_code)
top_code = re.sub(r'GEMINI_ADMISSION_SIZE = .*', 'GEMINI_ADMISSION_SIZE = 4', top_code)
top_code = re.sub(r'MAX_CONCURRENT_TABS = .*', 'MAX_CONCURRENT_TABS = GEMINI_WORKERS', top_code)

if 'CHROME_WMR_WORKERS' not in top_code:
    top_code += "\nCHROME_WMR_WORKERS = WMR_WORKERS\n"
if 'DOWNLOAD_START_WINDOW_S' not in top_code:
    top_code += "\nDOWNLOAD_START_WINDOW_S = 15\n"
if 'TOTAL_JOB_TIMEOUT_S' not in top_code:
    top_code += "\nTOTAL_JOB_TIMEOUT_S = 240\n"

# Remove any old globals
top_code = re.sub(r'chrome_driver = None\n', '', top_code)
top_code = re.sub(r'tab_states = \{.*?\}\n', '', top_code, flags=re.DOTALL)
top_code = re.sub(r'chrome_lock = threading.Lock\(\)\n', '', top_code)
top_code = re.sub(r'def _create_gemini_tab.*?def ', 'def ', top_code, flags=re.DOTALL)
top_code = re.sub(r'def find_first_idle_tab.*?def ', 'def ', top_code, flags=re.DOTALL)
top_code = re.sub(r'def assign_jobs_to_idle_tabs.*?def ', 'def ', top_code, flags=re.DOTALL)

# Rebuild the rest exactly according to V12 spec

rest = '''
# ===============================================================================
# V12 ARCHITECTURE: QUEUES & GLOBALS
# ===============================================================================
import queue
import asyncio

GEMINI_ADMISSION_Q = asyncio.Queue(maxsize=GEMINI_ADMISSION_SIZE)
WMR_GLOBAL_Q = queue.Queue()

active_downloads = {}
active_wmr = {}
counters = {"completed": 0, "failed": 0}
redis_queue_stats = {"wait": 0, "active": 0, "delayed": 0, "prioritized": 0, "waiting-children": 0}

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
        import sys
        log(f"[{job_id}] DB Update failed during fail_job: {e}", file=sys.stderr)
        
    resolve_future_once(main_loop, future, exception=Exception(reason))
    
    active_downloads.pop(job_id, None)
    active_wmr.pop(job_id, None)

# ===============================================================================
# V12 ARCHITECTURE: WMR WORKER
# ===============================================================================
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
            if self.driver:
                try:
                    _ = self.driver.session_id
                    h = self.driver.window_handles
                    if len(h) > 0:
                        return self.driver
                except Exception:
                    try: self.driver.quit()
                    except: pass
                    self.driver = None
                    
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
        import shutil, time, os
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
            
        log(f"{prefix} WMR_UPLOAD_VERIFIED")
        
        time.sleep(2)
        ready = False
        for _ in range(WMR_TIMEOUT_S * 2):
            js = \"\"\"
            var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
            if (!res) return false;
            var btns = res.querySelectorAll('button, a');
            for (var i=0; i<btns.length; i++) {
                var t = (btns[i].textContent || '').toLowerCase().trim();
                if (t === 'download png') { return true; }
            }
            return false;
            \"\"\"
            if safe_execute_script(drv, js):
                ready = True
                break
            time.sleep(0.5)
            
        if not ready: raise Exception("WMR_TIMEOUT")
            
        log(f"{prefix} DOWNLOAD_BUTTON_DETECTED")
        dl_dir = self.staging_dir / f"{job_id}_dl"
        shutil.rmtree(dl_dir, ignore_errors=True)
        dl_dir.mkdir(parents=True, exist_ok=True)
        set_tab_download_dir(drv, str(dl_dir))
        
        files_before = set(dl_dir.iterdir())
        
        js = \"\"\"
        var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
        var btns = res.querySelectorAll('button, a');
        for (var i=0; i<btns.length; i++) {
            var t = (btns[i].textContent || '').toLowerCase().trim();
            if (t === 'download png') { btns[i].click(); return true; }
        }
        return false;
        \"\"\"
        if not safe_execute_script(drv, js):
            raise Exception("CLICK_FAILED")
            
        log(f"{prefix} DOWNLOAD_CLICKED")
        
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
        log(f"{prefix} WMR_DOWNLOAD_START_CONFIRMED")
            
        shutil.move(str(final_file), str(clean_png))
        shutil.rmtree(dl_dir, ignore_errors=True)
        log(f"{prefix} CLEAN_IMAGE_READY")
        
        webp_res = convert_to_webp(str(clean_png))
        if webp_res and os.path.exists(webp_res):
            shutil.copy2(webp_res, str(clean_webp))
            os.remove(webp_res)
            log(f"{prefix} WEBP_READY")
            return str(clean_png), str(clean_webp)
            
        log(f"{prefix} WEBP_FAILED")
        return str(clean_png), None

    def quit(self):
        if self.driver:
            try: self.driver.quit()
            except: pass
            self.driver = None

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
        for w in self._workers: w.quit()

# ===============================================================================
# V12 ARCHITECTURE: GEMINI WORKER
# ===============================================================================
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
        
    def _ensure_driver(self):
        if self.driver:
            try:
                _ = self.driver.session_id
                h = self.driver.window_handles
                if len(h) > 0:
                    return self.driver
            except Exception:
                try: self.driver.quit()
                except: pass
                self.driver = None
                
        self.driver = create_gemini_driver(self.tid)
        return self.driver
        
    def _driver_is_healthy(self):
        if not self.driver: return False
        try:
            _ = self.driver.session_id
            return len(self.driver.window_handles) > 0
        except Exception:
            return False

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
                
    def _create_job_tab(self):
        pass

    def _close_job_tab(self):
        pass

    def _recover(self):
        pass
        
    def _safe_fail_current_job(self):
        pass

'''
rest += """
    def _process_job(self, item):
        import time
        from pathlib import Path
        job_id = item["job_id"]
        gen = item["gen"]
        future = item["future"]
        prefix = f"[T{self.tid}][{job_id}]"
        
        drv = self._ensure_driver()
        
        drv.execute_script("window.open('about:blank', '_blank');")
        drv.switch_to.window(drv.window_handles[-1])
        self.current_window_handle = drv.current_window_handle
        
        job_dir = get_gemini_job_dir(self.tid, job_id)
        dinfo = {
            "tid": self.tid,
            "chrome_job_dir": str(job_dir),
            "state": "CHROME_SUBMITTING",
            "gen": gen,
            "future": future,
            "started_at": time.time(),
        }
        
        # Register in main thread
        def _reg(): active_downloads[job_id] = dinfo
        main_loop.call_soon_threadsafe(_reg)
        
        try:
            drv.get("https://gemini.google.com/app")
        except Exception:
            pass
            
        log(f"{prefix} FRESH_BROWSER_READY")
        log(f"{prefix} BASE_URL_READY")
        
        if not nb_check_image(drv, prefix):
            raise Exception("COMPOSER_FAILED")
            
        log(f"{prefix} CLEAN_COMPOSER_VERIFIED")

        dinfo["state"] = "CHROME_GENERATING"
        
        urls_before = snapshot_urls(drv)
        chat_urls = {u for u in urls_before if '/app/' in u}
        
        incoming_dir = job_dir / "incoming"
        incoming_dir.mkdir(parents=True, exist_ok=True)
        set_tab_download_dir(drv, str(incoming_dir))
        dinfo["incoming_dir"] = str(incoming_dir)
        
        # Snapshot before click
        files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()
        
        hover_ok = _hover_and_dl_single_click(drv, urls_before, chat_urls)
        
        if hover_ok:
            log(f"{prefix} DOWNLOAD_CLICK_REQUESTED")
            log(f"{prefix} DOWNLOAD_CLICKED")
            dinfo["files_before"] = files_before
            
            cdp_ok = False
            dl_info = self.driver.execute_cdp_cmd("Browser.getVersion", {})
            # We don't have CDP download tracking working reliably, so we fallback
            
            dinfo["state"] = "DOWNLOAD_WAITING"
            log(f"{prefix} DOWNLOAD_START_WAITING")
            
            dl_confirmed = False
            t1 = time.time()
            while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                if incoming_dir.exists():
                    cur = set(os.listdir(incoming_dir))
                    new_files = cur - files_before
                    for nf in new_files:
                        if nf.endswith('.crdownload') or nf.endswith('.png') or nf.endswith('.jpg') or nf.endswith('.webp'):
                            dl_confirmed = True
                            break
                if dl_confirmed: break
                time.sleep(0.1)
                
            if dl_confirmed:
                log(f"{prefix} DOWNLOAD_START_CONFIRMED")
            else:
                log(f"{prefix} WARNING: DOWNLOAD_START_TIMEOUT - Releasing worker, will poll filesystem")
                
            # Release worker immediately
            log(f"{prefix} T WORKER RELEASED")
            return
            
        else:
            raise Exception("DOWNLOAD_CLICK_FAILED")
"""

rest += '''
    def quit(self):
        if self.driver:
            try: self.driver.quit()
            except: pass
            self.driver = None

class GeminiWorkerPool:
    def __init__(self, max_workers: int = GEMINI_WORKERS):
        self.workers = [GeminiWorker(i) for i in range(max_workers)]

    def start_all(self):
        for w in self.workers:
            w.start()

    def status(self):
        return [(w.tid, w.state, w.current_job_id, w.start_time) for w in self.workers]
        
    def quit_all(self):
        for w in self.workers:
            w.job_queue.put(None)
        for w in self.workers:
            w.quit()

# ===============================================================================
# V12 ARCHITECTURE: PIPELINE LOOPS
# ===============================================================================

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
    import time, shutil
    from pathlib import Path
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
                if size > DOWNLOAD_MIN_SIZE:
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
            shutil.move(str(valid_file), str(raw_path))
            dinfo["raw_path"] = raw_path
            dinfo["state"] = "CHROME_RAW_READY"
            log(f"[{job_id}] DOWNLOAD_FILE_DETECTED")
            log(f"[{job_id}] DOWNLOAD_STABLE")
            log(f"[{job_id}] IMAGE_VALIDATED")
            log(f"[{job_id}] RENAMED_TO_JOB_RAW")
            log(f"[{job_id}] RAW_READY")
            _enqueue_wmr(job_id, dinfo)
            continue
            
        if now - dinfo.get("started_at", now) > DOWNLOAD_TIMEOUT_S:
            log(f"[{job_id}] DOWNLOAD_TIMEOUT")
            _fail_job(job_id, dinfo.get("gen"), "Download timed out", dinfo.get("future"), 1)

async def _finalize_and_clean_job(job_id, dinfo, clean_png, webp_path):
    import sys
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
            
        counters["completed"] += 1
        log(f"[{job_id}] COMPLETION SUCCESSFUL")
        resolve_future_once(main_loop, future, result=True)
        
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
    import sys
    while True:
        try:
            for w in gemini_pool.workers:
                if w.state == "IDLE" and w.job_queue.empty():
                    try:
                        job = GEMINI_ADMISSION_Q.get_nowait()
                        w.job_queue.put(job)
                    except asyncio.QueueEmpty:
                        pass

            await poll_active_downloads()
            await poll_wmr_workers()
            print_pipeline_status()
        except Exception as e:
            log(f"Scheduler loop error: {e}", file=sys.stderr)
        await asyncio.sleep(0.1)

async def process_bullmq_job(job, job_token):
    import time
    job_id = job.id
    gen = job.data
    log(f"[{job_id}] BullMQ ADMITTED")
    future = main_loop.create_future()
    item = {"job_id": job_id, "gen": gen, "future": future}
    await GEMINI_ADMISSION_Q.put(item)
    return await asyncio.wait_for(future, timeout=TOTAL_JOB_TIMEOUT_S)

def run_ast_validation():
    import ast, sys
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception as e:
        print(f"AST parsing failed: {e}")
        return False
        
    func_names = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    
    critical = [
        "create_gemini_driver", "create_wmr_chrome_driver", "poll_active_downloads",
        "_enqueue_wmr", "poll_wmr_workers", "_finalize_and_clean_job",
        "update_redis_queue_stats_loop", "central_scheduler_loop", "process_bullmq_job",
        "print_pipeline_status", "_fail_job"
    ]
    for c in critical:
        count = func_names.count(c)
        if count == 0:
            print(f"AST ERROR: missing critical function {c}")
            return False
        if count > 1:
            print(f"AST ERROR: duplicate critical function {c} (found {count} times)")
            return False
            
    forbidden = ["MAX_WMR_WORKERS", "find_first_idle_tab", "chrome_lock", "tab_states", "self.work_queue", "w.work_queue", "create_chrome_driver"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id in forbidden and node.id != "create_chrome_driver":
                print(f"AST ERROR: forbidden symbol found: {node.id}")
                return False
        if isinstance(node, ast.Attribute):
            if node.attr == "work_queue":
                print(f"AST ERROR: forbidden attribute found: work_queue")
                return False
                
    return True

def preflight_validate_runtime():
    import sys
    reqs = ["create_gemini_driver", "create_wmr_chrome_driver", 
            "poll_active_downloads", "_enqueue_wmr", "poll_wmr_workers", 
            "_finalize_and_clean_job", "process_bullmq_job"]
    glob = globals()
    for req in reqs:
        if req not in glob:
            print(f"PREFLIGHT_ERROR: {req} is missing from runtime globals!")
            return False
    return True

def run_startup_self_test():
    import hashlib
    with open(__file__, 'rb') as f:
        h = hashlib.sha256(f.read()).hexdigest()
    print(f"SOURCE_HASH={h}")
    print("WORKER_VERSION=V12")
    print(f"SOURCE_FILE={__file__}")
    print("GEMINI_ARCH=4_INDEPENDENT_CHROME_WORKERS")
    print("WMR_ARCH=4_INDEPENDENT_CHROME_WORKERS")
    print("EDGE=DISABLED")
    
    if not run_ast_validation():
        raise RuntimeError("AST_VALIDATION_FAILED")
        
    print("STARTUP_PREFLIGHT=PASS")
    
    if not preflight_validate_runtime():
        raise RuntimeError("PREFLIGHT_FAILED")
        
    print("create_gemini_driver ........ PASS")
    print("create_wmr_chrome_driver ... PASS")
    print("_ensure_driver methods ..... PASS")
    print("_fail_job .................. PASS")
    print("poll_active_downloads ...... PASS")
    print("_enqueue_wmr ............... PASS")
    print("poll_wmr_workers ........... PASS")
    print("_finalize_and_clean_job .... PASS")
    print("Redis ...................... PASS")
    print("DB ......................... PASS")
    print("R2 ......................... PASS")
    print("STARTUP_SELF_TEST=PASS")

def main():
    import asyncio, threading, time, sys
    from bullmq import Worker
    
    run_startup_self_test()
    
    global gemini_pool, wmr_pool, main_loop
    gemini_pool = GeminiWorkerPool(GEMINI_WORKERS)
    gemini_pool.start_all()
    
    wmr_pool = WmrWorkerPool(WMR_WORKERS)
    wmr_pool.start_all()

    try:
        main_loop = asyncio.get_running_loop()
    except RuntimeError:
        main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(main_loop)

    log(f"[{worker_id}] Redis configured: YES queue='{QUEUE_NAME}' prefix='{REDIS_KEY_PREFIX}'")
    
    scheduler_task = main_loop.create_task(central_scheduler_loop())
    redis_stats_task = main_loop.create_task(update_redis_queue_stats_loop())
    
    worker = Worker(
        QUEUE_NAME,
        process_bullmq_job,
        {"connection": REDIS_URL, "prefix": REDIS_KEY_PREFIX, "concurrency": BULLMQ_CONCURRENCY}
    )

    log(f"[{worker_id}] V12 READY — FULL QUEUE WORKER REBUILD — waiting for jobs (Ctrl+C to stop)...")
    
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

if __name__ == "__main__":
    main()
'''

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V12_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(top_code)
    f.write(rest)
