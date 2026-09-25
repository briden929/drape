def get_chrome_job_dir(tab_id: int, job_id: str):
    """Returns (job_dir, incoming_dir) for Chrome downloads."""
    job_dir = CHROME_DL_BASE / f'T{tab_id}' / job_id
    incoming = job_dir / 'incoming'
    incoming.mkdir(parents=True, exist_ok=True)
    return (job_dir, incoming)

def get_wmr_job_dir(chrome_tab_id: int, job_id: str):
    """Returns (job_dir, incoming_dir) for WMR Chrome output. Named by T-slot, not W-slot."""
    job_dir = WMR_DL_BASE / f'T{chrome_tab_id}' / job_id
    incoming = job_dir / 'incoming'
    incoming.mkdir(parents=True, exist_ok=True)
    return (job_dir, incoming)

def get_wmr_staging_dir(wmr_worker_id: int) -> Path:
    """Returns the dedicated staging directory for WMR Chrome worker W{wmr_worker_id}."""
    d = WMR_STAGING_BASE / f'W{wmr_worker_id}'
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_final_output_dir(chrome_tab_id: int, job_id: str):
    """Returns final_output dir for this job."""
    d = FINAL_OUTPUT_BASE / f'T{chrome_tab_id}' / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def run_cmd(cmd, desc='', timeout=120):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0 and desc:
            print(f'  âš\xa0ï¸\x8f Warning during {desc}: {res.stderr.strip()[:200]}')
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        if desc:
            print(f'  âš\xa0ï¸\x8f Timeout during {desc}')
        return False
    except Exception as e:
        if desc:
            print(f'  âš\xa0ï¸\x8f Error during {desc}: {e}')
        return False

def _get_pool():
    global _db_pool
    if _db_pool is None:
        with _db_pool_lock:
            if _db_pool is None:
                _db_pool = _pgpool.ThreadedConnectionPool(minconn=1, maxconn=24, dsn=os.environ.get('DATABASE_URL'), connect_timeout=10, options='-c statement_timeout=90000')
    return _db_pool

def _mark_used(conn):
    if len(_db_last_used) > 64:
        _db_last_used.clear()
    _db_last_used[id(conn)] = time.time()

def _checkout():
    p = _get_pool()
    for attempt in (1, 2):
        conn = p.getconn()
        if time.time() - _db_last_used.get(id(conn), 0) < _PING_AFTER_IDLE_S:
            return conn
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
            conn.rollback()
            return conn
        except Exception:
            p.putconn(conn, close=True)
            if attempt == 2:
                raise
    raise RuntimeError('unreachable')

@contextlib.contextmanager
def db_connection():
    conn = _checkout()
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            _get_pool().putconn(conn, close=True)
            raise
        _mark_used(conn)
        _get_pool().putconn(conn)
        raise
    else:
        _mark_used(conn)
        _get_pool().putconn(conn)

class _PooledBorrow:

    def __init__(self, conn):
        self._conn = conn
        self._returned = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if self._returned:
            return
        self._returned = True
        try:
            self._conn.rollback()
        except Exception:
            _get_pool().putconn(self._conn, close=True)
            return
        _mark_used(self._conn)
        _get_pool().putconn(self._conn)

def db_borrow():
    return _PooledBorrow(_checkout())

def credits_settle_look(look_id):
    with _mod_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("\n                UPDATE image_generations\n                SET status = 'done', completed_at = NOW()\n                WHERE id = %s AND status = 'processing'\n            ", (look_id,))
            conn.commit()
    return True

def credits_refund_look(look_id, reason='failed'):
    with _mod_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("\n                UPDATE image_generations\n                SET status = 'failed', error = %s, completed_at = NOW()\n                WHERE id = %s\n            ", (reason[:500], look_id))
            conn.commit()
    return True

def fs_configured():
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_PUBLIC_URL)

def _r2_client():
    return boto3.client('s3', endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com', aws_access_key_id=R2_ACCESS_KEY_ID, aws_secret_access_key=R2_SECRET_ACCESS_KEY, region_name='auto')

def fashion_tryon_prompt(has_model=False):
    if has_model:
        core_obj = 'CORE OBJECTIVE\nCreate one physically plausible commercial fashion photograph by rendering a professional fashion model wearing the garment from CLOTHING_REF, in the exact body pose, camera framing and scene established by MANNEQUIN_REF.\nThis is a constrained reconstruction task, not creative image synthesis.'
        face_ref_auth = 'IDENTITY AUTH: The MODEL_REF establishes the exact facial likeness.\n'
        input_order = '1) CLOTHING_REF\n2) MANNEQUIN_REF\n3) MODEL_REF'
    else:
        core_obj = 'CORE OBJECTIVE\nCreate one physically plausible commercial fashion photograph by rendering a professional fashion model wearing the garment from CLOTHING_REF, in the exact body pose, camera framing and scene established by MANNEQUIN_REF.\nThis is a constrained reconstruction task, not creative image synthesis.'
        face_ref_auth = ''
        input_order = '1) CLOTHING_REF\n2) MANNEQUIN_REF'
    return core_obj + '\n\n' + _FASHION_TRYON_BODY.format(face_ref_authority=face_ref_auth, input_order=input_order)

def download_remote_image(url, dest_dir):
    import time
    ext = Path(url.split('?')[0]).suffix or '.webp'
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f'ref-{hashlib.sha1(url.encode()).hexdigest()[:20]}{ext}'
    if dest.exists() and dest.stat().st_size > 0:
        return str(dest)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    last_err = None
    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                dest.write_bytes(resp.read())
            return str(dest)
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f'REF_DOWNLOAD_FAILED (exhausted 4 retries): {last_err}')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=25) as resp:
        dest.write_bytes(resp.read())
    return str(dest)

def push_generation(image_path, prompt, user_id=None, params=None, gen_id=None, webp_path=None, force=False):
    if not fs_configured():
        raise RuntimeError('fashion-studio push not configured')
    target_user_id = user_id or FASHION_STUDIO_USER_ID
    if not target_user_id:
        raise RuntimeError('no fashion-studio account linked')
    ext = Path(image_path).suffix.lstrip('.').lower() or 'png'
    if ext == 'jpeg':
        ext = 'jpg'
    content_type = mimetypes.guess_type(image_path)[0] or 'image/png'
    gen_id = gen_id or str(uuid.uuid4())
    key = f'generations/{target_user_id}/{gen_id}.{ext}'
    with open(image_path, 'rb') as f:
        data = f.read()
    _r2_client().put_object(Bucket=R2_BUCKET_NAME, Key=key, Body=data, ContentType=content_type, CacheControl='public, max-age=31536000, immutable')
    output_url = f'{R2_PUBLIC_URL}/{key}'
    webp_url = None
    if webp_path and os.path.exists(webp_path):
        webp_key = f'generations/{target_user_id}/{gen_id}.webp'
        with open(webp_path, 'rb') as f:
            webp_data = f.read()
        _r2_client().put_object(Bucket=R2_BUCKET_NAME, Key=webp_key, Body=webp_data, ContentType='image/webp', CacheControl='public, max-age=31536000, immutable')
        webp_url = f'{R2_PUBLIC_URL}/{webp_key}'
    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE image_generations SET output_url = %s, webp_url = %s, status = 'done', completed_at = NOW() WHERE id = %s", (output_url, webp_url, gen_id))
        conn.commit()
    finally:
        conn.close()
    return {'output_url': output_url, 'webp_url': webp_url, 'gen_id': gen_id}

def _port_open(port, host='127.0.0.1', timeout=1.0):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def _wait_for_port(port, label='service', max_wait=15):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        if _port_open(port):
            print(f'  âœ… {label} ready on port :{port}')
            return True
        time.sleep(0.5)
    print(f'  âš\xa0ï¸\x8f {label} not ready on port :{port}')
    return False

def _kill_port(port):
    try:
        run_cmd(f'fuser -k {port}/tcp', 'kill port')
    except Exception:
        pass
    time.sleep(0.3)

