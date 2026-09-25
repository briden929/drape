import argparse
import base64
import json
import os
import pickle
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
EMBEDDED_COOKIES_B64 = globals().get('EMBEDDED_COOKIES_B64')
EMBEDDED_CHROME_PROFILE_REMOTE = globals().get('EMBEDDED_CHROME_PROFILE_REMOTE')

def run_cmd(cmd, timeout=120):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None

def is_colab():
    try:
        import google.colab
        return True
    except ImportError:
        return False

class Status:

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.data = {'phase': 'starting', 'message': '', 'mode': None, 'vnc_url': None, 'cookies_file': None, 'elapsed_s': 0, 'finished': False, 'error': None, 'log': []}
        self.flush(force=True)

    def update(self, **kwargs):
        with self.lock:
            self.data.update(kwargs)
            self.data['elapsed_s'] = round(time.time() - self.start_time, 1)
            msg = kwargs.get('message')
            if msg:
                phase = self.data.get('phase')
                last = self.data['log'][-1] if self.data['log'] else None
                if not last or last.get('phase') != phase or last.get('message') != msg:
                    self.data['log'].append({'phase': phase, 'message': msg, 't': self.data['elapsed_s']})
            snapshot = dict(self.data)
        self.flush(snapshot=snapshot, force=True)
        print(f"[{snapshot['phase']}] {snapshot.get('message', '')}", flush=True)

    def flush(self, snapshot=None, force=False):
        with self.lock:
            snapshot = snapshot or dict(self.data)
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f)
        os.replace(tmp, self.path)

def ensure_deps(status, headless):
    status.update(phase='installing', message='Checking Chrome + Selenium deps...')
    try:
        import selenium
        import undetected_chromedriver
    except ImportError:
        run_cmd(f'{sys.executable} -m pip install -q selenium undetected-chromedriver webdriver-manager setuptools', timeout=180)
        if headless:
            run_cmd(f'{sys.executable} -m pip install -q pyvirtualdisplay', timeout=60)
    chrome_bin = find_chrome()
    if not chrome_bin:
        if headless:
            os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
            run_cmd('apt-get update -y', timeout=60)
            run_cmd('apt-get install -y wget xvfb x11vnc novnc websockify unzip xclip curl dbus-x11', timeout=180)
            run_cmd('wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb', timeout=90)
            run_cmd('dpkg -i /tmp/chrome.deb', timeout=60)
            run_cmd('apt-get install -f -y', timeout=90)
            chrome_bin = find_chrome()
        if not chrome_bin:
            raise RuntimeError('Google Chrome not found. On macOS, install it from https://www.google.com/chrome/ first — headless auto-install is Linux/Colab-only (uses apt).')
    return chrome_bin

def find_chrome():
    candidates = ['/usr/bin/google-chrome-stable', '/usr/bin/google-chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe', os.path.expandvars('%LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe')]
    for path in candidates:
        if os.path.exists(path):
            return path
    for name in ('google-chrome-stable', 'google-chrome', 'chrome', 'chromium', 'chrome.exe'):
        found = shutil.which(name)
        if found:
            return found
    return None

