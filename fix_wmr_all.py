with open('v18_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_idx = text.find('class WmrWorker:')
end_idx = text.find('active_downloads = {}', start_idx)

new_wmr_code = '''class WmrWorker:
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.staging_dir = get_wmr_staging_dir(worker_id)
        self.driver = None
        self.driver_lock = threading.Lock()
        self.state = "IDLE"
        self.current_job_id = None

    def start(self):
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
        while True:
            item = WMR_GLOBAL_Q.get()
            if item is None:
                break
            
            job_id, tid, raw_path, future, loop = item
            self.state = "PROCESSING"
            self.current_job_id = job_id
            prefix = f"[WMR-W{self.worker_id}][{job_id}]"

            try:
                clean_png, webp_path = self._process_job(job_id, tid, raw_path, prefix)
                loop.call_soon_threadsafe(future.set_result, (clean_png, webp_path))
            except Exception as e:
                log(f"{prefix} FAILED: {e}", file=sys.stderr)
                loop.call_soon_threadsafe(future.set_exception, e)
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
        
        # Upload
        up_js = "var el = document.querySelector('input[type=file]'); if (el) { el.style.display = 'block'; return true; } return false;"
        if safe_execute_script(drv, up_js):
            drv.find_element(By.CSS_SELECTOR, "input[type=file]").send_keys(str(raw_path))
        else:
            raise Exception("UPLOAD_FAILED")
            
        time.sleep(2)
        
        # Wait WMR ready
        ready = False
        for _ in range(WMR_TIMEOUT_S * 2):
            js = """
            var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
            if (!res) return false;
            var btns = res.querySelectorAll('button, a');
            for (var i=0; i<btns.length; i++) {
                var t = (btns[i].textContent || '').toLowerCase().trim();
                if (t === 'download png') { return true; }
            }
            return false;
            """
            if safe_execute_script(drv, js):
                ready = True
                break
            time.sleep(0.5)
            
        if not ready:
            raise Exception("WMR_TIMEOUT")
            
        log(f"{prefix} DOWNLOAD_BUTTON_DETECTED")
        
        # Download setup
        dl_dir = self.staging_dir / f"{job_id}_dl"
        dl_dir.mkdir(parents=True, exist_ok=True)
        set_tab_download_dir(drv, str(dl_dir))
        
        js = """
        var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
        var btns = res.querySelectorAll('button, a');
        for (var i=0; i<btns.length; i++) {
            var t = (btns[i].textContent || '').toLowerCase().trim();
            if (t === 'download png') { btns[i].click(); return true; }
        }
        return false;
        """
        if not safe_execute_script(drv, js):
            raise Exception("CLICK_FAILED")
            
        log(f"{prefix} DOWNLOAD_CLICKED")
        
        # Wait for file
        import shutil
        t0 = time.time()
        final_file = None
        while time.time() - t0 < 60:
            for f in dl_dir.iterdir():
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
            
        if not final_file:
            raise Exception("FILE_MISSING")
            
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
        for w in self._workers:
            w.start()

    def submit_job(self, job_id: str, chrome_tab_id: int, raw_png_path: str, future, loop):
        WMR_GLOBAL_Q.put((job_id, chrome_tab_id, raw_png_path, future, loop))
        log(f"[WMR_GLOBAL] Enqueued job {job_id} (Q_depth={WMR_GLOBAL_Q.qsize()})")
        
    def status(self):
        return [(w.worker_id, w.state, w.current_job_id) for w in self._workers]

    def quit_all(self):
        for _ in range(self._max):
            WMR_GLOBAL_Q.put(None)

'''

text = text[:start_idx] + new_wmr_code + text[end_idx:]
with open('v18_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("COMPLETELY REPLACED WMR")
