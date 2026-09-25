# ============================================================================
# STEP 6: BROWSER DRIVERS INITIALIZATION (CHROME + EDGE)
# ============================================================================
print("=" * 80)
print("🌐 STEP 6: INITIALIZING PERSISTENT CHROME & EDGE DRIVERS")
print("=" * 80)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

def set_tab_download_dir(drv, path):
    ap = os.path.abspath(str(path))
    os.makedirs(ap, exist_ok=True)
    try:
        drv.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": ap})
    except Exception:
        pass
    try:
        drv.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": ap, "eventsEnabled": False})
    except Exception:
        pass

def create_chrome_driver():
    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={SCREEN_W},{SCREEN_H}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-features=IsolateOrigins,site-per-process")
    opts.add_argument("--disable-site-isolation-trials")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    prefs = {
        "download.default_directory": str(JOBS_DOWNLOAD_BASE),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    opts.add_experimental_option("prefs", prefs)

    drv = webdriver.Chrome(options=opts)
    try:
        drv.execute_cdp_cmd('Network.enable', {})
    except Exception:
        pass
    return drv

def create_edge_driver(dl_dir):
    opts = EdgeOptions()
    opts.add_argument(f"--user-data-dir={EDGE_PROFILE_DIR}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    dl_dir_str = str(Path(dl_dir).resolve())
    prefs = {
        "download.default_directory": dl_dir_str,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    opts.add_experimental_option("prefs", prefs)

    drv = webdriver.Edge(options=opts)
    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': dl_dir_str
        })
    except Exception:
        pass
    return drv

print("  Launching Google Chrome with persistent profile...")
chrome_driver = create_chrome_driver()
print(f"  ✅ Google Chrome driver ready (PID: {chrome_driver.service.process.pid}).\n")


# ============================================================================
# STEP 7: GOOGLE ACCOUNT & GEMINI LOGIN VERIFICATION
# ============================================================================
print("=" * 80)
print("🔐 STEP 7: VERIFYING GOOGLE / GEMINI LOGIN STATE")
print("=" * 80)

def verify_gemini_login(drv):
    try:
        drv.get(GEMINI_APP_URL)
        time.sleep(3.0)

        if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 50:
            try:
                with open(COOKIES_FILE, 'rb') as f:
                    cks = pickle.load(f)
                    for ck in cks:
                        try:
                            drv.add_cookie(ck)
                        except Exception:
                            pass
                drv.get(GEMINI_APP_URL)
                time.sleep(2.5)
            except Exception:
                pass

        for sel in ["div.ql-editor", "textarea", "button[aria-label='New chat']", "a[aria-label='New chat']"]:
            if drv.find_elements(By.CSS_SELECTOR, sel):
                try:
                    cookies = drv.get_cookies()
                    if cookies:
                        with open(COOKIES_FILE, 'wb') as f:
                            pickle.dump(cookies, f)
                except Exception:
                    pass
                return True
    except Exception:
        pass
    return False

if verify_gemini_login(chrome_driver):
    print("  ✅ Google Gemini session is ACTIVE and verified.")
else:
    print("  ⚠️ Gemini login required! Please complete login via noVNC on port 6080.")
    t0 = time.time()
    while time.time() - t0 < 180:
        if verify_gemini_login(chrome_driver):
            print("  ✅ Login detected! Session saved.")
            break
        time.sleep(3.0)
print()


# ============================================================================
# STEP 8: DUAL-BROWSER INDEPENDENT WATERMARK REMOVER (EDGE WORKER)
# ============================================================================
print("=" * 80)
print("🧼 STEP 8: STARTING INDEPENDENT EDGE WATERMARK REMOVER")
print("=" * 80)

def convert_to_webp(png_path, max_size_kb=800):
    try:
        webp_path = os.path.splitext(png_path)[0] + '.webp'
        img = Image.open(png_path)
        img.load()
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA' if img.mode in ('P', 'LA', 'PA') else 'RGB')
        for q in (90, 80, 70, 60, 50, 40):
            buf = io.BytesIO()
            img.save(buf, format='WEBP', quality=q, method=4)
            data = buf.getvalue()
            if len(data) / 1024 <= max_size_kb or q == 40:
                Path(webp_path).write_bytes(data)
                return webp_path
        return webp_path
    except Exception as e:
        print(f"  ⚠️ WebP conversion failed: {e}")
        return None

def safe_execute_script(drv, script, timeout=5):
    try:
        drv.set_script_timeout(timeout)
        return drv.execute_script(script)
    except Exception:
        return None
    finally:
        try:
            drv.set_script_timeout(60)
        except Exception:
            pass

def _wmr_find_file_input(drv):
    try:
        inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if inputs:
            return inputs[0]
    except Exception:
        pass
    try:
        drv.execute_script(
            "document.querySelectorAll('input[type=\"file\"]').forEach(function(el){"
            "  el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';"
            "  el.removeAttribute('hidden'); el.removeAttribute('disabled');"
            "});"
        )
    except Exception:
        pass
    time.sleep(0.3)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def _wmr_check_status(drv):
    res = safe_execute_script(drv,
        "var btn = document.querySelector('button.bg-success');"
        "if (btn && !btn.disabled) return 'DONE';"
        "var spans = document.querySelectorAll('span');"
        "for (var i = 0; i < spans.length; i++) {"
        "    if ((spans[i].textContent || '').trim() === 'Download PNG') {"
        "        var b = spans[i].closest('button');"
        "        if (b && !b.disabled) return 'DONE';"
        "    }"
        "}"
        "var imgs = document.querySelectorAll('img');"
        "for (var i = 0; i < imgs.length; i++) {"
        "    var alt = (imgs[i].getAttribute('alt') || '').toLowerCase();"
        "    var src = imgs[i].getAttribute('src') || '';"
        "    if (alt.indexOf('after') !== -1 && (src.indexOf('blob:') === 0 || src.indexOf('data:') === 0)) return 'DONE';"
        "}"
        "var t = document.body ? document.body.innerText.toLowerCase() : '';"
        "if (t.indexOf('not detected') !== -1 || t.indexOf('no watermark') !== -1) return 'NOT_FOUND';"
        "return 'BUSY';"
    )
    return res.lower() if res else "busy"

def _wmr_click_download(drv, attempts=6):
    for _ in range(attempts):
        res = safe_execute_script(drv,
            "var btn = document.querySelector('button.bg-success');"
            "if (!btn) {"
            "    var spans = document.querySelectorAll('span');"
            "    for (var i = 0; i < spans.length; i++) {"
            "        if ((spans[i].textContent || '').trim() === 'Download PNG') {"
            "            btn = spans[i].closest('button'); break;"
            "        }"
            "    }"
            "}"
            "if (btn && !btn.disabled) {"
            "    btn.scrollIntoView({behavior:'instant',block:'center'});"
            "    btn.click(); return 'CLICKED';"
            "}"
            "return 'NO';"
        )
        if res == "CLICKED":
            return True
        time.sleep(0.3)
    return False

class EdgeWatermarkRemover:
    def __init__(self):
        self.work_queue = queue.Queue()
        self.driver = None
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _get_driver(self):
        with self.lock:
            if self.driver is None:
                log(f"[{WORKER_ID}] [STEP_LAUNCH_EDGE] Launching independent Microsoft Edge for watermark removal...")
                self.driver = create_edge_driver(WMR_DL_DIR)
            return self.driver

    def _run_loop(self):
        while True:
            item = self.work_queue.get()
            if item is None:
                break
            gen_id, tab_id, input_png_path, response_future, loop = item
            job_dir = Path(input_png_path).parent
            cleaned_target = job_dir / f'{gen_id}_clean.png'

            try:
                log(f"[{WORKER_ID}] {gen_id}: [STEP_EDGE_WMR_START] Removing watermark in Edge...")
                drv = self._get_driver()
                ok = self._process_image(drv, input_png_path, job_dir, cleaned_target)
                final_png = cleaned_target if (ok and cleaned_target.exists() and cleaned_target.stat().st_size > 1000) else input_png_path
                log(f"[{WORKER_ID}] {gen_id}: [STEP_EDGE_WMR_CLEANED] Cleaned image ready -> {final_png}")

                webp_target = job_dir / f'{gen_id}_clean.webp'
                webp_path = convert_to_webp(str(final_png))
                if webp_path and os.path.exists(webp_path) and str(webp_path) != str(webp_target):
                    try:
                        shutil.copy2(webp_path, str(webp_target))
                        webp_path = str(webp_target)
                    except Exception:
                        pass
                loop.call_soon_threadsafe(response_future.set_result, (str(final_png), str(webp_path) if webp_path else None))
            except Exception as ex:
                log(f"[{WORKER_ID}] {gen_id}: [STEP_EDGE_WMR_ERROR] Watermark removal notice ({ex}), using original", file=sys.stderr)
                webp_path = convert_to_webp(str(input_png_path))
                loop.call_soon_threadsafe(response_future.set_result, (str(input_png_path), str(webp_path) if webp_path else None))
            finally:
                self.work_queue.task_done()

    def _process_image(self, drv, image_path, job_dir, cleaned_target_path, timeout=90):
        try:
            drv.get(WMR_SERVICE_URL)
            time.sleep(1.2)
            try:
                for f in os.listdir(WMR_DL_DIR):
                    fp = os.path.join(WMR_DL_DIR, f)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except Exception:
                            pass
            except Exception:
                pass

            fi = _wmr_find_file_input(drv)
            if not fi:
                time.sleep(0.4)
                fi = _wmr_find_file_input(drv)
            if not fi:
                return False

            candidate_dirs = [WMR_DL_DIR, job_dir, Path('/content/downloads'), Path('/root/Downloads')]
            for cd in candidate_dirs:
                cd.mkdir(parents=True, exist_ok=True)
            files_before_map = {str(d): set(os.listdir(d)) for d in candidate_dirs if os.path.exists(d)}

            fi.send_keys(os.path.abspath(image_path))
            time.sleep(0.5)

            t0 = time.time()
            ready = False
            while time.time() - t0 < timeout:
                status = _wmr_check_status(drv)
                if status == "done":
                    ready = True
                    break
                elif status == "not_found":
                    return False
                time.sleep(0.6)
            if not ready:
                return False

            if not _wmr_click_download(drv):
                return False

            t_dl = time.time()
            fp = None
            while time.time() - t_dl < 30:
                for d in candidate_dirs:
                    if not os.path.exists(d):
                        continue
                    cur = set(os.listdir(d))
                    before = files_before_map.get(str(d), set())
                    new_files = [f for f in (cur - before) if not f.endswith(('.crdownload', '.tmp', '.part', '.download')) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                    if new_files:
                        cand = os.path.join(d, new_files[0])
                        if os.path.getsize(cand) >= 1000:
                            fp = cand
                            break
                if fp:
                    break
                time.sleep(0.3)

            if fp and os.path.exists(fp):
                cleaned_target_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(fp, str(cleaned_target_path))
                except Exception:
                    shutil.copy2(fp, str(cleaned_target_path))
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
                if cleaned_target_path.exists() and cleaned_target_path.stat().st_size > 1000:
                    return True
            return False
        except Exception:
            return False

    def remove_watermark_async(self, gen_id, tab_id, input_png_path):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.work_queue.put((gen_id, tab_id, input_png_path, future, loop))
        return future

edge_wmr_worker = EdgeWatermarkRemover()
print("  ✅ Edge Watermark Remover worker thread active.\n")


# ============================================================================
# STEP 9: CHROME MULTI-TAB POOL (STRICTLY 4 TABS: T0, T1, T2, T3)
# ============================================================================
print("=" * 80)
print(f"📑 STEP 9: CONFIGURING CHROME MULTI-TAB POOL ({MAX_CONCURRENT_TABS} TABS: T0, T1, T2, T3)")
print("=" * 80)

S_IDLE = "IDLE"
S_SUBMITTING = "SUBMITTING"
S_GEN_WAITING = "GEN_WAITING"
S_IMAGE_DETECTED = "IMAGE_DETECTED"
S_DOWNLOAD_STARTED = "DOWNLOAD_STARTED"
S_DOWNLOAD_WAITING = "DOWNLOAD_WAITING"
S_FINALIZING = "FINALIZING"
S_FAILED = "FAILED"

tab_states = []
initial_handle = chrome_driver.current_window_handle
tab_states.append({
    "tab_id": 0, "name": "T0", "handle": initial_handle,
    "state": S_IDLE, "job": None, "job_id": None, "gen": None, "prompt": None,
    "start_time": 0.0, "last_poll": 0.0, "next_poll": 0.0,
    "urls_before": set(), "chat_urls": set(), "target_src": None,
    "download_started": False, "stuck_polls": 0, "job_download_dir": None, "raw_download_path": None
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
        "state": S_IDLE, "job": None, "job_id": None, "gen": None, "prompt": None,
        "start_time": 0.0, "last_poll": 0.0, "next_poll": 0.0,
        "urls_before": set(), "chat_urls": set(), "target_src": None,
        "download_started": False, "stuck_polls": 0, "job_download_dir": None, "raw_download_path": None
    })
    print(f"  ✅ Tab T{i} ready.")

chrome_lock = asyncio.Lock()
print(f"  ✅ All {MAX_CONCURRENT_TABS} Chrome tabs ready with lowest-ID priority.\n")
