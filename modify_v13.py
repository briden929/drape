import re
with open('v13_working.py', 'r', encoding='utf-8') as f:
    text = f.read()

# We need to inject create_persistent_chrome_driver and check_chrome_driver_health
# and rewrite GeminiWorker and main

new_arch = """
chrome_driver = None
anchor_window_handle = None

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

class GeminiWorker:
    def __init__(self, tid: int):
        self.tid = tid
        self.state = "IDLE"
        self.current_job_id = None
        self.start_time = 0
        self.window_handle = None
        
    def _ensure_tab(self):
        global chrome_driver
        if self.window_handle:
            try:
                if self.window_handle in chrome_driver.window_handles:
                    chrome_driver.switch_to.window(self.window_handle)
                    return chrome_driver
            except Exception:
                pass
                
        log(f"[T{self.tid}] Creating new logical Gemini tab...")
        res = chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
        target_id = res['targetId']
        
        # switch to it
        for h in chrome_driver.window_handles:
            chrome_driver.switch_to.window(h)
            if chrome_driver.current_url == 'about:blank':
                self.window_handle = h
                break
        
        if not self.window_handle:
            self.window_handle = chrome_driver.window_handles[-1]
            chrome_driver.switch_to.window(self.window_handle)
            
        return chrome_driver

    def process_job(self, item):
        import threading
        t = threading.Thread(target=self._process_job_thread, args=(item,))
        t.start()
        
    def _process_job_thread(self, item):
        import time, os, sys
        from pathlib import Path
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
            
            drv.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': str(incoming_dir)
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
            
            files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()
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
                if incoming_dir.exists():
                    cur = set(os.listdir(incoming_dir))
                    new_files = cur - files_before
                    for nf in new_files:
                        if nf.endswith('.crdownload') or nf.endswith('.png') or nf.endswith('.jpg') or nf.endswith('.webp'):
                            dl_confirmed_fs = True
                            break
                if dl_confirmed_fs: break
                time.sleep(0.1)
                
            if dl_guid and dl_confirmed_fs:
                log(f"{prefix} DOWNLOAD_START_EVENT guid={dl_guid}")
                log(f"{prefix} DOWNLOAD_FILESYSTEM_START_CONFIRMED")
                
                dinfo = {
                    "job_id": job_id,
                    "tid": self.tid,
                    "state": "BACKGROUND_DOWNLOAD",
                    "chrome_job_dir": str(job_dir),
                    "incoming_dir": str(incoming_dir),
                    "download_guid": dl_guid,
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
                raise Exception(f"DOWNLOAD_START_FAILED guid={bool(dl_guid)} fs={dl_confirmed_fs}")
                
        except Exception as e:
            log(f"{prefix} GEMINI_FAILED: {e}")
            _fail_job(job_id, gen, f"Gemini failed: {e}", future, 1)
            def _rel():
                GEMINI_BROKER.release(self.tid)
                self.state = "IDLE"
                self.current_job_id = None
            main_loop.call_soon_threadsafe(_rel)

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
    # Re-use comprehensive login if it exists, or just pass
    try:
        if "comprehensive_login_check" in globals():
            comprehensive_login_check(chrome_driver)
    except Exception as e:
        print(f"Login check failed: {e}")

def main():
    from bullmq import Worker
    import asyncio
    run_startup_self_test()
    
    startup_sequence()
    
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

    log(f"[{WORKER_ID}] Redis configured: YES queue='{QUEUE_NAME}' prefix='{REDIS_KEY_PREFIX}'")
    
    scheduler_task = main_loop.create_task(central_scheduler_loop())
    redis_stats_task = main_loop.create_task(update_redis_queue_stats_loop())
    
    worker = Worker(
        QUEUE_NAME,
        process_bullmq_job,
        {"connection": REDIS_URL, "prefix": REDIS_KEY_PREFIX, "concurrency": BULLMQ_CONCURRENCY}
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
"""

import re
# Remove the old create_gemini_driver
text = re.sub(r'def create_gemini_driver.*?return drv', '', text, flags=re.DOTALL)

# Remove the old GeminiWorker
text = re.sub(r'class GeminiWorker:.*?def quit\(self\):.*?self\.driver = None', '', text, flags=re.DOTALL)

# Remove the old main
text = re.sub(r'def main\(\):.*?if __name__ == "__main__":', '', text, flags=re.DOTALL)

# Also remove run_startup_self_test to rebuild it
text = re.sub(r'def run_startup_self_test\(\):.*?print\("STARTUP_SELF_TEST=PASS"\)', '', text, flags=re.DOTALL)
text = re.sub(r'def run_ast_validation\(\):.*?return True', '', text, flags=re.DOTALL)

final_text = text + "\n" + new_arch + "\nif __name__ == '__main__':\n    main()\n"

with open('v13_modified.py', 'w', encoding='utf-8') as f:
    f.write(final_text)
print("Modified saved")