def start_display():
    global _display_obj
    run_cmd('pkill -f Xvfb', 'pkill xvfb')
    time.sleep(0.3)
    try:
        _display_obj = Display(visible=0, size=(SCREEN_W, SCREEN_H))
        _display_obj.start()
        os.environ['DISPLAY'] = f':{_display_obj.display}'
        print(f'  âœ… Display :{_display_obj.display} running at {SCREEN_W}x{SCREEN_H}.')
    except Exception as e:
        print(f'  âš\xa0ï¸\x8f pyvirtualdisplay fallback: {e}')
        subprocess.Popen(['Xvfb', ':99', '-screen', '0', f'{SCREEN_W}x{SCREEN_H}x24', '-ac'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ['DISPLAY'] = ':99'
        time.sleep(1.0)
        print('  âœ… Display :99 running.')

def start_vnc():
    global _x11vnc_proc, _novnc_proc
    disp = os.environ.get('DISPLAY', ':99')
    run_cmd('pkill -f x11vnc', 'pkill x11vnc')
    run_cmd('pkill -f websockify', 'pkill websockify')
    run_cmd('pkill -f fluxbox', 'pkill fluxbox')
    _kill_port(VNC_PORT)
    _kill_port(NOVNC_PORT)
    time.sleep(0.5)
    subprocess.Popen(['fluxbox'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    _x11vnc_proc = subprocess.Popen(['x11vnc', '-display', disp, '-forever', '-nopw', '-quiet', '-rfbport', str(VNC_PORT), '-shared'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    _wait_for_port(VNC_PORT, 'x11vnc', max_wait=10)
    novnc_web_dir = None
    for p in ['/usr/share/novnc', '/usr/share/noVNC', '/opt/novnc', '/opt/noVNC', '/usr/local/share/novnc']:
        if os.path.isfile(os.path.join(p, 'vnc.html')) or os.path.isfile(os.path.join(p, 'vnc_lite.html')):
            novnc_web_dir = p
            break
    if novnc_web_dir:
        vnc_html = os.path.join(novnc_web_dir, 'vnc.html')
        vnc_lite = os.path.join(novnc_web_dir, 'vnc_lite.html')
        if not os.path.isfile(vnc_html) and os.path.isfile(vnc_lite):
            shutil.copy(vnc_lite, vnc_html)
    cmd = ['websockify', '--web', novnc_web_dir, str(NOVNC_PORT), f'localhost:{VNC_PORT}'] if novnc_web_dir else ['websockify', str(NOVNC_PORT), f'localhost:{VNC_PORT}']
    _novnc_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    _wait_for_port(NOVNC_PORT, 'noVNC/websockify', max_wait=10)

def start_novnc_tunnel():
    global _cf_proc
    local_url = f'http://localhost:{NOVNC_PORT}'
    cf_bin = '/usr/local/bin/cloudflared'
    if os.path.exists(cf_bin):
        try:
            run_cmd('pkill -f cloudflared', 'pkill cloudflared')
            time.sleep(0.5)
            _cf_proc = subprocess.Popen([cf_bin, 'tunnel', '--url', local_url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            deadline = time.time() + 30
            while time.time() < deadline:
                line = _cf_proc.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                m = re.search('https://[a-z0-9\\-]+\\.trycloudflare\\.com', line)
                if m:
                    tb = m.group(0)
                    vnc_url = f'{tb}/vnc.html?autoconnect=true&resize=scale'
                    try:
                        _banner = f"<div style='background:linear-gradient(135deg,#1b5e20,#2e7d32);color:white;padding:16px;border-radius:10px;font-size:15px;font-weight:bold;margin:10px 0;box-shadow:0 4px 6px rgba(0,0,0,0.3);'>ðŸ–¥ï¸\x8f <b>noVNC Remote Desktop Stream:</b><br><br>ðŸŒ\x90 <a href='{vnc_url}' target='_blank' style='color:#a7ffeb;text-decoration:underline;'>Open Live UI ({vnc_url})</a><br></div>"
                        ipy_display(HTML(_banner))
                    except Exception:
                        pass
                    print(f'  ðŸŒ\x90 noVNC Public Link: {vnc_url}')
                    return tb
        except Exception as e:
            print(f'  âš\xa0ï¸\x8f noVNC tunnel notice: {e}')
    fallback = f'http://localhost:{NOVNC_PORT}/vnc.html'
    print(f'  âš\xa0ï¸\x8f noVNC listening locally: {fallback}')
    return fallback

def set_tab_download_dir(drv, path):
    ap = os.path.abspath(str(path))
    os.makedirs(ap, exist_ok=True)
    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': ap})
    except Exception:
        pass
    try:
        drv.execute_cdp_cmd('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': ap, 'eventsEnabled': False})
    except Exception:
        pass

def create_gemini_driver(tid: int):
    master_profile = Path(CHROME_PROFILE_DIR)
    worker_profile = Path(str(CHROME_PROFILE_DIR) + f'_T{tid}')
    if not worker_profile.exists():
        if master_profile.exists():
            import shutil
            log(f'[T{tid}] Cloning master Gemini profile...')
            shutil.copytree(master_profile, worker_profile)
        else:
            worker_profile.mkdir(parents=True, exist_ok=True)
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = worker_profile / fname
        if fpath.exists():
            try:
                fpath.unlink()
            except Exception:
                pass
    opts = ChromeOptions()
    opts.add_argument(f'--user-data-dir={worker_profile}')
    opts.add_argument('--profile-directory=Default')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument(f'--window-size={SCREEN_W},{SCREEN_H}')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_argument('--no-first-run')
    opts.add_argument('--no-default-browser-check')
    opts.add_argument('--disable-sync')
    dl_dir = CHROME_DL_BASE / f'T{tid}'
    dl_dir.mkdir(parents=True, exist_ok=True)
    prefs = {'download.default_directory': str(dl_dir), 'download.prompt_for_download': False, 'download.directory_upgrade': True, 'safebrowsing.enabled': False, 'safebrowsing.disable_download_protection': True, 'profile.default_content_setting_values.automatic_downloads': 1}
    opts.add_experimental_option('prefs', prefs)
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_experimental_option('useAutomationExtension', False)
    drv = webdriver.Chrome(options=opts)
    try:
        drv.execute_cdp_cmd('Network.enable', {})
    except Exception:
        pass
    return drv

def create_wmr_chrome_driver(worker_id: int) -> webdriver.Chrome:
    """Create a dedicated Chrome WMR driver for W{worker_id}.
    Downloads go to wmr_staging/W{worker_id}/ â€” fixed at launch time via Chrome prefs.
    Profile is completely isolated from Gemini Chrome and other WMR workers.
    Never uses Microsoft Edge.
    """
    staging_dir = get_wmr_staging_dir(worker_id)
    profile_dir = WMR_PROFILES_BASE / f'W{worker_id}'
    profile_dir.mkdir(parents=True, exist_ok=True)
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = profile_dir / fname
        if fpath.exists():
            try:
                fpath.unlink()
            except:
                pass
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
    prefs = {'download.default_directory': dl_dir_str, 'download.prompt_for_download': False, 'download.directory_upgrade': True, 'safebrowsing.enabled': False, 'safebrowsing.disable_download_protection': True, 'profile.default_content_setting_values.automatic_downloads': 1}
    opts.add_experimental_option('prefs', prefs)
    drv = webdriver.Chrome(options=opts)
    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': dl_dir_str})
    except Exception:
        pass
    log(f'[WMR-W{worker_id}] Browser = Google Chrome  staging={staging_dir}')
    return drv

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
        log(f'  âš\xa0ï¸\x8f WebP conversion failed: {e}')
        return None

def validate_image_file(path, min_size=DOWNLOAD_MIN_SIZE):
    """Returns True if path exists, is large enough, and PIL can open it."""
    try:
        p = Path(path)
        if not p.exists() or p.stat().st_size < min_size:
            return False
        with Image.open(p) as im:
            im.verify()
        return True
    except Exception:
        return False

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

def _wmr_expose_file_inputs(drv):
    try:
        drv.execute_script('document.querySelectorAll(\'input[type="file"]\').forEach(function(el){  el.style.cssText=\'display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;\';  el.removeAttribute(\'hidden\'); el.removeAttribute(\'disabled\');});')
    except Exception:
        pass
    time.sleep(0.3)

def _wmr_find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs:
        return inputs[0]
    _wmr_expose_file_inputs(drv)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def _wmr_check_status(drv: webdriver.Chrome):
    try:
        js = '\n        var res = document.querySelector(\'.result-container, .output-container, div[class*="result"]\');\n        if (!res) return null;\n        var btns = res.querySelectorAll(\'button, a\');\n        for (var i=0; i<btns.length; i++) {\n            var t = (btns[i].textContent || \'\').toLowerCase().trim();\n            if (t === \'download png\') {\n                return \'READY\';\n            }\n        }\n        return \'PROCESSING\';\n        '
        return safe_execute_script(drv, js)
    except:
        return None

def _wmr_click_download(drv: webdriver.Chrome, prefix: str) -> bool:
    try:
        js = '\n        var res = document.querySelector(\'.result-container, .output-container, div[class*="result"]\');\n        if (!res) return false;\n        var btns = res.querySelectorAll(\'button, a\');\n        for (var i=0; i<btns.length; i++) {\n            var t = (btns[i].textContent || \'\').toLowerCase().trim();\n            if (t === \'download png\') {\n                btns[i].click();\n                return true;\n            }\n        }\n        return false;\n        '
        return safe_execute_script(drv, js)
    except:
        return False

def is_logged_in_method_1_profile_avatar(driver):
    try:
        avatar_selectors = ["//div[@aria-label='Google Account']//img", "//img[contains(@src, 'lh3.googleusercontent.com')]", "//div[@data-is-profile-button='true']//img", "//a[@aria-label='Google Account']//img", "//img[@alt and contains(@alt, 'Profile')]"]
        for selector in avatar_selectors:
            try:
                elem = driver.find_element(By.XPATH, selector)
                if elem.is_displayed():
                    print('    Method 1: Profile avatar found!')
                    return True
            except:
                continue
        return False
    except:
        return False

def is_logged_in_method_2_email_text(driver):
    try:
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        email_pattern = '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, page_text)
        if emails:
            print(f'    Method 2: Email found: {emails[0]}')
            return True
        return False
    except:
        return False

def is_logged_in_method_3_account_elements(driver):
    try:
        account_selectors = ["//a[@aria-label='Google Account']", "//div[contains(text(),'Google Account')]", "//h1[contains(text(),'Google Account')]", "//*[contains(text(),'Personal info')]", "//*[contains(text(),'Security and sign-in')]", "//*[contains(text(),'Data and privacy')]"]
        for selector in account_selectors:
            try:
                elem = driver.find_element(By.XPATH, selector)
                if elem.is_displayed():
                    print(f'    Method 3: Account element found: {elem.text[:50]}')
                    return True
            except:
                continue
        return False
    except:
        return False

def is_logged_in_method_4_no_signin(driver):
    try:
        signin_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Sign in') or contains(., 'Sign In')] | " + "//a[contains(., 'Sign in') or contains(., 'Sign In')]")
        visible_signin = [btn for btn in signin_buttons if btn.is_displayed()]
        if not visible_signin:
            print("    Method 4: No 'Sign in' button found!")
            return True
        return False
    except:
        return False

def is_logged_in_method_5_url_check(driver):
    try:
        url = driver.current_url.lower()
        logged_in_patterns = ['myaccount.google.com', 'accounts.google.com/b/0/', 'accounts.google.com/ManageAccount']
        not_logged_patterns = ['signin', 'login', 'identifier', 'challenge']
        for pattern in logged_in_patterns:
            if pattern in url:
                for not_pattern in not_logged_patterns:
                    if not_pattern in url:
                        return False
                print(f'    Method 5: URL indicates logged in: {url[:60]}')
                return True
        return False
    except:
        return False

def is_logged_in_method_6_cookies(driver):
    try:
        cookies = driver.get_cookies()
        auth_cookies = ['SID', 'HSID', 'SSID', 'APISID', 'SAPISID', 'LOGIN_INFO', 'SIDCC']
        found = [c['name'] for c in cookies if c['name'] in auth_cookies]
        if len(found) >= 2:
            print(f'    Method 6: Auth cookies found: {found}')
            return True
        return False
    except:
        return False

def is_logged_in_method_7_profile_button(driver):
    try:
        profile_btns = driver.find_elements(By.CSS_SELECTOR, "[data-is-profile-button='true'], [aria-label*='Google Account'], [aria-label*='Profile']")
        for btn in profile_btns:
            if btn.is_displayed():
                print(f'    Method 7: Profile button found!')
                return True
        return False
    except:
        return False

def comprehensive_login_check(driver, page_name=''):
    url = driver.current_url.lower()
    if 'signin' in url or 'challenge/pwd' in url or 'identifier' in url:
        print('    CONCLUSION: ON SIGN-IN PAGE -> NOT LOGGED IN')
        return False
    print(f"\n Checking login status{(f' ({page_name})' if page_name else '')}...")
    print(f'   Current URL: {driver.current_url[:80]}')
    methods = [('Profile Avatar', is_logged_in_method_1_profile_avatar), ('Email Text', is_logged_in_method_2_email_text), ('Account Elements', is_logged_in_method_3_account_elements), ('No Sign-in Button', is_logged_in_method_4_no_signin), ('URL Check', is_logged_in_method_5_url_check), ('Auth Cookies', is_logged_in_method_6_cookies), ('Profile Button', is_logged_in_method_7_profile_button)]
    passed = 0
    for name, method in methods:
        try:
            if method(driver):
                passed += 1
        except:
            pass
    confidence = passed / len(methods) * 100
    print(f'\n    Login Confidence: {passed}/{len(methods)} methods passed ({confidence:.0f}%)')
    if confidence >= 43:
        print('    CONCLUSION: USER IS LOGGED IN!')
        return True
    print('    CONCLUSION: USER IS NOT LOGGED IN')
    return False

def extract_verification_number(driver):
    try:
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        for pattern in ['tap\\s+(\\d+)\\s+on\\s+your\\s+phone', 'then\\s+tap\\s+(\\d+)', 'verification\\s+code[:\\s]+(\\d+)', 'code[:\\s]+(\\d{2,6})', 'number[:\\s]+(\\d+)']:
            match = re.search(pattern, page_text.lower())
            if match:
                return match.group(1)
        return None
    except:
        return None

def extract_page_details(driver):
    details = {'page_text': '', 'input_fields': [], 'buttons': [], 'verification_number': None, 'headings': []}
    try:
        body = driver.find_element(By.TAG_NAME, 'body')
        details['page_text'] = body.text
        details['verification_number'] = extract_verification_number(driver)
        for field in driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[type='password'], input[type='tel']"):
            if field.is_displayed():
                details['input_fields'].append({'type': field.get_attribute('type'), 'id': field.get_attribute('id'), 'aria_label': field.get_attribute('aria-label'), 'placeholder': field.get_attribute('placeholder')})
        for btn in driver.find_elements(By.CSS_SELECTOR, "button, div[role='button']"):
            if btn.is_displayed() and (btn.text.strip() or btn.get_attribute('aria-label')):
                details['buttons'].append({'text': btn.text.strip(), 'aria_label': btn.get_attribute('aria-label')})
        for heading in driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, div[role='heading']"):
            if heading.is_displayed() and heading.text.strip():
                details['headings'].append(heading.text.strip())
    except:
        pass
    return details

def display_page_info(details, step_name=''):
    print('\n' + '=' * 70)
    print(f' PAGE INFORMATION - {step_name}')
    if details['verification_number']:
        print(f" VERIFICATION NUMBER: {details['verification_number']} ")
    print('=' * 70)

def take_screenshot(driver, step_name):
    try:
        filename = f"{SCREENSHOT_FOLDER}/{time.strftime('%H%M%S')}_{step_name}.png"
        driver.save_screenshot(filename)
        return filename
    except:
        return None

def save_cookies(driver):
    try:
        with open(COOKIES_FILE, 'wb') as f:
            pickle.dump(driver.get_cookies(), f)
        print('  Cookies saved locally')
        return True
    except:
        return False

def load_cookies(driver):
    try:
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'rb') as f:
                cookies = pickle.load(f)
            driver.get('https://www.google.com')
            time.sleep(1)
            for c in cookies:
                try:
                    driver.add_cookie(c)
                except:
                    pass
            print('  Cookies loaded from local storage')
            return True
        return False
    except:
        return False

def detect_push_notification_verification(driver):
    try:
        page_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
        return sum((1 for ind in ['check your', 'tap yes', 'notification', 'sent a notification', 'on your phone', "verify it's you"] if ind in page_text)) >= 2
    except:
        return False

def wait_for_push_notification_approval(driver, max_wait_seconds=60):
    checks = max_wait_seconds // 5
    for check in range(1, checks + 1):
        print(f'\n Check {check}/{checks}')
        for remaining in range(5, 0, -1):
            print(f'\r Waiting for approval: {remaining}s ', end='', flush=True)
            time.sleep(1)
        if comprehensive_login_check(driver, 'push approval check'):
            print('\n Push notification approved!')
            return True
    return False

def handle_verification_code_with_retry(driver, wait, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            page_details = extract_page_details(driver)
            display_page_info(page_details, f'Verification Attempt {attempt}')
            if detect_push_notification_verification(driver):
                take_screenshot(driver, f'push_notification_attempt_{attempt}')
                if wait_for_push_notification_approval(driver, max_wait_seconds=60 if attempt == 1 else 30):
                    return True
                if comprehensive_login_check(driver):
                    return True
                continue
            code_input = None
            for selector in ["input[type='tel']", "input[name='totpPin']", "input[id='totpPin']", "input[type='text'][name='pin']", "input[aria-label*='code']"]:
                try:
                    for field in driver.find_elements(By.CSS_SELECTOR, selector):
                        if field.is_displayed():
                            code_input = field
                            break
                    if code_input:
                        break
                except:
                    continue
            if not code_input:
                time.sleep(2)
                continue
            take_screenshot(driver, f'verification_code_attempt_{attempt}_before')
            otp = input(f'Enter Verification Code (Attempt {attempt}/{max_attempts}): ').strip()
            if not otp:
                continue
            code_input.clear()
            code_input.send_keys(otp)
            time.sleep(SHORT_WAIT)
            next_found = False
            for selector in ["//button[@id='next']", "//button[contains(., 'Next')]", "//button[@type='submit']"]:
                try:
                    btn = driver.find_element(By.XPATH, selector)
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        next_found = True
                        break
                except:
                    continue
            if not next_found:
                code_input.send_keys(Keys.RETURN)
            time.sleep(4)
            take_screenshot(driver, f'verification_code_attempt_{attempt}_after_submit')
            if comprehensive_login_check(driver):
                return True
            time.sleep(2)
        except:
            time.sleep(2)
    return False

def handle_google_login_fast(driver, wait):
    try:
        print('\n' + '=' * 70)
        print(' FAST GOOGLE LOGIN')
        print('=' * 70)
        if load_cookies(driver):
            driver.refresh()
            time.sleep(2)
            if comprehensive_login_check(driver, 'after cookies'):
                save_cookies(driver)
                return True
        driver.get('https://accounts.google.com/')
        time.sleep(3)
        if comprehensive_login_check(driver, 'accounts page'):
            save_cookies(driver)
            return True
        email = input('Enter your EMAIL: ').strip()
        if not email:
            return False
        email_field = wait.until(EC.presence_of_element_located((By.ID, 'identifierId')))
        email_field.clear()
        email_field.send_keys(email)
        time.sleep(1)
        next_btn = wait.until(EC.element_to_be_clickable((By.ID, 'identifierNext')))
        driver.execute_script('arguments[0].click();', next_btn)
        time.sleep(3)
        if comprehensive_login_check(driver, 'after email'):
            save_cookies(driver)
            return True
        pwd_field = None
        for by, selector in [(By.NAME, 'Passwd'), (By.CSS_SELECTOR, "input[type='password']"), (By.CSS_SELECTOR, '#password input')]:
            try:
                pwd_field = WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, selector)))
                if pwd_field and pwd_field.is_displayed():
                    break
            except:
                continue
        if not pwd_field:
            try:
                pwd_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'Passwd')))
            except:
                return False
        password = input('Enter your PASSWORD: ').strip()
        if not password:
            return False
        pwd_field.clear()
        pwd_field.send_keys(password)
        time.sleep(1)
        pwd_next = wait.until(EC.element_to_be_clickable((By.ID, 'passwordNext')))
        driver.execute_script('arguments[0].click();', pwd_next)
        time.sleep(4)
        if comprehensive_login_check(driver, 'after password'):
            save_cookies(driver)
            return True
        url = driver.current_url
        page_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
        if 'challenge' in url or 'verify' in url or 'check your' in page_text:
            if handle_verification_code_with_retry(driver, wait, MAX_VERIFICATION_ATTEMPTS):
                save_cookies(driver)
                return True
            return False
        if comprehensive_login_check(driver, 'final'):
            save_cookies(driver)
            return True
        if input('Are you logged in? (y/n): ').strip().lower() == 'y':
            save_cookies(driver)
            return True
        return False
    except Exception as e:
        print(f'\n ERROR: {e}')
        return False

def gemini_activity(driver):
    print('\n' + '=' * 70)
    print(' TURNING OFF GEMINI ACTIVITY')
    print('=' * 70)
    try:
        driver.get('https://myactivity.google.com/product/gemini')
        time.sleep(5)
        WebDriverWait(driver, 20).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(3)
        page_source = driver.page_source.lower()
        if 'off' in page_source and 'keep activity' in page_source:
            for elem in driver.find_elements(By.XPATH, "//*[contains(text(),'Off') or contains(text(),'off')]"):
                if elem.is_displayed() and 'activity' in elem.text.lower():
                    print(' Gemini activity appears to be already OFF!')
                    return True
        toggle_button = None
        for selector in ["[role='switch']", "span[jsname='V67aGc']", "button[jscontroller='LBaJxb']"]:
            try:
                for el in driver.find_elements(By.CSS_SELECTOR, selector):
                    if el.is_displayed():
                        toggle_button = el
                        break
                if toggle_button:
                    break
            except:
                continue
        if not toggle_button:
            for btn in driver.find_elements(By.XPATH, "//button[contains(@aria-label,'activity') or contains(@aria-label,'Keep activity')]"):
                if btn.is_displayed():
                    toggle_button = btn
                    break
        if not toggle_button:
            return False
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", toggle_button)
            time.sleep(1)
            driver.execute_script('arguments[0].click();', toggle_button)
        except:
            driver.execute_script('arguments[0].click();', toggle_button)
        time.sleep(2)
        clicked = False
        for attempt in range(3):
            try:
                for option in driver.find_elements(By.XPATH, "//div[contains(text(),'Turn off') and not(contains(text(),'delete'))] | //span[contains(text(),'Turn off') and not(contains(text(),'delete'))] | //button[contains(.,'Turn off') and not(contains(.,'delete'))] | //div[contains(text(),'Pause')] | //span[contains(text(),'Pause')] | //button[contains(.,'Pause')]"):
                    if option.is_displayed():
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", option)
                            time.sleep(0.5)
                            driver.execute_script('arguments[0].click();', option)
                            clicked = True
                            break
                        except:
                            driver.execute_script('arguments[0].click();', option)
                            clicked = True
                            break
                if clicked:
                    break
            except:
                pass
            time.sleep(1)
        time.sleep(2)
        for _ in range(5):
            try:
                for btn in driver.find_elements(By.XPATH, "//button[.//span[contains(text(),'Got it')]] | //button[.//span[contains(text(),'Pause')]] | //button[contains(.,'Turn off')] | //button[contains(.,'OK')] | //button[contains(.,'Confirm')] | //div[@role='button' and contains(.,'Got it')]"):
                    if btn.is_displayed() and btn.is_enabled():
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                            time.sleep(0.5)
                            driver.execute_script('arguments[0].click();', btn)
                        except:
                            driver.execute_script('arguments[0].click();', btn)
                        time.sleep(1)
            except:
                pass
            time.sleep(1)
        driver.refresh()
        time.sleep(4)
        print(' Activity toggle process completed!')
        return True
    except:
        return False

def _wmr_wait_for_new_file(incoming_dir: Path, files_before: set, timeout=30) -> Path | None:
    """Wait for a new stable image file to appear in incoming_dir."""
    t0 = time.time()
    last_size = -1
    stable_checks = 0
    candidate = None
    while time.time() - t0 < timeout:
        if candidate is None:
            for fn in os.listdir(incoming_dir):
                if fn.endswith(('.crdownload', '.tmp', '.part', '.download')):
                    continue
                if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    continue
                if fn in files_before:
                    continue
                fp = incoming_dir / fn
                try:
                    if fp.stat().st_size >= DOWNLOAD_MIN_SIZE:
                        candidate = fp
                        break
                except Exception:
                    pass
        if candidate:
            try:
                sz = candidate.stat().st_size
                if sz == last_size:
                    stable_checks += 1
                    if stable_checks >= DOWNLOAD_STABLE_CHECKS:
                        if validate_image_file(candidate):
                            return candidate
                        else:
                            candidate = None
                            stable_checks = 0
                            last_size = -1
                else:
                    last_size = sz
                    stable_checks = 0
            except Exception:
                pass
        time.sleep(0.5)
    return None

class ModelLimitReached(Exception):
    pass

class NewChatFailed(Exception):
    pass

class FileInputMissing(Exception):
    pass

class AttachmentCountMismatch(Exception):
    pass

class PromptFailed(Exception):
    pass

def _dismiss_new_chat_dialog(drv):
    """
    Handle 'Create a new chat and delete this one?' confirmation dialog.
    Clicks the affirmative button (New chat / Create / Confirm), NOT Cancel.
    Returns True if a dialog was found and handled.
    """
    try:
        for dialog_sel in ["div[role='dialog']", 'mat-dialog-container', "[data-test-id='confirm-dialog']"]:
            dialogs = drv.find_elements(By.CSS_SELECTOR, dialog_sel)
            for dialog in dialogs:
                if not dialog.is_displayed():
                    continue
                for btn in dialog.find_elements(By.TAG_NAME, 'button'):
                    if not btn.is_displayed():
                        continue
                    txt = (btn.text or '').strip().lower()
                    aria = (btn.get_attribute('aria-label') or '').lower()
                    combined = txt + ' ' + aria
                    if any((w in combined for w in ['new chat', 'create', 'confirm', 'delete', 'continue', 'yes'])):
                        if 'cancel' not in combined:
                            drv.execute_script('arguments[0].click();', btn)
                            log(f"    [DIALOG] Clicked affirmative button: '{btn.text.strip()}'")
                            time.sleep(0.5)
                            return True
    except Exception:
        pass
    try:
        res = drv.execute_script('\n            var modals = document.querySelectorAll(\'[role="dialog"], mat-dialog-container, [class*="dialog"], [class*="modal"]\');\n            for (var m = 0; m < modals.length; m++) {\n                var modal = modals[m];\n                if (!modal.offsetParent) continue;\n                var btns = modal.querySelectorAll(\'button\');\n                for (var i = 0; i < btns.length; i++) {\n                    var b = btns[i];\n                    if (!b.offsetParent) continue;\n                    var t = (b.textContent || \'\').trim().toLowerCase();\n                    var a = (b.getAttribute(\'aria-label\') || \'\').toLowerCase();\n                    var combined = t + \' \' + a;\n                    if ((combined.indexOf(\'new chat\') !== -1 || combined.indexOf(\'create\') !== -1 ||\n                         combined.indexOf(\'confirm\') !== -1 || combined.indexOf(\'delete\') !== -1) &&\n                        combined.indexOf(\'cancel\') === -1) {\n                        b.click(); return \'OK:\' + t;\n                    }\n                }\n            }\n            return \'NO\';\n        ')
        if res and res.startswith('OK:'):
            log(f'    [DIALOG] JS-dismissed: {res}')
            time.sleep(0.5)
            return True
    except Exception:
        pass
    return False

def open_new_chat_and_reload(drv, tid: int, job_id: str='') -> str:
    """
    Creates a verified new Gemini chat and returns the new chat URL.

    Algorithm:
    1. Capture old_url
    2. Click "New chat"
    3. Handle confirmation dialog
    4. Wait for URL to change (new_url != old_url, starts with /app/)
    5. Navigate to exact new_url
    6. Verify clean composer

    Returns new_chat_url on success. Raises NewChatFailed after retries.
    """
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    for attempt in range(1, MAX_NEW_CHAT_RETRIES + 1):
        try:
            old_url = drv.current_url
            log(f'{prefix} NEW_CHAT_START (attempt {attempt}) OLD_URL={old_url}')
            clicked = False
            res = drv.execute_script('\n                var sels = [\n                    \'a[aria-label="New chat"]\',\n                    \'button[aria-label="New chat"]\',\n                    \'div[aria-label="New chat"]\',\n                    \'[data-test-id="new-chat-button"]\',\n                    \'a[href="/app"]\',\n                ];\n                for (var s = 0; s < sels.length; s++) {\n                    var els = document.querySelectorAll(sels[s]);\n                    for (var i = 0; i < els.length; i++) {\n                        if (els[i].offsetParent !== null) {\n                            els[i].click(); return \'OK:\' + sels[s];\n                        }\n                    }\n                }\n                return \'NO\';\n            ')
            if res and res.startswith('OK:'):
                clicked = True
                log(f'{prefix} NEW_CHAT_CLICK -> {res}')
            else:
                drv.get(GEMINI_APP_URL)
                clicked = True
                log(f'{prefix} NEW_CHAT_NAVIGATE -> {GEMINI_APP_URL}')
            time.sleep(0.3)
            dialog_handled = _dismiss_new_chat_dialog(drv)
            if dialog_handled:
                log(f'{prefix} DIALOG_HANDLED')
                time.sleep(0.4)
            url_deadline = time.time() + 8.0
            new_url = None
            while time.time() < url_deadline:
                cur = drv.current_url
                if cur != old_url and 'gemini.google.com/app' in cur and (cur != GEMINI_APP_URL):
                    new_url = cur
                    break
                if 'gemini.google.com/app/' in cur and cur != old_url:
                    new_url = cur
                    break
                time.sleep(0.25)
            if not new_url:
                cur = drv.current_url
                if 'gemini.google.com/app' in cur:
                    new_url = cur
                    log(f'{prefix} NEW_CHAT_URL_UNCHANGED  accepting base URL: {new_url}')
            if not new_url:
                log(f'{prefix} NEW_CHAT_URL_NOT_CHANGED (attempt {attempt})  retrying')
                time.sleep(0.5)
                continue
            log(f'{prefix} NEW_CHAT_URL={new_url}')
            log(f'{prefix} RELOADING NEW CHAT URL')
            drv.get(new_url)
            time.sleep(1.0)
            log(f'{prefix} NEW_CHAT_RELOADED')
            if _verify_clean_composer(drv):
                log(f'{prefix} NEW_CHAT_VERIFIED ')
                return new_url
            else:
                log(f'{prefix} NEW_CHAT_COMPOSER_NOT_CLEAN (attempt {attempt})  retrying')
                time.sleep(0.5)
                continue
        except Exception as e:
            log(f'{prefix} NEW_CHAT_EXCEPTION (attempt {attempt}): {e}', file=sys.stderr)
            time.sleep(0.5)
            continue
    raise NewChatFailed(f'Tab T{tid}: Could not create a verified new Gemini chat after {MAX_NEW_CHAT_RETRIES} attempts')

def _verify_clean_composer(drv) -> bool:
    """
    Verifies that the current page has a clean, empty Gemini image composer:
    - Image prompt editor exists and is empty
    - No old attachment chips
    - No previous generated model-response with images
    """
    try:
        t0 = time.time()
        while time.time() - t0 < 6.0:
            editors = drv.find_elements(By.CSS_SELECTOR, 'div.ql-editor')
            if editors and any((e.is_displayed() for e in editors)):
                break
            time.sleep(0.3)
        for ed in drv.find_elements(By.CSS_SELECTOR, 'div.ql-editor'):
            if not ed.is_displayed():
                continue
            txt = (ed.text or '').strip()
            if txt and txt != ed.get_attribute('data-placeholder'):
                return False
            break
        chip_count = 0
        for sel in ["button[aria-label='close attachment']", 'gem-media-attachment', 'uploader-file-preview', '.attachment-preview-wrapper', "div[data-test-id='uploaded-img']"]:
            chip_count += len([e for e in drv.find_elements(By.CSS_SELECTOR, sel) if e.is_displayed()])
        if chip_count > 0:
            return False
        for img in drv.find_elements(By.CSS_SELECTOR, 'model-response img, single-image img, generated-image img'):
            if img.is_displayed():
                src = img.get_attribute('src') or ''
                if src.startswith('blob:') or 'googleusercontent' in src:
                    return False
        return True
    except Exception:
        return False

def _get_current_model_text(drv):
    selectors = ["div[data-test-id='logo-pill-label-container'] span.picker-primary-text", "div[data-test-id='logo-pill-label-container'] span.gds-body-m", 'span.picker-primary-text']
    for sel in selectors:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    txt = (el.text or '').strip()
                    if txt:
                        return txt
        except Exception:
            continue
    try:
        txt = drv.execute_script('var el=document.querySelector(  \'div[data-test-id="logo-pill-label-container"] span.picker-primary-text,   div[data-test-id="logo-pill-label-container"] span.gds-body-m\');return el ? el.textContent.trim() : \'\';')
        return (txt or '').strip()
    except Exception:
        return ''

def _open_model_picker(drv):
    try:
        btn = drv.find_element(By.CSS_SELECTOR, "button[data-test-id='bard-mode-menu-button']")
        if btn and btn.is_displayed():
            drv.execute_script('arguments[0].click();', btn)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        el = drv.find_element(By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container']")
        if el and el.is_displayed():
            drv.execute_script('arguments[0].click();', el)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        res = drv.execute_script("var spans=document.querySelectorAll('span.picker-primary-text,span.gds-body-m');for(var i=0;i<spans.length;i++){  var s=spans[i]; if(!s.offsetParent) continue;  var b=s.closest('button');  if(b&&!b.disabled){ b.click(); return 'OK'; }} return 'NO';")
        if res == 'OK':
            time.sleep(0.45)
            return True
    except Exception:
        pass
    return False

def _click_flash_in_picker(drv):

    def _is_valid_flash(el):
        try:
            txt = (el.text or '').strip().lower()
            return 'flash' in txt and 'lite' not in txt
        except Exception:
            return False
    for tid in ['bard-mode-option-flash', 'mode-option-flash', 'flash-option', 'model-flash']:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, f"[data-test-id='{tid}']"):
                if el.is_displayed():
                    drv.execute_script('arguments[0].click();', el)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue
    for sel in ['mat-option', "[role='option']", "[role='menuitem']", "[role='menuitemradio']", "button[class*='mode-option']", "button[class*='picker']"]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed() and _is_valid_flash(el):
                    drv.execute_script('arguments[0].click();', el)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue
    xpaths = ["//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]/ancestor-or-self::button[1]", "//mat-option[.//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]]", "//*[@role='option' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]"]
    for xp in xpaths:
        try:
            for el in drv.find_elements(By.XPATH, xp):
                if el.is_displayed():
                    drv.execute_script('arguments[0].click();', el)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue
    try:
        res = drv.execute_script('\n            var candidates = document.querySelectorAll(\'mat-option, [role="option"], [role="menuitem"], [role="menuitemradio"], button\');\n            for (var i = 0; i < candidates.length; i++) {\n                var el = candidates[i];\n                if (!el.offsetParent) continue;\n                var txt = (el.textContent || \'\').trim().toLowerCase();\n                if (txt.indexOf(\'flash\') === -1) continue;\n                if (txt.indexOf(\'lite\') !== -1) continue;\n                if (txt.length > 60) continue;\n                var dis = el.getAttribute(\'disabled\') || el.getAttribute(\'aria-disabled\') === \'true\';\n                if (dis) return \'DISABLED\';\n                el.click(); return \'OK:\' + txt;\n            } return \'NO\';\n        ')
        if res and res.startswith('OK'):
            time.sleep(0.4)
            return True
        if res == 'DISABLED':
            raise ModelLimitReached('Flash disabled in picker')
    except ModelLimitReached:
        raise
    except Exception:
        pass
    return False

def _verify_flash_selected(drv, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            txt = _get_current_model_text(drv)
            if txt and 'flash' in txt.lower() and ('lite' not in txt.lower()):
                return True
        except Exception:
            pass
        time.sleep(0.15)
    return False

def ensure_flash_mode(drv, tid=0, job_id=''):
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    current = _get_current_model_text(drv)
    if current and 'flash' in current.lower() and ('lite' not in current.lower()):
        log(f"{prefix} FLASH_VERIFIED (already active: '{current}')")
        return True
    for attempt in range(1, 4):
        if not _open_model_picker(drv):
            time.sleep(0.4)
            continue
        time.sleep(0.3)
        try:
            clicked = _click_flash_in_picker(drv)
        except ModelLimitReached:
            try:
                drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            except Exception:
                pass
            raise
        if clicked and _verify_flash_selected(drv, timeout=2.5):
            log(f'{prefix} FLASH_VERIFIED ')
            return True
        try:
            drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError(f'Tab T{tid}: Flash mode could not be verified')

def click_plus_button(drv):
    try:
        res = drv.execute_script('\n            var btns = document.querySelectorAll(\'button\');\n            for (var i = 0; i < btns.length; i++) {\n                var b = btns[i];\n                if (b.offsetParent === null) continue;\n                var lbl = (b.getAttribute(\'aria-label\') || \'\').toLowerCase();\n                if (lbl.indexOf(\'upload\') !== -1 || lbl.indexOf(\'tools\') !== -1 || lbl.indexOf(\'plus\') !== -1) {\n                    b.click(); return \'OK\';\n                }\n                var icon = b.querySelector(\'mat-icon[fonticon="plus"], mat-icon[data-mat-icon-name="plus"]\');\n                if (icon) { b.click(); return \'OK\'; }\n            } return \'NO\';\n        ')
        if res == 'OK':
            time.sleep(0.3)
            return True
    except Exception:
        pass
    for sel in ['button[aria-label="Upload and tools"]', 'button[jslog*="300142"]', 'button[aria-haspopup="menu"][aria-label*="Upload"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script('arguments[0].click();', btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    return False

def is_create_image_mode(drv):
    try:
        editors = drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder*='Describe'], div.ql-editor[data-placeholder*='image']")
        if any((e.is_displayed() for e in editors)):
            return True
        signals = ["mat-icon[data-mat-icon-name='image_create']", "mat-icon[fonticon='image_create']", "button[aria-label*='Aspect ratio']", "//span[contains(text(), 'Aspect ratio')]", "//h1[contains(text(), 'Create images')]", "//button[contains(., 'Images')]"]
        for sig in signals:
            by = By.XPATH if sig.startswith('//') else By.CSS_SELECTOR
            for el in drv.find_elements(by, sig):
                if el.is_displayed():
                    return True
        return False
    except Exception:
        return False
        signals = ["mat-icon[data-mat-icon-name='image_create']", "mat-icon[fonticon='image_create']", "button[aria-label*='Aspect ratio']", "//span[contains(text(), 'Aspect ratio')]", "//button[contains(., 'Images')]"]
        for sig in signals:
            by = By.XPATH if sig.startswith('//') else By.CSS_SELECTOR
            for el in drv.find_elements(by, sig):
                if el.is_displayed():
                    return True
        return len(editors) > 0
    except Exception:
        return False

def ensure_create_image_mode(drv, tid=0, job_id=''):
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    deadline = time.time() + 4.0
    while time.time() < deadline:
        if is_create_image_mode(drv):
            log(f'{prefix} CREATE_IMAGE_VERIFIED')
            return True
        time.sleep(0.5)
    for attempt in range(1, 3):
        root = _get_composer_root(drv, prefix)
        if root and _click_composer_plus(drv, prefix, root):
            time.sleep(0.5)
            try:
                btns = drv.find_elements(By.CSS_SELECTOR, "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button")
                for btn in btns:
                    if btn.is_displayed() and 'create image' in btn.text.lower():
                        drv.execute_script('arguments[0].click();', btn)
                        time.sleep(1.0)
                        break
                else:
                    for icon in drv.find_elements(By.CSS_SELECTOR, "mat-icon[data-mat-icon-name='image_create'], mat-icon[fonticon='image_create']"):
                        if icon.is_displayed():
                            btn = drv.execute_script("var e=arguments[0];while(e&&e.tagName!=='BUTTON')e=e.parentElement;return e;", icon)
                            if btn and btn.is_displayed():
                                drv.execute_script('arguments[0].click();', btn)
                                time.sleep(1.0)
                                break
            except Exception:
                pass
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if is_create_image_mode(drv):
                log(f'{prefix} CREATE_IMAGE_VERIFIED')
                return True
            time.sleep(0.5)
    raise RuntimeError(f'Tab T{tid}: Failed to activate Create image mode')

def _expose_file_inputs(drv):
    try:
        drv.execute_script('\n            document.querySelectorAll(\'input[type="file"]\').forEach(function(el){\n                el.style.cssText=\'display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;\';\n                el.removeAttribute(\'hidden\'); el.removeAttribute(\'disabled\');\n            });\n        ')
    except Exception:
        pass

def _find_file_input(drv):
    _expose_file_inputs(drv)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def _get_composer_root(drv, prefix):
    """
    Locates the main Gemini image composer root container.
    """
    try:
        res = drv.execute_script('\n            var ed = document.querySelector(\'div.ql-editor[data-placeholder*="Describe"], div.ql-editor[data-placeholder*="image"]\');\n            if (!ed) ed = document.querySelector(\'div[contenteditable="true"]\');\n            if (!ed) return null;\n            return ed.closest(\'user-input\') || ed.closest(\'.input-area-container\') || ed.parentElement.parentElement.parentElement;\n        ')
        if res:
            log(f'{prefix} COMPOSER_ROOT_FOUND')
            return res
    except Exception:
        pass
    log(f'{prefix} COMPOSER_ROOT_NOT_FOUND')
    return None

def _check_wrong_sidebar_menu(drv, prefix):
    try:
        res = drv.execute_script("\n            var text = document.body.innerText.toLowerCase();\n            return (text.includes('share conversation') && text.includes('pin') && text.includes('rename') && text.includes('delete'));\n        ")
        if res:
            log(f'{prefix} WRONG_SIDEBAR_MENU_OPEN')
            ActionChains(drv).send_keys(Keys.ESCAPE).perform()
            log(f'{prefix} ESC_SENT')
            time.sleep(0.5)
            return True
    except Exception:
        pass
    return False

def _exact_click(drv, element, prefix, label):
    """
    Scrolls, validates elementFromPoint, and clicks safely.
    """
    try:
        drv.execute_script("arguments[0].scrollIntoView({block:'center', behavior:'instant'});", element)
        time.sleep(0.15)
        rect = drv.execute_script('\n            var r = arguments[0].getBoundingClientRect();\n            return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};\n        ', element)
        if rect['w'] == 0 or rect['h'] == 0:
            return False
        cx = rect['x'] + rect['w'] / 2
        cy = rect['y'] + rect['h'] / 2
        log(f"{prefix} {label}_RECT x={cx} y={cy} w={rect['w']} h={rect['h']}")
        owns = drv.execute_script('\n            var el = arguments[0];\n            var topEl = document.elementFromPoint(arguments[1], arguments[2]);\n            if (!topEl) return false;\n            if (topEl === el || el.contains(topEl) || topEl.contains(el)) return true;\n            return false;\n        ', element, cx, cy)
        if not owns:
            log(f'{prefix} TARGET_OCCLUDED_OR_MISSING at {cx},{cy}')
            return False
        try:
            ActionChains(drv).move_to_element(element).click().perform()
            log(f'{prefix} {label}_CLICKED (Action)')
            return True
        except Exception:
            try:
                element.click()
                log(f'{prefix} {label}_CLICKED (Native)')
                return True
            except Exception:
                drv.execute_script('arguments[0].click();', element)
                log(f'{prefix} {label}_CLICKED (JS)')
                return True
    except Exception as e:
        log(f'{prefix} EXACT_CLICK_ERROR: {e}')
        return False

def _click_composer_plus(drv, prefix, composer_root):
    try:
        btns = drv.execute_script('\n            var root = arguments[0];\n            var cands = Array.from(root.querySelectorAll(\'button\'));\n            var res = [];\n            for (var i=0; i<cands.length; i++) {\n                var b = cands[i];\n                if (b.offsetParent === null) continue;\n                var aria = (b.getAttribute(\'aria-label\') || \'\').toLowerCase();\n                var jslog = (b.getAttribute(\'jslog\') || \'\').toLowerCase();\n                if (aria.includes(\'upload and tools\') || aria.includes(\'upload\') || jslog.includes(\'300142\')) {\n                    res.push(b);\n                } else if (b.querySelector(\'mat-icon[fonticon="plus"], mat-icon[data-mat-icon-name="plus"]\')) {\n                    res.push(b);\n                }\n            }\n            return res;\n        ', composer_root)
        for btn in btns:
            if btn.is_displayed() and btn.is_enabled():
                log(f'{prefix} COMPOSER_PLUS_FOUND')
                if _exact_click(drv, btn, prefix, 'COMPOSER_PLUS'):
                    return True
    except Exception:
        pass
    log(f'{prefix} COMPOSER_PLUS_NOT_FOUND')
    return False

def _click_drawer_upload_files(drv, prefix):
    try:
        drawer = drv.execute_script('\n            var menus = document.querySelectorAll(\'[role="menu"], [role="dialog"], .cdk-overlay-pane, .mat-mdc-menu-panel\');\n            for (var i=0; i<menus.length; i++) {\n                if (menus[i].offsetParent !== null) {\n                    var text = menus[i].innerText.toLowerCase();\n                    if (text.includes(\'upload files\') || text.includes(\'upload from computer\') || text.includes(\'create image\')) {\n                        return menus[i];\n                    }\n                }\n            }\n            return null;\n        ')
        if not drawer:
            log(f'{prefix} DRAWER_ROOT_NOT_FOUND')
            return False
        log(f'{prefix} DRAWER_ROOT_FOUND')
        btns = drv.execute_script('\n            var root = arguments[0];\n            var cands = Array.from(root.querySelectorAll(\'button, [role="menuitem"]\'));\n            var res = [];\n            for (var i=0; i<cands.length; i++) {\n                var b = cands[i];\n                if (b.offsetParent === null) continue;\n                var testId = b.getAttribute(\'data-test-id\') || \'\';\n                var text = b.innerText.toLowerCase();\n                var aria = (b.getAttribute(\'aria-label\') || \'\').toLowerCase();\n                if (testId === \'local-images-files-uploader-button\' || text.includes(\'upload files\') || text.includes(\'upload from computer\') || aria.includes(\'upload\')) {\n                    res.push(b);\n                }\n            }\n            return res;\n        ', drawer)
        for btn in btns:
            if btn.is_displayed():
                log(f'{prefix} UPLOAD_CONTROL_FOUND')
                if _exact_click(drv, btn, prefix, 'UPLOAD_CONTROL'):
                    return True
    except Exception:
        pass
    return False

def perform_robust_upload(drv, paths, tid=0, job_id=''):
    """
    State machine for strictly scoped DOM upload.
    """
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    log(f'{prefix} FILE_INPUT_DIRECT_CHECK')
    fi = _find_file_input(drv)
    if fi:
        log(f'{prefix} FILE_INPUT_READY (direct)')
        try:
            fi.send_keys('\n'.join(paths))
            log(f'{prefix} UPLOAD_SENT {len(paths)} files')
            return
        except Exception as e:
            raise RuntimeError(f'UPLOAD_FAILED: {e}')
    log(f'{prefix} FILE_INPUT_NOT_FOUND')
    for attempt in range(1, 4):
        log(f'{prefix} UPLOAD_DRAWER_OPENING (attempt {attempt})')
        if _check_wrong_sidebar_menu(drv, prefix):
            log(f'{prefix} TARGET_REACQUIRED (menus closed)')
        root = _get_composer_root(drv, prefix)
        if not root:
            if attempt == 3:
                raise RuntimeError('COMPOSER_ROOT_MISSING')
            drv.refresh()
            time.sleep(2.0)
            ensure_create_image_mode(drv, tid, job_id)
            continue
        if not _click_composer_plus(drv, prefix, root):
            if attempt == 3:
                raise RuntimeError('COMPOSER_PLUS_CLICK_FAILED')
            continue
        drawer_opened = False
        for _ in range(25):
            if _check_wrong_sidebar_menu(drv, prefix):
                break
            if _click_drawer_upload_files(drv, prefix):
                drawer_opened = True
                break
            time.sleep(0.2)
        if drawer_opened:
            deadline = time.time() + 6.0
            while time.time() < deadline:
                fi = _find_file_input(drv)
                if fi:
                    log(f'{prefix} FILE_INPUT_READY')
                    break
                time.sleep(0.3)
            if fi:
                try:
                    fi.send_keys('\n'.join(paths))
                    log(f'{prefix} UPLOAD_SENT {len(paths)} files')
                    return
                except Exception as e:
                    raise RuntimeError(f'UPLOAD_FAILED: {e}')
        log(f'{prefix} UPLOAD_DRAWER_FAILED  reloading page before retry')
        drv.refresh()
        time.sleep(2.0)
        ensure_create_image_mode(drv, tid, job_id)
    raise RuntimeError('FILE_INPUT_MISSING after 3 attempts')

def verify_attachment_count(drv, expected: int, tid=0, job_id='') -> tuple:
    """
    Polls until attachment count == expected. Uses canonical identities to avoid double counting wrappers.
    Returns (verified: bool, actual_count: int).
    """
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    if expected == 0:
        return (True, 0)
    deadline = time.time() + 15.0
    actual_count = 0
    while time.time() < deadline:
        identities = set()
        try:
            els = drv.find_elements(By.CSS_SELECTOR, 'gem-media-attachment')
            for idx, el in enumerate(els):
                if el.is_displayed():
                    identities.add(f'attachment-{idx}')
        except Exception:
            pass
        actual_count = len(identities)
        if actual_count == expected:
            log(f'{prefix} ATTACHMENT_IDENTITIES expected={expected} actual={actual_count}')
            log(f'{prefix} ATTACHMENTS_VERIFIED')
            return (True, actual_count)
        time.sleep(0.5)
    log(f'{prefix} ATTACHMENT_TIMEOUT expected {expected}, actual {actual_count}')
    return (False, actual_count)

def normalize_prompt_text(text):
    if not text:
        return ''
    t = text.replace('\r\n', '\n').replace('\r', '\n')
    t = re.sub('[ \\t]+', ' ', t)
    lines = [line.rstrip() for line in t.split('\n')]
    return '\n'.join(lines).strip()

def _set_clipboard_xclip(text):
    disp = os.environ.get('DISPLAY', ':99')
    env = {**os.environ, 'DISPLAY': disp}
    try:
        proc = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        proc.communicate(input=text.encode('utf-8'), timeout=5)
        return proc.returncode == 0
    except Exception:
        return False

def get_quill_editor(drv):
    for sel in ["div.ql-editor[data-placeholder='Describe your image']", "div.ql-editor[contenteditable='true']", "rich-textarea div[contenteditable='true']", "div[contenteditable='true']"]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return el
        except Exception:
            pass
    return None

def _verify_editor_prompt(drv, editor, expected_text, tid=0, job_id=''):
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    try:
        actual_raw = editor.text or ''
        if not actual_raw:
            actual_raw = drv.execute_script("return (arguments[0].textContent || '');", editor) or ''
        expected_norm = normalize_prompt_text(expected_text)
        actual_norm = normalize_prompt_text(actual_raw)
        exp_len = len(expected_norm)
        act_len = len(actual_norm)
        log(f'{prefix} PROMPT_LENGTH expected={exp_len} actual={act_len}')
        if exp_len == 0:
            return act_len == 0
        coverage = act_len / exp_len if exp_len > 0 else 0
        if coverage < 0.98 or coverage > 1.05:
            log(f'{prefix} PROMPT_LENGTH_MISMATCH coverage={coverage:.2%}')
            return False
        prefix_len = min(80, exp_len)
        if actual_norm[:prefix_len] != expected_norm[:prefix_len]:
            log(f"{prefix} PROMPT_START_MISMATCH: '{actual_norm[:30]}' != '{expected_norm[:30]}'")
            return False
        log(f'{prefix} PROMPT_START_VERIFIED')
        suffix_len = min(80, exp_len)
        if actual_norm[-suffix_len:] != expected_norm[-suffix_len:]:
            log(f"{prefix} PROMPT_END_MISMATCH: '{actual_norm[-30:]}' != '{expected_norm[-30:]}'")
            return False
        log(f'{prefix} PROMPT_END_VERIFIED')
        log(f'{prefix} PROMPT_VERIFIED ')
        return True
    except Exception as e:
        log(f'{prefix} Prompt verification error: {e}')
        return False

def _inject_prompt_atomic(drv, text, tid=0, job_id=''):
    """
    Inject full prompt in ONE atomic operation.
    Primary: Chrome CDP Input.insertText
    Fallback: single xclip Ctrl+V
    No chunked/loop typing ever.
    """
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    editor = get_quill_editor(drv)
    if not editor:
        raise PromptFailed(f'Tab T{tid}: Quill editor not found')
    for attempt in range(1, 3):
        try:
            drv.execute_script('arguments[0].focus();', editor)
            time.sleep(0.1)
            ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
            time.sleep(0.05)
            ActionChains(drv).send_keys(Keys.DELETE).perform()
            drv.execute_script("document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);")
            time.sleep(0.1)
            cdp_ok = False
            try:
                drv.execute_cdp_cmd('Input.insertText', {'text': text})
                cdp_ok = True
                log(f'{prefix} PROMPT_INJECTING via CDP')
            except Exception as cdp_err:
                log(f'{prefix} CDP notice ({cdp_err}), trying xclip fallback...')
            if not cdp_ok:
                if _set_clipboard_xclip(text):
                    drv.execute_script('arguments[0].focus();', editor)
                    ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                    log(f'{prefix} PROMPT_INJECTING via xclip Ctrl+V')
                else:
                    log(f'{prefix} xclip failed', file=sys.stderr)
            time.sleep(0.3)
            if _verify_editor_prompt(drv, editor, text, tid=tid, job_id=job_id):
                return True
            else:
                log(f'{prefix} PROMPT_VERIFY_FAIL attempt {attempt}  clearing and retrying')
                drv.execute_script("arguments[0].focus();document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);", editor)
                time.sleep(0.3)
        except PromptFailed:
            raise
        except Exception as e:
            log(f'{prefix} Prompt injection exception (attempt {attempt}): {e}')
            try:
                drv.execute_script("arguments[0].focus();document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);", editor)
            except Exception:
                pass
            time.sleep(0.3)
    raise PromptFailed(f'Tab T{tid}: Prompt injection failed after 2 atomic attempts')

def _click_send_button(drv, tid=0, job_id=''):
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    root = _get_composer_root(drv, prefix)
    if not root:
        log(f'{prefix} SEND_TARGET_NOT_FOUND (no composer root)')
        return False
    try:
        btns = drv.execute_script('\n            var root = arguments[0];\n            var cands = Array.from(root.querySelectorAll(\'button\'));\n            var res = [];\n            for (var i=0; i<cands.length; i++) {\n                var b = cands[i];\n                if (b.offsetParent === null) continue;\n                var aria = (b.getAttribute(\'aria-label\') || \'\').toLowerCase();\n                var testId = (b.getAttribute(\'data-test-id\') || \'\').toLowerCase();\n                if (aria.includes(\'send\') || testId === \'send-button\') {\n                    res.push(b);\n                } else if (b.querySelector(\'mat-icon[fonticon="arrow_upward"], mat-icon[data-mat-icon-name="arrow_upward"], mat-icon[fonticon="send"], mat-icon[data-mat-icon-name="send"]\')) {\n                    res.push(b);\n                }\n            }\n            return res;\n        ', root)
        for btn in btns:
            if btn.is_displayed() and btn.is_enabled():
                log(f'{prefix} SEND_TARGET_FOUND')
                if _exact_click(drv, btn, prefix, 'SEND'):
                    return True
    except Exception as e:
        log(f'{prefix} SEND_ERROR: {e}')
    return False

def verify_generation_started(drv, timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            stop = drv.execute_script('\n                var sels = [\'button[aria-label="Stop generating"]\', \'button[aria-label="Cancel"]\',\n                            \'mat-icon[fonticon="stop"]\', \'mat-icon[data-mat-icon-name="stop"]\'];\n                for (var s = 0; s < sels.length; s++) {\n                    var els = document.querySelectorAll(sels[s]);\n                    for (var i = 0; i < els.length; i++) {\n                        if (els[i].offsetParent !== null) return true;\n                    }\n                } return false;\n            ')
            if stop:
                return True
            loading = drv.execute_script('\n                var el = document.querySelector(\'image-loading-overlay [data-test-id="image-loading-overlay"]\');\n                if (el && el.offsetParent !== null) {\n                    return !el.classList.contains(\'done-generating\');\n                } return false;\n            ')
            if loading:
                return True
            in_prog = drv.execute_script("\n                var el = document.querySelector('model-response .generating-sparkle, model-response .loading');\n                return el !== null && el.offsetParent !== null;\n            ")
            if in_prog:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

def snapshot_urls(drv):
    try:
        return set(drv.execute_script('return Array.from(document.querySelectorAll(\'img[src^="blob:"],img[src*="googleusercontent"]\')).map(i=>i.src).filter(s=>s&&s.length>10);') or [])
    except Exception:
        return set()

def _thumb_up_visible(drv):
    try:
        return drv.execute_script('\n            var icons = document.querySelectorAll(\'mat-icon[data-mat-icon-name="thumb_up"], mat-icon[fonticon="thumb_up"]\');\n            for (var i = 0; i < icons.length; i++) {\n                if (icons[i].offsetParent !== null) return true;\n            } return false;\n        ')
    except Exception:
        return False

def _send_btn_enabled(drv):
    try:
        return drv.execute_script('\n            var sels = [\'mat-icon[fonticon="arrow_upward"]\', \'mat-icon[data-mat-icon-name="arrow_upward"]\',\n                        \'mat-icon[fonticon="send"]\', \'button[aria-label="Send message"]\'];\n            for (var s = 0; s < sels.length; s++) {\n                var els = document.querySelectorAll(sels[s]);\n                for (var i = 0; i < els.length; i++) {\n                    var b = els[i].tagName === \'BUTTON\' ? els[i] : els[i].closest(\'button\');\n                    if (b && !b.disabled && b.offsetParent !== null) return true;\n                }\n            } return false;\n        ')
    except Exception:
        return False

def _is_gemini_processing(drv):
    try:
        stop = drv.execute_script('\n            var sels = [\'button[aria-label="Stop generating"]\', \'button[aria-label="Cancel"]\',\n                        \'mat-icon[fonticon="stop"]\', \'mat-icon[data-mat-icon-name="stop"]\'];\n            for (var s = 0; s < sels.length; s++) {\n                var els = document.querySelectorAll(sels[s]);\n                for (var i = 0; i < els.length; i++) {\n                    if (els[i].offsetParent !== null) return true;\n                }\n            } return false;\n        ')
        if stop:
            return True
        loading = drv.execute_script('\n            var el = document.querySelector(\'image-loading-overlay [data-test-id="image-loading-overlay"]\');\n            if (el && el.offsetParent !== null) {\n                return !el.classList.contains(\'done-generating\');\n            } return false;\n        ')
        return bool(loading)
    except Exception:
        return False

def _has_generated_image(drv, urls_before):
    try:
        blob_srcs = drv.execute_script('\n            var srcs = [];\n            var imgs = document.querySelectorAll(\'img[src^="blob:https://gemini.google.com"]\');\n            for (var i = imgs.length - 1; i >= 0; i--) {\n                var img = imgs[i]; if (!img.offsetParent) continue;\n                var src = img.getAttribute(\'src\') || \'\';\n                var tid = img.getAttribute(\'data-test-id\') || \'\';\n                if (tid.indexOf(\'uploaded-img\') !== -1 || tid === \'image-preview\') continue;\n                if (src.length > 10) srcs.push(src);\n            } return srcs;\n        ') or []
        for src in blob_srcs:
            if src not in urls_before:
                return src
    except Exception:
        pass
    for sel in ['generated-image img', 'single-image img', "img[src*='googleusercontent']", 'model-response img']:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                if not img.is_displayed():
                    continue
                src = img.get_attribute('src') or ''
                tid = img.get_attribute('data-test-id') or ''
                if len(src) < 10 or 'uploaded-img' in tid or tid == 'image-preview':
                    continue
                if src in urls_before:
                    continue
                if src.startswith('blob:https://gemini.google.com') or 'googleusercontent' in src:
                    return src
        except Exception:
            continue
    return None

def check_gemini_error(drv):
    try:
        b = drv.find_element(By.TAG_NAME, 'body').text.lower()
        u = drv.current_url.lower()
        if any((w in b for w in ['encountered an error', 'something went wrong', 'unable to complete your request'])):
            return 'error'
        if any((w in u for w in ['google.com/sorry', 'recaptcha'])):
            return 'sorry'
    except Exception:
        pass
    return None

def check_text_error(drv):
    try:
        b = drv.find_element(By.TAG_NAME, 'body').text.lower()
        if any((w in b for w in ['cannot create images of', "can't create images of", 'unable to create that image'])):
            return 'refusal'
        if any((w in b for w in ['image-generation limit', 'daily limit', 'rate limit', 'too many requests'])):
            return 'limit'
    except Exception:
        pass
    return None

def nb_check_image(drv, urls_before, chat_urls):
    rc = check_text_error(drv)
    if rc:
        return ('REFUSED' if rc == 'refusal' else 'LIMIT', None)
    ge = check_gemini_error(drv)
    if ge:
        return ('ERROR', None)
    img_src = _has_generated_image(drv, urls_before)
    if img_src and img_src not in chat_urls:
        return ('SUCCESS', img_src)
    if _thumb_up_visible(drv):
        img_src2 = _has_generated_image(drv, urls_before)
        if img_src2 and img_src2 not in chat_urls:
            return ('SUCCESS', img_src2)
        if not _is_gemini_processing(drv):
            return ('TIMEOUT', None)
    return ('WAITING', None)

def _hover_and_dl_single_click(drv, urls_before, chat_urls) -> bool:
    """
    Primary download method: hover over the generated image, click Download button.
    Returns True if download button was clicked.
    """

    def _try_hover(img):
        try:
            drv.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'});", img)
            time.sleep(0.15)
            ActionChains(drv).move_to_element(img).perform()
            time.sleep(0.2)
            for sel in ["button[data-test-id='download-generated-image-button']", "//mat-icon[@data-mat-icon-name='download']/ancestor::button", "//mat-icon[@fonticon='download']/ancestor::button", "button[aria-label*='Download']"]:
                by = By.XPATH if sel.startswith('//') else By.CSS_SELECTOR
                for btn in reversed(drv.find_elements(by, sel)):
                    if btn.is_displayed() and btn.is_enabled():
                        drv.execute_script('arguments[0].click();', btn)
                        return True
        except Exception:
            pass
        return False
    candidates = []
    seen = set()
    for sel in ['single-image img', 'generated-image img', "img[src^='blob:https://gemini.google.com']", "img[src*='googleusercontent']"]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                src = img.get_attribute('src') or ''
                tid = img.get_attribute('data-test-id') or ''
                if 'uploaded-img' in tid or tid == 'image-preview' or src in urls_before or (src in chat_urls) or (src in seen) or (len(src) < 10):
                    continue
                seen.add(src)
                candidates.append(img)
        except Exception:
            continue
    for img in reversed(candidates):
        try:
            if img.is_displayed() and _try_hover(img):
                return True
        except Exception:
            continue
    try:
        clicked = drv.execute_script('\n            var btns = document.querySelectorAll(\'button[data-test-id="download-generated-image-button"], button[aria-label*="Download"]\');\n            for (var i = btns.length - 1; i >= 0; i--) {\n                var b = btns[i];\n                if (b.offsetParent !== null && !b.disabled) {\n                    b.scrollIntoView({block:\'center\'}); b.click(); return \'OK\';\n                }\n            } return null;\n        ')
        if clicked:
            return True
    except Exception:
        pass
    return False

def _direct_fetch_cdp(drv, save_path, urls_before) -> bool:
    """
    Fallback: direct CDP memory fetch of the generated image blob.
    Used only when hover download is not available.
    """
    try:
        blob = drv.execute_script('\n            var imgs = document.querySelectorAll(\n                \'single-image img, generated-image img, img[src^="blob:https://gemini.google.com"], img[src*="googleusercontent"]\'\n            );\n            for (var i = imgs.length - 1; i >= 0; i--) {\n                var s = imgs[i].getAttribute(\'src\') || \'\';\n                var tid = imgs[i].getAttribute(\'data-test-id\') || \'\';\n                if (tid.indexOf(\'uploaded-img\') !== -1 || tid === \'image-preview\') continue;\n                if (s && s.length > 10) return s;\n            } return null;\n        ')
        if not blob or blob in urls_before:
            return False
        expr = f"""\n            (function() {{\n                var src = {json.dumps(blob)};\n                return fetch(src)\n                    .then(function(r) {{ return r.blob(); }})\n                    .then(function(b) {{\n                        return new Promise(function(resolve) {{\n                            var fr = new FileReader();\n                            fr.onloadend = function() {{ resolve(fr.result.split(',')[1]); }};\n                            fr.onerror = function() {{ resolve(null); }};\n                            fr.readAsDataURL(b);\n                        }});\n                    }}).catch(function(e) {{\n                        try {{\n                            var imgs = document.querySelectorAll('single-image img, generated-image img, img[src*="googleusercontent"]');\n                            for (var i = imgs.length - 1; i >= 0; i--) {{\n                                var img = imgs[i];\n                                if (img.offsetParent !== null && (img.naturalWidth > 100 || img.width > 100)) {{\n                                    var canvas = document.createElement('canvas');\n                                    canvas.width = img.naturalWidth;\n                                    canvas.height = img.naturalHeight;\n                                    var ctx = canvas.getContext('2d');\n                                    ctx.drawImage(img, 0, 0);\n                                    return canvas.toDataURL('image/png').split(',')[1];\n                                }}\n                            }}\n                        }} catch (ex) {{}}\n                        return null;\n                    }});\n            }})()\n        """
        res = drv.execute_cdp_cmd('Runtime.evaluate', {'expression': expr, 'awaitPromise': True, 'returnByValue': True})
        if res and 'result' in res and ('value' in res['result']) and res['result']['value']:
            b64_val = res['result']['value']
            data = base64.b64decode(b64_val)
            if len(data) > DOWNLOAD_MIN_SIZE:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                Path(save_path).write_bytes(data)
                return True
    except Exception:
        pass
    return False

def fetch_generation(gen_id):
    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        cur.execute('\n            SELECT g.id, g.user_id, g.model_id, g.catalogue_item_id, g.package_id,\n                   g.prompt, g.params, g.attempts, g.max_attempts, g.credits_cost,\n                   ci.hologram_url, ci.thumbnail_url, ci.model_id AS ci_model_id,\n                   pk.primary_outfit_name,\n                   m.image_url AS model_image_url, m.angle_image_url AS model_angle_url\n            FROM image_generations g\n            LEFT JOIN catalogue_items ci ON ci.id = g.catalogue_item_id\n            LEFT JOIN packages pk ON pk.id = COALESCE(g.package_id, ci.package_id)\n            LEFT JOIN models m ON m.id = COALESCE(g.model_id, ci.model_id)\n            WHERE g.id = %s\n            ', (gen_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()

def resolve_prompt_and_refs(gen):
    params = gen.get('params') or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            params = {}
    garment_url = params.get('garmentImage') or params.get('garmentUrl') or params.get('garment_image_url') or params.get('garmentImageUrl')
    if not garment_url and isinstance(params.get('garmentImages'), list) and params['garmentImages']:
        garment_url = params['garmentImages'][0]
    if not garment_url:
        raise ValueError(f"Generation {gen['id']}: No garment reference found in params.")
    model_img_url = params.get('modelImage') or gen.get('model_angle_url') or gen.get('model_image_url')
    holo_url = params.get('styleImage') or gen.get('hologram_url')
    garment_path = sys.modules['fashion_studio'].download_remote_image(garment_url, REFS_CACHE_DIR)
    model_path = sys.modules['fashion_studio'].download_remote_image(model_img_url, REFS_CACHE_DIR) if model_img_url else None
    holo_path = sys.modules['fashion_studio'].download_remote_image(holo_url, REFS_CACHE_DIR) if holo_url else None
    prompt = gen.get('prompt') or sys.modules['fashion_studio'].fashion_tryon_prompt(has_model=bool(model_path))
    return (prompt, garment_path, model_path, holo_path)

def record_dead_letter(gen, failed_reason, attempts_made, max_attempts, error_stack=None):
    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        summary = json.dumps({'generationId': gen['id']})
        cur.execute("\n            INSERT INTO dead_letter_jobs\n                (queue_name, job_name, generation_id, payload_summary, failed_reason,\n                 attempts_made, status, worker_id, error_stack)\n            VALUES (%s, %s, %s, %s::jsonb, %s, %s, 'open', %s, %s)\n            ", (QUEUE_NAME, 'process-generation', gen['id'], summary, failed_reason[:4000], attempts_made, WORKER_ID, (error_stack or '')[:8000]))
        conn.commit()
    finally:
        conn.close()

def ensure_chrome_driver_alive(driver):
    if driver is None:
        raise RuntimeError('Driver is None')
    try:
        driver.execute_script('return 1')
        return True
    except Exception as e:
        raise RuntimeError(f'Driver dead: {e}')

def check_chrome_driver_health(driver):
    if driver is None:
        return {'alive': False}
    try:
        driver.execute_script('return 1')
        return {'alive': True, 'window_count': len(driver.window_handles), 'current_handle': driver.current_window_handle, 'current_url': driver.current_url, 'pid': driver.service.process.pid if driver.service and driver.service.process else None}
    except Exception:
        return {'alive': False}

def configure_browser_download_events(driver):
    driver.execute_cdp_cmd('Browser.setDownloadBehavior', {'behavior': 'allowAndName', 'downloadPath': '/content/downloads/chrome_staging/global', 'eventsEnabled': True})

def create_persistent_chrome_driver():
    import undetected_chromedriver as uc
    profile_dir = Path('/content/queue_worker_bundle/queue_worker_state/chrome_profile')
    profile_dir.mkdir(parents=True, exist_ok=True)
    options = uc.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--user-data-dir={profile_dir}')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-session-crashed-bubble')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        raise RuntimeError(f'CHROME_START_FAILED: {type(e).__name__}: {e}') from e
    assert driver is not None
    assert driver.service is not None
    assert driver.window_handles
    driver.execute_script('return document.readyState')
    driver.execute_cdp_cmd('Browser.getVersion', {})
    return driver

def _fail_job(job_id, gen, reason, future, attempt):
    log(f'[{job_id}] FAILING JOB: {reason}')
    counters['failed'] += 1
    try:
        import db
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET status='FAILED', error_message=%s WHERE id=%s", (str(reason)[:255], job_id))
            conn.commit()
    except Exception as e:
        log(f'[{job_id}] DB Update failed during fail_job: {e}', file=sys.stderr)
    resolve_future_once(main_loop, future, exception=Exception(reason))
    active_downloads.pop(job_id, None)
    active_wmr.pop(job_id, None)

def upload_to_r2(file_path, object_name):
    return 'https://r2/' + object_name