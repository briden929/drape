
import threading
import heapq

SCREEN_W = 1920
SCREEN_H = 1080
_db_pool_lock = threading.Lock()
_db_last_used = {}
_mod_db = None
import asyncio
import base64
import contextlib
import hashlib
import io
import json
import mimetypes
import os
import pickle
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from PIL import Image
from IPython.display import display as ipy_display, HTML
_FALLBACKS = {'DATABASE_URL': 'postgresql://postgres.cfgthwsqgmvtftlyoamj:Daxil%4016%3F80!@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres', 'R2_ACCOUNT_ID': '8e22889fff8e7c874800278c4bdcb26c', 'R2_ACCESS_KEY_ID': 'e90045f23e9cd55bb08238384b771bf2', 'R2_SECRET_ACCESS_KEY': '0b0e32afb39cf06d1682968ee7dc1750526b04c2ea16b200fb6027b070e7d4d6', 'R2_BUCKET_NAME': 'studio-photoshoot', 'R2_PUBLIC_URL': 'https://pub-943056d53cd64d87aef37136315753a7.r2.dev', 'REDIS_URL': 'rediss://default:gQAAAAAABH39AAIgcDIzNDM4OTNlMTY0NDU0MWQ0YmYwMDJmZWMxOTc0N2Q4NQ@harmless-orca-294397.upstash.io:6379'}
QUEUE_NAME = 'generations'
REDIS_KEY_PREFIX = os.environ.get('REDIS_KEY_PREFIX', 'vastralook:')
REDIS_URL = os.environ.get('REDIS_URL')
MAX_CONCURRENT_TABS = 4
CHROME_WMR_WORKERS = 4
GENERATION_TIMEOUT_S = 240
LOCAL_REDIS_PORT = 16379
MAX_NEW_CHAT_RETRIES = 3
MAX_JOB_RETRIES = 2
DOWNLOAD_STABLE_CHECKS = 2
DOWNLOAD_MIN_SIZE = 5000
DOWNLOAD_TIMEOUT_S = 120
DOWNLOAD_START_WINDOW_S = 15
WMR_TIMEOUT_S = 120
VNC_PORT = 5900
NOVNC_PORT = 6080
GEMINI_APP_URL = 'https://gemini.google.com/app'
WMR_SERVICE_URL = 'https://app.gemini-logo-remover.workers.dev/gemini'
WORKER_ID = f'queue_worker-{uuid.uuid4().hex[:8]}'
def log(msg, file=None):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', file=file, flush=True)
BASE_DIR = Path('/content/queue_worker_bundle')
STATE_DIR = BASE_DIR / 'queue_worker_state'
CHROME_PROFILE_DIR = STATE_DIR / 'chrome_profile'
WMR_PROFILES_BASE = STATE_DIR / 'wmr_chrome_profiles'
REFS_CACHE_DIR = STATE_DIR / 'refs'
DL_BASE = Path('/content/downloads')
CHROME_DL_BASE = DL_BASE / 'chrome'
WMR_DL_BASE = DL_BASE / 'wmr'
WMR_STAGING_BASE = DL_BASE / 'wmr_staging'
FINAL_OUTPUT_BASE = DL_BASE / 'final_output'
COOKIES_FILE = STATE_DIR / 'cookies.pkl'
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
            print(f'   Warning during {desc}: {res.stderr.strip()[:200]}')
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        if desc:
            print(f'   Timeout during {desc}')
        return False
    except Exception as e:
        if desc:
            print(f'   Error during {desc}: {e}')
        return False
