with open('v16_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

new_process_job = '''
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
        files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()
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
            drv.close()
        except Exception:
            pass
            
        # Ensure we switch back to dummy tab so driver doesn't hang
        try:
            drv.switch_to.window(drv.window_handles[0])
        except Exception:
            pass
            
        log(f"{prefix} PHYSICAL_TAB_CLOSED")
        log(f"{prefix} T WORKER RELEASED")
'''

text = re.sub(r'    def _process_job\(self, item\):.*?log\(f"\{prefix\} T WORKER RELEASED"\)\n', new_process_job, text, flags=re.DOTALL)

with open('v16_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patched _process_job with exact V9.1 download functions")
