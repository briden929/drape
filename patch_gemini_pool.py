with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

gemini_worker_code = '''
class GeminiWorker:
    def __init__(self, tid: int):
        self.tid = tid
        self.state = S_IDLE
        self.current_job_id = None
        self.start_time = 0
        self.driver = None
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"GeminiWorker-T{tid}"
        )
        self._thread.start()
        log(f"[T{tid}] Gemini worker slot registered")

    def _ensure_driver(self):
        if not self.driver:
            self.driver = create_gemini_driver(self.tid)
            # Dummy tab to keep driver alive when job tabs are closed
            self.driver.get("data:,")
        return self.driver
        
    def _run_loop(self):
        while True:
            item = GEMINI_ADMISSION_Q.get()
            if item is None: break
            self.current_job_id = item["job_id"]
            self.state = S_SUBMITTING
            self.start_time = time.time()
            set_job_stage(self.current_job_id, "GEMINI_SUBMIT")
            
            try:
                self._process_job(item)
            except Exception as e:
                log(f"[T{self.tid}][{self.current_job_id}] GEMINI_FAILED: {e}")
                set_job_stage(self.current_job_id, "FAILED")
                _fail_job(self.current_job_id, None, f"Gemini failed: {e}", item.get("future"), 1)
            finally:
                self.state = S_IDLE
                self.current_job_id = None
                self.start_time = 0
                GEMINI_ADMISSION_Q.task_done()
                
    def _process_job(self, item):
        job_id = item["job_id"]
        prompt = item["prompt"]
        refs = item["refs"]
        loop = item["loop"]
        future = item["future"]
        prefix = f"[T{self.tid}][{job_id}]"
        
        drv = self._ensure_driver()
        
        # 1. Fresh tab
        drv.switch_to.new_window('tab')
        drv.get("https://gemini.google.com/app")
        log(f"{prefix} FRESH_TAB_READY")
        log(f"{prefix} NEW_CHAT_SKIPPED_FRESH_TAB")
        
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
        
        # 7. Send
        log(f"{prefix} SEND_REQUESTED")
        if not _click_send_button(drv, self.tid, job_id):
            raise Exception("SEND_FAILED: Could not click send button")
        log(f"{prefix} SEND_CLICKED")
        
        # 8. Verify generation started
        log(f"{prefix} GENERATION_SIGNAL_SEARCH")
        if not verify_generation_started(drv):
            raise Exception("GEN_START_FAILED: No generation signal after Send")
            
        self.state = S_GEN_WAITING
        set_job_stage(job_id, "GEMINI_GENERATING")
        log(f"{prefix} GENERATION_STARTED ✅")
        
        # 9. Wait for image detection (Inline polling instead of global scheduler)
        t0 = time.time()
        image_detected = False
        while time.time() - t0 < GENERATION_TIMEOUT_S:
            status = verify_generation_completed(drv)
            if status == "COMPLETED":
                image_detected = True
                break
            time.sleep(1.0)
            
        if not image_detected:
            raise Exception("GENERATION_TIMEOUT")
            
        log(f"{prefix} IMAGE_DETECTED")
        
        # 10. Click Download
        dl_clicked = _click_download_button(drv, self.tid, job_id)
        if not dl_clicked:
            raise Exception("DOWNLOAD_CLICK_FAILED")
            
        log(f"{prefix} DOWNLOAD_CLICKED")
        self.state = "DOWNLOAD_START_WAITING"
        set_job_stage(job_id, "GEMINI_DOWNLOAD_WAIT")
        
        # 11. Wait for .crdownload
        t1 = time.time()
        dl_confirmed = False
        files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()
        
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
        
        # Register for background filesystem polling
        active_downloads[job_id] = {
            "gen": {"id": job_id},
            "tid": self.tid,
            "incoming_dir": incoming_dir,
            "chrome_job_dir": chrome_job_dir,
            "files_before": files_before,
            "started_at": time.time(),
            "state": "DOWNLOAD_WAITING",
            "future": future,
            "attempt": 1,
            "loop": loop
        }
        
        # 12. Close Tab & Release Worker
        try:
            drv.close()
        except Exception:
            pass
            
        # Ensure we switch back to dummy tab so driver doesn't hang
        try:
            drv.switch_to.window(drv.window_handles[0])
        except Exception:
            pass
            
        log(f"{prefix} PHYSICAL_TAB_CLOSED")
        log(f"{prefix} GEMINI_WORKER_RELEASED")
        

class GeminiWorkerPool:
    def __init__(self, max_workers=MAX_CONCURRENT_TABS):
        self.workers = [GeminiWorker(i) for i in range(max_workers)]
        
    def status(self):
        return [(w.tid, w.state, w.current_job_id, w.start_time) for w in self.workers]
        
gemini_pool = GeminiWorkerPool()

'''

import re
text = re.sub(r'async def _submit_job_to_tab\(tid: int\):.*?async def poll_active_tabs\(\):.*?(?=def print_pipeline_status)', gemini_worker_code, text, flags=re.DOTALL)
text = re.sub(r'async def assign_jobs_to_idle_tabs\(\):.*?(?=async def _submit_job_to_tab)', '', text, flags=re.DOTALL) # In case assign_jobs_to_idle_tabs is still there

with open('v13_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Injected GeminiWorkerPool")