def start_display_and_vnc(status, screen_w=1920, screen_h=1080, vnc_port=5900, novnc_port=6080):
    if platform.system() != 'Linux':
        raise RuntimeError(f'Headless mode (Xvfb/x11vnc/noVNC) needs Linux/apt — this is {platform.system()}. Use --mode local on a Mac instead: Chrome opens as a real, visible window and no virtual display is needed.')
    status.update(phase='waiting_display', message='Starting virtual display + noVNC...')
    from pyvirtualdisplay import Display
    disp_obj = Display(visible=0, size=(screen_w, screen_h))
    disp_obj.start()
    os.environ['DISPLAY'] = f":{getattr(disp_obj, 'display', 99)}"
    run_cmd('pkill -f x11vnc', timeout=5)
    run_cmd('pkill -f websockify', timeout=5)
    time.sleep(0.5)
    subprocess.Popen(['x11vnc', '-display', os.environ['DISPLAY'], '-forever', '-nopw', '-shared', '-quiet', '-rfbport', str(vnc_port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    web_dir = None
    for p in ('/usr/share/novnc', '/usr/share/noVNC'):
        if os.path.isfile(os.path.join(p, 'vnc.html')):
            web_dir = p
            break
    cmd = ['websockify', '--web', web_dir, str(novnc_port), f'localhost:{vnc_port}'] if web_dir else ['websockify', str(novnc_port), f'localhost:{vnc_port}']
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    cf_path = '/usr/local/bin/cloudflared'
    if not os.path.exists(cf_path):
        run_cmd(f'wget -q -O {cf_path} https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64', timeout=90)
        run_cmd(f'chmod +x {cf_path}', timeout=5)
    if os.path.exists(cf_path):
        proc = subprocess.Popen([cf_path, 'tunnel', '--url', f'http://localhost:{novnc_port}'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        deadline = time.time() + 20
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                continue
            m = re.search('https://[a-z0-9\\-]+\\.trycloudflare\\.com', line)
            if m:
                url = f'{m.group(0)}/vnc.html?autoconnect=true&resize=scale'
                return url
    return f'http://localhost:{novnc_port}/vnc.html'

def _make_plain_selenium_driver(chrome_bin, screen_w, screen_h, prefs, profile_dir=None):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    opts = Options()
    opts.binary_location = chrome_bin
    opts.add_argument(f'--window-size={screen_w},{screen_h}')
    opts.add_argument('--start-maximized')
    opts.add_argument('--lang=en-US,en')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_experimental_option('useAutomationExtension', False)
    if profile_dir:
        opts.add_argument(f'--user-data-dir={profile_dir}')
        opts.add_argument('--profile-directory=Default')
    if prefs:
        opts.add_experimental_option('prefs', prefs)
    svc = Service(ChromeDriverManager().install())
    d = webdriver.Chrome(service=svc, options=opts)
    d.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return d

def make_driver(chrome_bin, screen_w=1920, screen_h=1080, download_dir=None, profile_dir=None):
    try:
        from selenium.webdriver.remote.remote_connection import RemoteConnection
        RemoteConnection.set_timeout(120)
    except Exception:
        pass
    prefs = None
    if download_dir:
        prefs = {'download.default_directory': os.path.abspath(download_dir), 'download.prompt_for_download': False, 'download.directory_upgrade': True, 'safebrowsing.enabled': True}
    d = None
    try:
        import undetected_chromedriver as uc
        from webdriver_manager.chrome import ChromeDriverManager
        driver_path = ChromeDriverManager().install()
        opts = uc.ChromeOptions()
        opts.binary_location = chrome_bin
        opts.add_argument(f'--window-size={screen_w},{screen_h}')
        opts.add_argument('--lang=en-US,en')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        if profile_dir:
            opts.add_argument(f'--user-data-dir={profile_dir}')
            opts.add_argument('--profile-directory=Default')
        if prefs:
            opts.add_experimental_option('prefs', prefs)
        d = uc.Chrome(options=opts, driver_executable_path=driver_path, use_subprocess=True)
        d.get('about:blank')
        print('[make_driver] using undetected-chromedriver', flush=True)
    except Exception as e:
        print(f'[make_driver] undetected-chromedriver failed ({e!r}), falling back to plain Selenium', flush=True)
        try:
            if d is not None:
                d.quit()
        except Exception:
            pass
        d = _make_plain_selenium_driver(chrome_bin, screen_w, screen_h, prefs, profile_dir)
    d.set_page_load_timeout(60)
    d.implicitly_wait(3)
    return d

def save_cookies(drv, cookies_file):
    Path(cookies_file).parent.mkdir(parents=True, exist_ok=True)
    with open(cookies_file, 'wb') as f:
        pickle.dump(drv.get_cookies(), f)

def load_cookies(drv, cookies_file):
    if not os.path.exists(cookies_file):
        return False
    try:
        with open(cookies_file, 'rb') as f:
            cookies = pickle.load(f)
        drv.get('https://www.google.com')
        time.sleep(0.5)
        for c in cookies:
            try:
                drv.add_cookie(c)
            except Exception:
                pass
        return True
    except Exception:
        return False
_PROFILE_SKIP_DIRS = {'cache', 'code cache', 'gpucache', 'shadercache', 'grshadercache', 'dawncache', 'blob_storage', 'file system', 'cachestorage', 'component_crx_cache', 'safe browsing', 'webrtc_event_logs', 'optimization_guide_prediction_models'}

def restore_chrome_profile(profile_dir, embedded_remote_path):
    if not embedded_remote_path or not os.path.exists(embedded_remote_path):
        return False
    try:
        if os.path.isdir(profile_dir) and os.listdir(profile_dir):
            return False
        os.makedirs(profile_dir, exist_ok=True)
        shutil.unpack_archive(embedded_remote_path, profile_dir, format='zip')
        return True
    except Exception:
        return False

def save_chrome_profile(profile_dir, archive_out_path):
    if not profile_dir or not os.path.isdir(profile_dir):
        return False
    try:
        import zipfile
        Path(archive_out_path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = str(archive_out_path) + '.tmp'
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(profile_dir):
                dirs[:] = [d for d in dirs if d.lower() not in _PROFILE_SKIP_DIRS]
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        zf.write(fpath, os.path.relpath(fpath, profile_dir))
                    except Exception:
                        continue
        os.replace(tmp_path, archive_out_path)
        return True
    except Exception:
        return False

def is_logged_in(drv):
    try:
        drv.get('https://myaccount.google.com/')
        time.sleep(1.5)
        url = drv.current_url
        return 'myaccount.google.com' in url and 'signin' not in url
    except Exception:
        return False
_GOOGLE_SESSION_COOKIE_NAMES = {'SID', 'HSID', 'SSID', '__Secure-1PSID', '__Secure-3PSID'}

def has_google_session_cookie(drv):
    try:
        names = {c.get('name') for c in drv.get_cookies()}
        return bool(names & _GOOGLE_SESSION_COOKIE_NAMES)
    except Exception:
        return False

def _activity_click_menu_item(drv, texts):
    from selenium.webdriver.common.by import By
    texts_l = [t.lower() for t in texts]
    try:
        for el in drv.find_elements(By.CSS_SELECTOR, "button, [role='menuitem'], [role='menuitemcheckbox']"):
            try:
                if not el.is_displayed():
                    continue
                label = (el.text or el.get_attribute('aria-label') or '').strip().lower()
                if label and any((t in label for t in texts_l)):
                    drv.execute_script('arguments[0].click();', el)
                    time.sleep(0.5)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False

def turn_off_gemini_activity(drv, status):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    try:
        status.update(message='Checking Gemini Activity setting...')
        drv.get('https://myactivity.google.com/product/gemini')
        WebDriverWait(drv, 20).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(3)
        toggle = None
        for el in drv.find_elements(By.CSS_SELECTOR, "[role='switch']"):
            if el.is_displayed():
                toggle = el
                break
        if not toggle:
            for el in drv.find_elements(By.XPATH, "//button[contains(@aria-label,'activity') or contains(@aria-label,'Keep activity')]"):
                if el.is_displayed():
                    toggle = el
                    break
        if not toggle:
            return False
        drv.execute_script("arguments[0].scrollIntoView({block:'center'});", toggle)
        time.sleep(0.5)
        try:
            toggle.click()
        except Exception:
            drv.execute_script('arguments[0].click();', toggle)
        time.sleep(1.5)
        if not _activity_click_menu_item(drv, ['turn off']):
            return False
        time.sleep(1.5)
        _activity_click_menu_item(drv, ['got it', 'pause', 'confirm', 'ok'])
        status.update(message='Gemini Activity turned off.')
        return True
    except Exception:
        return False

def handle_login(drv, status, cookies_file, login_timeout, mark_finished=True, profile_dir=None, profile_archive_out=None):
    status.update(phase='checking_cookies', message='Checking for saved cookies...')
    if load_cookies(drv, cookies_file):
        drv.refresh()
        if is_logged_in(drv):
            status.update(phase='logged_in', message='Logged in via saved cookies.', cookies_file=cookies_file, finished=mark_finished)
            return True
        drv.delete_all_cookies()
    drv.get('https://accounts.google.com/ServiceLogin')
    status.update(phase='waiting_login', message=f'Waiting for manual login (timeout {login_timeout}s)...')
    deadline = time.time() + login_timeout
    while time.time() < deadline:
        if has_google_session_cookie(drv) and is_logged_in(drv):
            save_cookies(drv, cookies_file)
            if profile_dir and profile_archive_out:
                save_chrome_profile(profile_dir, profile_archive_out)
            turn_off_gemini_activity(drv, status)
            status.update(phase='logged_in', message='Login confirmed, cookies saved.', cookies_file=cookies_file, finished=mark_finished)
            return True
        time.sleep(3)
    status.update(phase='timeout', message='Timed out waiting for login.', finished=True, error='login_timeout')
    return False
_PERSISTENT_DRIVER = globals().get('_PERSISTENT_DRIVER')
_PERSISTENT_VNC_URL = globals().get('_PERSISTENT_VNC_URL')

def main():
    parser = argparse.ArgumentParser(description='Gemini/Google login worker')
    parser.add_argument('--status-file', required=True)
    parser.add_argument('--output-dir', default='./gemini_login_session')
    parser.add_argument('--cookies-file', default=None, help='Defaults to <output-dir>/google_cookies.pkl')
    parser.add_argument('--headless', action='store_true', help='Force the Xvfb+noVNC path even off Colab (local-headless mode).')
    parser.add_argument('--login-timeout', type=int, default=900)
    parser.add_argument('--screen-width', type=int, default=1920)
    parser.add_argument('--screen-height', type=int, default=1080)
    parser.add_argument('--keep-alive', action='store_true', help="Leave the browser open (in this kernel's globals) instead of quitting it, so a later `colab exec` on the same session can reuse it for Generate without logging in again.")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    cookies_file = args.cookies_file or os.path.join(args.output_dir, 'google_cookies.pkl')
    if EMBEDDED_COOKIES_B64:
        Path(cookies_file).parent.mkdir(parents=True, exist_ok=True)
        Path(cookies_file).write_bytes(base64.b64decode(EMBEDDED_COOKIES_B64))
    profile_dir = os.path.join(args.output_dir, 'chrome_profile')
    profile_archive_out = os.path.join(args.output_dir, 'chrome_profile.zip')
    if EMBEDDED_CHROME_PROFILE_REMOTE:
        restore_chrome_profile(profile_dir, EMBEDDED_CHROME_PROFILE_REMOTE)
    status = Status(args.status_file)
    headless = args.headless or is_colab()
    mode = 'colab' if is_colab() else 'local-headless' if args.headless else 'local'
    status.update(mode=mode, message=f"Starting in '{mode}' mode.")
    try:
        chrome_bin = ensure_deps(status, headless)
        global _PERSISTENT_DRIVER, _PERSISTENT_VNC_URL
        if _PERSISTENT_DRIVER is not None:
            status.update(phase='checking_session', message='Checking existing browser session...')
            if is_logged_in(_PERSISTENT_DRIVER):
                status.update(phase='logged_in', message='Already logged in — reusing existing session.', cookies_file=cookies_file, finished=True)
                if not args.keep_alive:
                    try:
                        _PERSISTENT_DRIVER.quit()
                    except Exception:
                        pass
                    _PERSISTENT_DRIVER = None
                return
            try:
                _PERSISTENT_DRIVER.quit()
            except Exception:
                pass
            _PERSISTENT_DRIVER = None
        vnc_url = None
        if headless:
            vnc_url = start_display_and_vnc(status, args.screen_width, args.screen_height)
            _PERSISTENT_VNC_URL = vnc_url
            status.update(vnc_url=vnc_url, message='Virtual display ready — open vnc_url to log in.')
        status.update(phase='launching_browser', message=f'Launching Chrome ({chrome_bin})...')
        drv = make_driver(chrome_bin, args.screen_width, args.screen_height, args.output_dir, profile_dir)
        if args.keep_alive:
            ok = handle_login(drv, status, cookies_file, args.login_timeout, profile_dir=profile_dir, profile_archive_out=profile_archive_out)
            if ok:
                _PERSISTENT_DRIVER = drv
                status.update(message=status.data.get('message', '') + ' (browser kept open for reuse)')
            else:
                drv.quit()
            return
        try:
            handle_login(drv, status, cookies_file, args.login_timeout, profile_dir=profile_dir, profile_archive_out=profile_archive_out)
        finally:
            drv.quit()
    except Exception as e:
        status.update(phase='error', message=str(e), error=str(e), finished=True)
        raise
if __name__ == '__main__':
    main()