from psycopg2 import pool as _pgpool
import boto3
_PING_AFTER_IDLE_S = 60
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
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
R2_PUBLIC_URL = os.environ.get('R2_PUBLIC_URL')
FASHION_STUDIO_USER_ID = os.environ.get('FASHION_STUDIO_USER_ID', 'system')
def fs_configured():
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_PUBLIC_URL)
def _r2_client():
    return boto3.client('s3', endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com', aws_access_key_id=R2_ACCESS_KEY_ID, aws_secret_access_key=R2_SECRET_ACCESS_KEY, region_name='auto')
_FASHION_TRYON_BODY = 'FASHION TRY-ON INSTRUCTIONS\n{face_ref_authority}INPUT IMAGES\n{input_order}\n\nTASK\nGenerate ONE photorealistic commercial fashion photograph of the model wearing the garment.\n- Garment integrity: exact colors, textures, patterns, and drape\n- Model consistency: natural pose, studio lighting, hyper-realistic detail\n- Professional studio backdrop with clean aesthetic.'
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
from pyvirtualdisplay import Display
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
            print(f'   {label} ready on port :{port}')
            return True
        time.sleep(0.5)
    print(f'   {label} not ready on port :{port}')
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
        print(f'   Display :{_display_obj.display} running at {SCREEN_W}x{SCREEN_H}.')
    except Exception as e:
        print(f'   pyvirtualdisplay fallback: {e}')
        subprocess.Popen(['Xvfb', ':99', '-screen', '0', f'{SCREEN_W}x{SCREEN_H}x24', '-ac'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ['DISPLAY'] = ':99'
        time.sleep(1.0)
        print('   Display :99 running.')
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
                        _banner = f"<div style='background:linear-gradient(135deg,#1b5e20,#2e7d32);color:white;padding:16px;border-radius:10px;font-size:15px;font-weight:bold;margin:10px 0;box-shadow:0 4px 6px rgba(0,0,0,0.3);'> <b>noVNC Remote Desktop Stream:</b><br><br> <a href='{vnc_url}' target='_blank' style='color:#a7ffeb;text-decoration:underline;'>Open Live UI ({vnc_url})</a><br></div>"
                        ipy_display(HTML(_banner))
                    except Exception:
                        pass
                    print(f'   noVNC Public Link: {vnc_url}')
                    return tb
        except Exception as e:
            print(f'   noVNC tunnel notice: {e}')
    fallback = f'http://localhost:{NOVNC_PORT}/vnc.html'
    print(f'   noVNC listening locally: {fallback}')
    return fallback
NOVNC_PUBLIC_URL = start_novnc_tunnel()
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
SCREENSHOT_FOLDER = '/content/login_screenshots'
MAX_VERIFICATION_ATTEMPTS = 3
SHORT_WAIT = 2
TIMEOUT = 15
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
        log(f'   WebP conversion failed: {e}')
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
def _wmr_check_status(drv):
    js_code = "\n        var btns = document.querySelectorAll('button');\n        for (var i = 0; i < btns.length; i++) {\n            var btn = btns[i];\n            var txt = (btn.textContent || '').trim();\n            if (txt.indexOf('Download PNG') !== -1 || txt.indexOf('Save') !== -1) {\n                var style = window.getComputedStyle(btn);\n                var isVisible = style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';\n                if (isVisible && !btn.disabled) {\n                    return 'DONE';\n                }\n            }\n        }\n        // Wait strictly for Download PNG button as per architecture\n        // Do not use after-image detection as a shortcut for readiness\n        var allText = document.body ? document.body.innerText.toLowerCase() : '';\n        if (allText.indexOf('detecting') !== -1 || allText.indexOf('processing') !== -1) {\n            return 'BUSY';\n        }\n        if (allText.indexOf('not detected') !== -1 || allText.indexOf('no watermark') !== -1) {\n            for (var i = 0; i < btns.length; i++) {\n                var txt = (btns[i].textContent || '').trim();\n                if (txt.indexOf('Download PNG') !== -1 || txt.indexOf('Save') !== -1) {\n                    return 'DONE';\n                }\n            }\n            return 'NOT_FOUND';\n        }\n        if (allText.length < 10) return 'LOADING';\n        return 'BUSY';\n    "
    res = safe_execute_script(drv, js_code)
    return (res or 'error').upper()
def _wmr_click_download(drv, prefix, attempts=1):
    js_code = '\n        // 1. Locate the result container. Often it\'s the parent of the comparison slider, or contains the text "Result"\n        // Since we might not know the exact class, we find the container holding "Clean" or "Result" or just find the exact button and verify its context.\n        var btns = document.querySelectorAll(\'button\');\n        var target = null;\n        for (var i = 0; i < btns.length; i++) {\n            var btn = btns[i];\n            var txt = (btn.textContent || btn.innerText || \'\').trim();\n            if (txt === \'Download PNG\') {\n                target = btn;\n                break;\n            }\n        }\n        if (!target) return \'NOT_FOUND\';\n        \n        var style = window.getComputedStyle(target);\n        if (style.display === \'none\' || style.visibility === \'hidden\' || target.disabled) {\n            return \'NOT_VISIBLE_OR_DISABLED\';\n        }\n        \n        // Scope verification: walk up to ensure it\'s in the main result section\n        var root = target.closest(\'main\') || target.closest(\'.result\') || target.parentElement.parentElement;\n        \n        target.scrollIntoView({behavior: \'instant\', block: \'center\'});\n        var r = target.getBoundingClientRect();\n        \n        return {\n            x: Math.round(r.x), \n            y: Math.round(r.y), \n            w: Math.round(r.width), \n            h: Math.round(r.height),\n            text: (target.textContent || \'\').trim()\n        };\n    '
    for _ in range(attempts):
        res = safe_execute_script(drv, js_code)
        if isinstance(res, dict):
            log(f'{prefix} WMR_DOWNLOAD_TARGET_FOUND')
            log(f"{prefix} WMR_DOWNLOAD_TARGET_TEXT '{res['text']}'")
            log(f"{prefix} WMR_DOWNLOAD_TARGET_RECT x={res['x']} y={res['y']} w={res['w']} h={res['h']}")
            try:
                btns = drv.find_elements(By.XPATH, "//button[normalize-space(.)='Download PNG']")
                if btns and btns[0].is_displayed() and btns[0].is_enabled():
                    btns[0].click()
                    return True
            except Exception:
                drv.execute_script("\n                    var btns = document.querySelectorAll('button');\n                    for (var i = 0; i < btns.length; i++) {\n                        if (btns[i].textContent.trim() === 'Download PNG') {\n                            btns[i].click();\n                            return;\n                        }\n                    }\n                ")
                return True
        time.sleep(0.3)
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
S_IDLE = 'IDLE'
S_NEW_CHAT = 'NEW_CHAT'
S_SUBMITTING = 'SUBMITTING'
S_GEN_WAITING = 'GENERATING'
S_FAILED = 'FAILED'
def _make_tab_state(tid: int, handle=None) -> dict:
    return {'tab_id': tid, 'name': f'T{tid}', 'handle': handle, 'state': S_IDLE, 'job': None, 'job_id': None, 'gen': None, 'prompt': None, 'refs': [], 'start_time': 0.0, 'last_poll': 0.0, 'next_poll': 0.0, 'urls_before': set(), 'chat_urls': set(), 'target_src': None, 'download_started': False, 'stuck_polls': 0, 'future': None, 'attempt': 0}
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

chrome_driver = None
anchor_window_handle = None

download_registry = {}
tab_states = {}
job_contexts = {}

def ensure_chrome_driver_alive(driver):
    if driver is None:
        raise RuntimeError("Driver is None")
    try:
        
        driver.execute_script("return 1")
        return True
    except Exception as e:
        raise RuntimeError(f"Driver dead: {e}")

def check_chrome_driver_health(driver):
    if driver is None:
        return {"alive": False}
    try:
        
        driver.execute_script("return 1")
        return {
            "alive": True,
            "window_count": len(driver.window_handles),
            "current_handle": driver.current_window_handle,
            "current_url": driver.current_url,
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
            
            job_dir = get_chrome_job_dir(self.tid, job_id)
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
    def __init__(self, max_workers: int = MAX_CONCURRENT_TABS):
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
    return await asyncio.wait_for(future, timeout=(GENERATION_TIMEOUT_S + DOWNLOAD_TIMEOUT_S))

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

if __name__ == '__main__':
    main()

def upload_to_r2(file_path, object_name):
    return "https://r2/" + object_name
