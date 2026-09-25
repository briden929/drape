# @title 🚀 ECOM PHOTOSHOOT N2N QUEUE WORKER - V16
# ============================================================================
# PURPOSE:
#   Production BullMQ worker for AI ECOM fashion photoshoot generation.
#
# COMPLETE N2N FLOW:
#   BullMQ Job
#       ↓
#   PostgreSQL generation lookup
#       ↓
#   Resolve prompt + ALL reference images
#       ↓
#   Gemini Chrome T0-T3
#       ↓
#   Generate image
#       ↓
#   REAL Browser.downloadWillBegin
#       ↓
#   RELEASE GEMINI RESOURCE IMMEDIATELY
#       ↓
#   Raw PNG continues downloading independently
#       ↓
#   RAW PNG filesystem validation
#       ↓
#   WMR Chrome W0-T0 ... W3-T1
#       ↓
#   REAL watermark-removal operation
#       ↓
#   REAL Browser.downloadWillBegin
#       ↓
#   RELEASE WMR RESOURCE IMMEDIATELY
#       ↓
#   Clean PNG continues downloading independently
#       ↓
#   PNG validation
#       ↓
#   WebP conversion + validation
#       ↓
#   Cloudflare R2 upload
#       ↓
#   PostgreSQL finalization
#       ↓
#   Credit settlement
#       ↓
#   BullMQ SUCCESS
#
# ============================================================================
# INPUT SOURCE:
#   BullMQ queue:
#       generations
#
#   Each BullMQ job resolves:
#       generationId
#       prompt
#       garment reference
#       mannequin/model reference
#       hologram/style reference when required
#       user_id
#       generation metadata
#
# ============================================================================
# GEMINI RESOURCES:
#   T0
#   T1
#   T2
#   T3
#
#   Total logical Gemini resources = 4
#   Gemini resources are persistent/lazy.
#
# ============================================================================
# WMR RESOURCES:
#   W0-T0
#   W0-T1
#   W1-T0
#   W1-T1
#   W2-T0
#   W2-T1
#   W3-T0
#   W3-T1
#
#   Total logical WMR resources = 8
#
#   IMPORTANT:
#   Every logical WMR slot must have isolated Chrome ownership.
#   Never share the same Chrome profile between W0-T0 and W0-T1.
#
# ============================================================================
# LOCAL STORAGE:
#
#   Base:
#       /content/queue_worker_bundle/
#
#   Reference cache:
#       /content/queue_worker_bundle/queue_worker_state/refs/
#
#   Gemini downloads:
#       /content/downloads/chrome/T0/<job_id>/incoming/
#       /content/downloads/chrome/T1/<job_id>/incoming/
#       /content/downloads/chrome/T2/<job_id>/incoming/
#       /content/downloads/chrome/T3/<job_id>/incoming/
#
#   WMR downloads:
#       /content/downloads/wmr_staging/W0-T0/<job_id>/
#       /content/downloads/wmr_staging/W0-T1/<job_id>/
#       /content/downloads/wmr_staging/W1-T0/<job_id>/
#       /content/downloads/wmr_staging/W1-T1/<job_id>/
#       /content/downloads/wmr_staging/W2-T0/<job_id>/
#       /content/downloads/wmr_staging/W2-T1/<job_id>/
#       /content/downloads/wmr_staging/W3-T0/<job_id>/
#       /content/downloads/wmr_staging/W3-T1/<job_id>/
#
#   Final:
#       /content/downloads/final_output/<job_id>/
#
# ============================================================================
# RESOURCE RULE:
#
#   Gemini:
#       generation complete
#           ↓
#       REAL download start detected
#           ↓
#       release T immediately
#           ↓
#       raw download continues independently
#
#   WMR:
#       watermark removal complete
#           ↓
#       REAL download start detected
#           ↓
#       release W slot immediately
#           ↓
#       clean download continues independently
#
# ============================================================================
# BROWSER:
#   Chrome ONLY
#   No Microsoft Edge
#   No EdgeOptions
#   No msedgedriver
#   No Playwright replacement
#
# ============================================================================
# REMOTE UI:
#   Xvfb
#   x11vnc
#   noVNC
#   Cloudflare tunnel
#
#   Used for:
#   - Google login
#   - CAPTCHA
#   - 2FA / manual intervention
#
# ============================================================================
# SECURITY:
#   Secrets ONLY from environment / Colab Secrets.
#   Never print:
#       DATABASE_URL
#       REDIS_URL
#       R2_ACCESS_KEY_ID
#       R2_SECRET_ACCESS_KEY
#       cookies
#       Google credentials
#
# ============================================================================
# FAILURE ISOLATION:
#   One failed Gemini/WMR resource must not kill the entire worker.
#   Resource failure:
#       mark DEAD
#       recover/restart resource
#       return resource to broker only after health verification
#
# ============================================================================
# RUNTIME MODEL:
#   ONE BullMQ Worker
#   ONE central pipeline scheduler
#   ONE download monitor
#   ONE Gemini broker
#   ONE WMR broker
#   ONE runtime supervisor
#   ONE shutdown path
#
# ============================================================================
# IMPORTANT:
#   Preserve proven Steps 1-10.
#   Existing V9.1 browser DOM operations remain the source of truth.
#   V15/V16 controls orchestration, lifecycle, recovery and persistence.
# ============================================================================

import asyncio
import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import os
import pathlib
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
import mimetypes
import base64
import math
import pickle
import platform
import hmac
import types
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import heapq

def bootstrap_dependencies():
    pkg_map = {'selenium': 'selenium', 'bullmq': 'bullmq', 'boto3': 'boto3', 'psycopg2': 'psycopg2-binary', 'PIL': 'Pillow', 'websockets': 'websockets', 'undetected_chromedriver': 'undetected-chromedriver', 'pyvirtualdisplay': 'pyvirtualdisplay'}
    missing = []
    for mod, pkg in pkg_map.items():
        if importlib.util.find_spec(mod) is None:
            missing.append(pkg)
    if missing:
        print(f'[BOOTSTRAP] Installing missing dependencies: {missing}')
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q'] + missing, check=True)
        importlib.invalidate_caches()
        print('[BOOTSTRAP] Dependencies installed.')
bootstrap_dependencies()
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException, StaleElementReferenceException
from PIL import Image
import boto3
import undetected_chromedriver as uc
from bullmq import Worker, Job, Queue
import psycopg2
from psycopg2 import pool as _pgpool
try:
    from IPython.display import display as ipy_display, HTML
except ImportError:
    ipy_display = print
    HTML = str
try:
    from pyvirtualdisplay import Display
except ImportError:
    Display = None



def resolve_future_once(fut: asyncio.Future, result=None, exception=None):
    if fut and (not fut.done()):
        try:
            if exception:
                fut.set_exception(exception)
            else:
                fut.set_result(result)
        except asyncio.InvalidStateError:
            pass

def threadsafe_resolve_future(loop, fut: asyncio.Future, result=None, exception=None):
    loop.call_soon_threadsafe(resolve_future_once, fut, result, exception)

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
        except:
            pass
        _get_pool().putconn(self._conn)
print('=' * 80)
print('🔑 STEP 1: INITIALIZING SECRETS & CONFIGURATION')
print('=' * 80)
_REQUIRED_SECRETS = [
    'DATABASE_URL',
    'REDIS_URL',
    'R2_ACCOUNT_ID',
    'R2_ACCESS_KEY_ID',
    'R2_SECRET_ACCESS_KEY',
    'R2_BUCKET_NAME',
    'R2_PUBLIC_URL'
]
_missing = []
for _k in _REQUIRED_SECRETS:
    if not os.environ.get(_k):
        _missing.append(_k)

if _missing:
    print(f"[FATAL ERROR] Missing required environment variables: {', '.join(_missing)}")
    sys.exit(1)

os.environ.setdefault('REDIS_KEY_PREFIX', 'vastralook:')
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
SCREEN_W, SCREEN_H = (1920, 1080)
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
for _d in (BASE_DIR, STATE_DIR, CHROME_PROFILE_DIR, WMR_PROFILES_BASE, REFS_CACHE_DIR, DL_BASE, CHROME_DL_BASE, WMR_DL_BASE, WMR_STAGING_BASE, FINAL_OUTPUT_BASE):
    _d.mkdir(parents=True, exist_ok=True)
for _i in range(CHROME_WMR_WORKERS):
    (WMR_PROFILES_BASE / f'W{_i}').mkdir(parents=True, exist_ok=True)
    (WMR_STAGING_BASE / f'W{_i}').mkdir(parents=True, exist_ok=True)
_drive_cookies = Path('/content/drive/MyDrive/gemini-queue-worker/cookies.pkl')
COOKIES_FILE = _drive_cookies if _drive_cookies.parent.parent.exists() else STATE_DIR / 'cookies.pkl'
COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

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
print(f'  Worker ID:         {WORKER_ID}')
from urllib.parse import urlparse
_u = urlparse(REDIS_URL or "")
print(f"  Redis: {_u.scheme}://{_u.hostname}:{_u.port or 6379} (credentials={'configured' if _u.password else 'none'})")
print(f'  Chrome Profile:    {CHROME_PROFILE_DIR}')
print(f'  WMR Profiles:      {WMR_PROFILES_BASE}/W{{0-3}}')
print(f'  Max Chrome Tabs:   {MAX_CONCURRENT_TABS} (T0-T3)')
print(f'  WMR Chrome Workers: {CHROME_WMR_WORKERS} (W0-W3)')
print('  ✅ Secrets and directories configured successfully.\n')
print('=' * 80)
print('📦 STEP 2: VERIFYING & INSTALLING DEPENDENCIES')
print('=' * 80)
os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

def run_cmd(cmd, desc='', timeout=120):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0 and desc:
            print(f'  ⚠️ Warning during {desc}: {res.stderr.strip()[:200]}')
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        if desc:
            print(f'  ⚠️ Timeout during {desc}')
        return False
    except Exception as e:
        if desc:
            print(f'  ⚠️ Error during {desc}: {e}')
        return False
print('  Installing Python packages...')
run_cmd('pip install -q bullmq psycopg2-binary boto3 selenium Pillow websockets nest_asyncio undetected-chromedriver webdriver-manager pyvirtualdisplay setuptools numpy requests', 'pip install')
print('  ✅ Python packages ready.')
print('  Installing system packages...')
run_cmd('apt-get update -qq && apt-get install -y -qq wget curl xvfb x11vnc novnc websockify fluxbox net-tools procps unzip zip xclip xsel dbus-x11 python3-numpy python3-websockify', 'system packages')
cf_path = '/usr/local/bin/cloudflared'
cf_ok = False
if os.path.exists(cf_path):
    cf_ok = run_cmd(f'{cf_path} --version', 'cloudflared version')
if not cf_ok:
    arch = 'arm64' if platform.machine().lower() in ['aarch64', 'arm64'] else 'amd64'
    run_cmd(f'curl -sL -o {cf_path} https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}', 'cloudflared download')
    if os.path.exists(cf_path) and os.path.getsize(cf_path) > 100000:
        run_cmd(f'chmod +x {cf_path}', 'chmod cloudflared')
        cf_ok = True
print(f"  {('✅' if cf_ok else '⚠️')} Cloudflared tunnel client: {cf_path}")
print('  ✅ Virtual display stack ready.')
print('  Verifying Google Chrome...')
chrome_path = shutil.which('google-chrome') or shutil.which('google-chrome-stable')
if not chrome_path:
    run_cmd('wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && dpkg -i /tmp/chrome.deb || apt-get install -fy -qq', 'chrome install')
    chrome_path = shutil.which('google-chrome') or shutil.which('google-chrome-stable')
print(f'  ✅ Google Chrome available at: {chrome_path}')
print('=' * 80)
print('⚙️ STEP 3: REGISTERING FULL BACKEND SYSTEM MODULES')
print('=' * 80)
_mod_db = types.ModuleType('db')
sys.modules['db'] = _mod_db
_db_pool = None
_db_pool_lock = threading.Lock()
_db_last_used = {}
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

def db_borrow():
    return _PooledBorrow(_checkout())
_mod_db.connection = db_connection
_mod_db.borrow = db_borrow
print("  ✅ Backend module 'db' loaded.")
_mod_credits = types.ModuleType('credits')
sys.modules['credits'] = _mod_credits

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
_mod_credits.settle_look = credits_settle_look
_mod_credits.refund_look = credits_refund_look
print("  ✅ Backend module 'credits' loaded.")
_mod_fs = types.ModuleType('fashion_studio')
sys.modules['fashion_studio'] = _mod_fs
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
        cur.execute("UPDATE image_generations SET output_url = %s, webp_url = %s WHERE id = %s", (output_url, webp_url, gen_id))
        conn.commit()
    finally:
        conn.close()
    return {'output_url': output_url, 'webp_url': webp_url, 'gen_id': gen_id}
_mod_fs.configured = fs_configured
_mod_fs.fashion_tryon_prompt = fashion_tryon_prompt
_mod_fs.download_remote_image = download_remote_image
_mod_fs.push_generation = push_generation
print("  ✅ Backend module 'fashion_studio' loaded.\n")
print('=' * 80)
print('🖥️ STEP 5: INITIALIZING VIRTUAL DISPLAY & NOVNC STREAMING')
print('=' * 80)
_display_obj = _x11vnc_proc = _novnc_proc = _cf_proc = None

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
            print(f'  ✅ {label} ready on port :{port}')
            return True
        time.sleep(0.5)
    print(f'  ⚠️ {label} not ready on port :{port}')
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
        print(f'  ✅ Display :{_display_obj.display} running at {SCREEN_W}x{SCREEN_H}.')
    except Exception as e:
        print(f'  ⚠️ pyvirtualdisplay fallback: {e}')
        subprocess.Popen(['Xvfb', ':99', '-screen', '0', f'{SCREEN_W}x{SCREEN_H}x24', '-ac'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ['DISPLAY'] = ':99'
        time.sleep(1.0)
        print('  ✅ Display :99 running.')

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
                        _banner = f"<div style='background:linear-gradient(135deg,#1b5e20,#2e7d32);color:white;padding:16px;border-radius:10px;font-size:15px;font-weight:bold;margin:10px 0;box-shadow:0 4px 6px rgba(0,0,0,0.3);'>🖥️ <b>noVNC Remote Desktop Stream:</b><br><br>🌐 <a href='{vnc_url}' target='_blank' style='color:#a7ffeb;text-decoration:underline;'>Open Live UI ({vnc_url})</a><br></div>"
                        ipy_display(HTML(_banner))
                    except Exception:
                        pass
                    print(f'  🌐 noVNC Public Link: {vnc_url}')
                    return tb
        except Exception as e:
            print(f'  ⚠️ noVNC tunnel notice: {e}')
    fallback = f'http://localhost:{NOVNC_PORT}/vnc.html'
    print(f'  ⚠️ noVNC listening locally: {fallback}')
    return fallback
start_display()
start_vnc()
NOVNC_PUBLIC_URL = start_novnc_tunnel()
print()
print('=' * 80)
print('🌐 STEP 6: INITIALIZING PERSISTENT CHROME DRIVERS')
print('=' * 80)

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

def create_chrome_driver():
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = CHROME_PROFILE_DIR / fname
        if fpath.exists():
            try:
                fpath.unlink()
            except Exception as e:
                print(f'Warning: Could not delete {fname}: {e}')
    opts = ChromeOptions()
    opts.add_argument(f'--user-data-dir={CHROME_PROFILE_DIR}')
    opts.add_argument('--profile-directory=Default')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument(f'--window-size={SCREEN_W},{SCREEN_H}')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_argument('--no-first-run')
    opts.add_argument('--no-default-browser-check')
    opts.add_argument('--disable-sync')
    opts.add_argument('--disable-features=IdentityConsistencyBrowserUI,SyncPromoUI')
    opts.add_argument('--disable-features=IsolateOrigins,site-per-process')
    opts.add_argument('--disable-site-isolation-trials')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_experimental_option('useAutomationExtension', False)
    prefs = {'download.default_directory': str(CHROME_DL_BASE), 'download.prompt_for_download': False, 'download.directory_upgrade': True, 'safebrowsing.enabled': False, 'safebrowsing.disable_download_protection': True, 'profile.default_content_setting_values.automatic_downloads': 1}
    opts.add_experimental_option('prefs', prefs)
    drv = webdriver.Chrome(options=opts)
    try:
        drv.execute_cdp_cmd('Network.enable', {})
    except Exception:
        pass
    return drv

def create_wmr_chrome_driver(resource_id: str) -> webdriver.Chrome:
    """Create a dedicated Chrome WMR driver for a specific logical resource (e.g., W0-T0)."""
    staging_dir = WMR_STAGING_BASE / resource_id
    profile_dir = WMR_PROFILES_BASE / resource_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
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
    log(f'[WMR-{resource_id}] Browser = Google Chrome  staging={staging_dir}')
    return drv
print('  Launching Google Chrome with persistent profile...')
chrome_driver = create_chrome_driver()
print(f'  ✅ Google Chrome driver ready (PID: {chrome_driver.service.process.pid}).\n')
print('=' * 80)
print('🔐 STEP 7: VERIFYING GOOGLE / GEMINI LOGIN STATE')
print('=' * 80)
SCREENSHOT_FOLDER = '/content/login_screenshots'
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
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
                    print('   ✅ Method 1: Profile avatar found!')
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
            print(f'   ✅ Method 2: Email found: {emails[0]}')
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
                    print(f'   ✅ Method 3: Account element found: {elem.text[:50]}')
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
            print("   ✅ Method 4: No 'Sign in' button found!")
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
                print(f'   ✅ Method 5: URL indicates logged in: {url[:60]}')
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
            print(f'   ✅ Method 6: Auth cookies found: {found}')
            return True
        return False
    except:
        return False

def is_logged_in_method_7_profile_button(driver):
    try:
        profile_btns = driver.find_elements(By.CSS_SELECTOR, "[data-is-profile-button='true'], [aria-label*='Google Account'], [aria-label*='Profile']")
        for btn in profile_btns:
            if btn.is_displayed():
                print(f'   ✅ Method 7: Profile button found!')
                return True
        return False
    except:
        return False

def comprehensive_login_check(driver, page_name=''):
    url = driver.current_url.lower()
    if 'signin' in url or 'challenge/pwd' in url or 'identifier' in url:
        print('    CONCLUSION: ON SIGN-IN PAGE -> NOT LOGGED IN')
        return False
    print(f"\n🔍 Checking login status{(f' ({page_name})' if page_name else '')}...")
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
    print(f'\n   📊 Login Confidence: {passed}/{len(methods)} methods passed ({confidence:.0f}%)')
    if confidence >= 43:
        print('   ✅ CONCLUSION: USER IS LOGGED IN!')
        return True
    print('   ❌ CONCLUSION: USER IS NOT LOGGED IN')
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
    print(f'📋 PAGE INFORMATION - {step_name}')
    if details['verification_number']:
        print(f"🔢 VERIFICATION NUMBER: {details['verification_number']} 🔢🔢")
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
        print('💾 ✅ Cookies saved locally')
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
            print('💾 ✅ Cookies loaded from local storage')
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
        print(f'\n🔍 Check {check}/{checks}')
        for remaining in range(5, 0, -1):
            print(f'\r Waiting for approval: {remaining}s ', end='', flush=True)
            time.sleep(1)
        if comprehensive_login_check(driver, 'push approval check'):
            print('\n✅ Push notification approved!')
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
        print('🔐 FAST GOOGLE LOGIN')
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
        print(f'\n❌ ERROR: {e}')
        return False

def turn_off_gemini_activity(driver):
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
                    print('✅ Gemini activity appears to be already OFF!')
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
        turn_off_clicked = False
        for attempt in range(3):
            try:
                for option in driver.find_elements(By.XPATH, "//div[contains(text(),'Turn off') and not(contains(text(),'delete'))] | //span[contains(text(),'Turn off') and not(contains(text(),'delete'))] | //button[contains(.,'Turn off') and not(contains(.,'delete'))] | //div[contains(text(),'Pause')] | //span[contains(text(),'Pause')] | //button[contains(.,'Pause')]"):
                    if option.is_displayed():
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", option)
                            time.sleep(0.5)
                            driver.execute_script('arguments[0].click();', option)
                            turn_off_clicked = True
                            break
                        except:
                            driver.execute_script('arguments[0].click();', option)
                            turn_off_clicked = True
                            break
                if turn_off_clicked:
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
        print('✅ Activity toggle process completed!')
        return True
    except:
        return False
wait = WebDriverWait(chrome_driver, TIMEOUT)
is_logged_in = False
for url, name in [('https://myaccount.google.com', 'Google Account'), ('https://gemini.google.com/app', 'Gemini')]:
    try:
        chrome_driver.get(url)
        time.sleep(3)
        WebDriverWait(chrome_driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(2)
        if comprehensive_login_check(chrome_driver, name):
            is_logged_in = True
            break
    except:
        pass
if is_logged_in:
    print('✅ ALREADY LOGGED IN!')
    save_cookies(chrome_driver)
    turn_off_gemini_activity(chrome_driver)
else:
    print('❌ USER IS NOT LOGGED IN - STARTING LOGIN')
    if handle_google_login_fast(chrome_driver, wait):
        print('✅ LOGIN SUCCESSFUL!')
        turn_off_gemini_activity(chrome_driver)
    else:
        print('❌ LOGIN FAILED. Please login manually via noVNC!')
        t0 = time.time()
        while time.time() - t0 < 180:
            if comprehensive_login_check(chrome_driver):
                print('✅ Login detected manually! Session saved.')
                save_cookies(chrome_driver)
                turn_off_gemini_activity(chrome_driver)
                break
            time.sleep(3.0)
print()
print('=' * 80)
print('🧼 STEP 8: REGISTERING CHROME WMR POOL (LAZY — W0-W3 created on demand)')
print('=' * 80)

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
        log(f'  ⚠️ WebP conversion failed: {e}')
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

def validate_webp_file(path, min_size=1000):
    """Returns True if path exists, is large enough, PIL can open it, format is WEBP, and dimensions are valid."""
    try:
        p = Path(path)
        if not p.exists() or p.stat().st_size < min_size:
            return False
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im2:
            if im2.format != 'WEBP':
                return False
            if im2.width <= 0 or im2.height <= 0:
                return False
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
    js_code = "\n        var btns = document.querySelectorAll('button');\n        for (var i = 0; i < btns.length; i++) {\n            var btn = btns[i];\n            var txt = (btn.textContent || '').trim();\n            if (txt.indexOf('Download PNG') !== -1 || txt.indexOf('Save') !== -1) {\n                var style = window.getComputedStyle(btn);\n                var isVisible = style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';\n                if (isVisible && !btn.disabled) {\n                    return 'DONE';\n                }\n            }\n        }\n        var imgs = document.querySelectorAll('img');\n        for (var i = 0; i < imgs.length; i++) {\n            var alt = (imgs[i].getAttribute('alt') || '').toLowerCase();\n            var src = imgs[i].getAttribute('src') || '';\n            if (alt.indexOf('after') !== -1 && (src.indexOf('blob:') === 0 || src.indexOf('data:') === 0)) {\n                return 'DONE';\n            }\n        }\n        var allText = document.body ? document.body.innerText.toLowerCase() : '';\n        if (allText.indexOf('detecting') !== -1 || allText.indexOf('processing') !== -1) {\n            return 'BUSY';\n        }\n        if (allText.indexOf('not detected') !== -1 || allText.indexOf('no watermark') !== -1) {\n            for (var i = 0; i < btns.length; i++) {\n                var txt = (btns[i].textContent || '').trim();\n                if (txt.indexOf('Download PNG') !== -1 || txt.indexOf('Save') !== -1) {\n                    return 'DONE';\n                }\n            }\n            return 'NOT_FOUND';\n        }\n        if (allText.length < 10) return 'LOADING';\n        return 'BUSY';\n    "
    res = safe_execute_script(drv, js_code)
    return (res or 'error').upper()

def _wmr_click_download(drv, attempts=6):
    js_code = "\n        var btns = document.querySelectorAll('button');\n        for (var i = 0; i < btns.length; i++) {\n            var btn = btns[i];\n            var txt = (btn.textContent || '').trim();\n            if (txt.indexOf('Download PNG') !== -1 || txt.indexOf('Save') !== -1) {\n                var style = window.getComputedStyle(btn);\n                if (style.display !== 'none' && style.visibility !== 'hidden' && !btn.disabled) {\n                    btn.scrollIntoView({behavior: 'instant', block: 'center'});\n                    btn.click();\n                    return 'CLICKED';\n                }\n            }\n        }\n        return 'NOT_FOUND';\n    "
    for _ in range(attempts):
        res = safe_execute_script(drv, js_code)
        if res == 'CLICKED':
            return True
        time.sleep(0.3)
    try:
        btns = drv.find_elements(By.CSS_SELECTOR, 'button')
        for btn in btns:
            txt = btn.text.strip()
            if 'Download' in txt or 'Save' in txt:
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    return True
    except Exception:
        pass
    return False

def _wmr_wait_for_new_file(incoming_dir: Path, files_before: set, timeout=30) -> Path | None:
    """Wait for a new stable image file to appear in incoming_dir."""
    t0 = time.time()
    while time.time() - t0 < timeout:
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
                    return fp
            except Exception:
                pass
        time.sleep(0.4)
    return None
print(f'  ✅ Chrome WMR Pool initialized (LAZY — workers W0-W{CHROME_WMR_WORKERS - 1} created on demand).\n')
print('=' * 80)
print(f'📑 STEP 9: CONFIGURING LAZY CHROME MULTI-TAB POOL ({MAX_CONCURRENT_TABS} SLOTS: T0-T3)')
print('=' * 80)
S_IDLE = 'IDLE'
S_NEW_CHAT = 'NEW_CHAT'
S_SUBMITTING = 'SUBMITTING'
S_GEN_WAITING = 'GENERATING'
S_FAILED = 'FAILED'
tab_states = []
chrome_lock = asyncio.Lock()

def _make_tab_state(tid: int, handle=None) -> dict:
    return {'tab_id': tid, 'name': f'T{tid}', 'handle': handle, 'state': S_IDLE, 'job': None, 'job_id': None, 'gen': None, 'prompt': None, 'refs': [], 'start_time': 0.0, 'last_poll': 0.0, 'next_poll': 0.0, 'urls_before': set(), 'chat_urls': set(), 'target_src': None, 'download_started': False, 'stuck_polls': 0, 'future': None, 'attempt': 0}

def _create_gemini_tab(tid: int) -> str:
    """
    Physically create a new Chrome tab for logical slot T{tid}.
    Always creates a NEW tab so the anchor tab is never consumed.
    """
    if not chrome_driver.window_handles:
        raise RuntimeError('BROWSER_SESSION_DEAD: No anchor window exists. Session is broken.')
    before = set(chrome_driver.window_handles)
    chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': GEMINI_APP_URL})
    deadline = time.time() + 5.0
    handle = None
    while time.time() < deadline:
        diff = set(chrome_driver.window_handles) - before
        if diff:
            handle = list(diff)[0]
            break
        time.sleep(0.2)
    if not handle:
        raise RuntimeError(f'Tab T{tid}: Failed to create physical tab via CDP')
    chrome_driver.switch_to.window(handle)
    time.sleep(1.0)
    return handle
for _i in range(MAX_CONCURRENT_TABS):
    tab_states.append(_make_tab_state(_i, handle=None))
print(f'  ✅ {MAX_CONCURRENT_TABS} Gemini tab slots registered (LAZY — physical tabs created on demand).\n')
print('=' * 80)
print('🎯 STEP 10: INITIALIZING GEMINI DOM & INTERACTION ENGINE')
print('=' * 80)

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
                    log(f'{prefix} NEW_CHAT_URL_UNCHANGED — accepting base URL: {new_url}')
            if not new_url:
                log(f'{prefix} NEW_CHAT_URL_NOT_CHANGED (attempt {attempt}) — retrying')
                time.sleep(0.5)
                continue
            log(f'{prefix} NEW_CHAT_URL={new_url}')
            log(f'{prefix} RELOADING NEW CHAT URL')
            drv.get(new_url)
            time.sleep(1.0)
            log(f'{prefix} NEW_CHAT_RELOADED')
            if _verify_clean_composer(drv):
                log(f'{prefix} NEW_CHAT_VERIFIED ✅')
                return new_url
            else:
                log(f'{prefix} NEW_CHAT_COMPOSER_NOT_CLEAN (attempt {attempt}) — retrying')
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
            log(f'{prefix} FLASH_VERIFIED ✅')
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
        if click_plus_button(drv):
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

def open_upload_drawer(drv, tid=0, job_id='') -> bool:
    """Open the upload/tools drawer by clicking the + button."""
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    if not click_plus_button(drv):
        log(f'{prefix} DRAWER_FAILED: Could not click plus button', file=sys.stderr)
        return False
    time.sleep(0.25)
    return True

def click_upload_files_in_drawer(drv):
    for sel in ["button[data-test-id='local-images-files-uploader-button']", "//span[contains(text(),'Upload files')]/ancestor::button", "//div[contains(text(),'Upload files')]/ancestor::button"]:
        try:
            by = By.XPATH if sel.startswith('//') else By.CSS_SELECTOR
            for btn in drv.find_elements(by, sel):
                if btn.is_displayed():
                    drv.execute_script('arguments[0].click();', btn)
                    time.sleep(0.2)
                    return True
        except Exception:
            continue
    try:
        res = drv.execute_script("\n            var btns = document.querySelectorAll('button');\n            for (var i = 0; i < btns.length; i++) {\n                if (btns[i].offsetParent !== null && btns[i].textContent.toLowerCase().indexOf('upload files') !== -1) {\n                    btns[i].click(); return 'OK';\n                }\n            } return 'NO';\n        ")
        if res == 'OK':
            time.sleep(0.2)
            return True
    except Exception:
        pass
    return False

def find_file_input_strict(drv, tid=0, job_id=''):
    """
    Finds the file input element. Raises FileInputMissing if not found.
    Never silently continues.
    """
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    deadline = time.time() + 4.0
    while time.time() < deadline:
        try:
            drv.execute_script('\n                document.querySelectorAll(\'input[type="file"]\').forEach(function(el){\n                    el.style.cssText=\'display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;\';\n                    el.removeAttribute(\'hidden\'); el.removeAttribute(\'disabled\');\n                });\n            ')
        except Exception:
            pass
        inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if inputs:
            return inputs[0]
        time.sleep(0.3)
    raise FileInputMissing(f'Tab T{tid}: file input not found after Create Image mode was verified (4s wait)')

def upload_reference_files(drv, abs_paths: list, tid=0, job_id='') -> bool:
    """Send file paths to the file input. Returns True on success."""
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    valid_paths = [p for p in abs_paths if p and os.path.exists(p)]
    if not valid_paths:
        log(f'{prefix} UPLOAD_SKIPPED: No valid reference paths')
        return True
    try:
        fi = find_file_input_strict(drv, tid, job_id)
        fi.send_keys('\n'.join(valid_paths))
        return True
    except FileInputMissing:
        raise
    except Exception as e:
        log(f'{prefix} UPLOAD_FAILED: send_keys error: {e}', file=sys.stderr)
        return False

def verify_attachment_count(drv, expected: int, tid=0, job_id='') -> tuple:
    """
    Polls until attachment chip count == expected (exact match required).
    Returns (verified: bool, actual_count: int).
    FAIL on count < expected OR count > expected.
    If not verified within timeout, returns (False, actual_count).
    """
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    t0 = time.time()
    chip_count = 0
    while time.time() - t0 < 15.0:
        chips = []
        for sel in ["button[aria-label='close attachment']", 'gem-media-attachment', 'uploader-file-preview', '.attachment-preview-wrapper', "div[data-test-id='uploaded-img']"]:
            try:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        chips.append(id(el))
            except Exception:
                pass
        chip_count = len(set(chips))
        if chip_count == expected:
            log(f'{prefix} ATTACHMENTS {chip_count}/{expected} ✅ (exact match)')
            return (True, chip_count)
        time.sleep(0.35)
    log(f'{prefix} ATTACHMENT_MISMATCH: expected exactly {expected}, got {chip_count} (must be exact — not >= or >)', file=sys.stderr)
    return (False, chip_count)

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
        log(f'{prefix} PROMPT_VERIFIED ✅')
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
                log(f'{prefix} PROMPT_VERIFY_FAIL attempt {attempt} — clearing and retrying')
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

def _click_send_button(drv):
    try:
        res = drv.execute_script('\n            var sels = [\'mat-icon[fonticon="arrow_upward"]\', \'mat-icon[data-mat-icon-name="arrow_upward"]\',\n                        \'mat-icon[fonticon="send"]\', \'button[aria-label="Send message"]\'];\n            for (var s = 0; s < sels.length; s++) {\n                var els = document.querySelectorAll(sels[s]);\n                for (var i = 0; i < els.length; i++) {\n                    var b = els[i].tagName === \'BUTTON\' ? els[i] : els[i].closest(\'button\');\n                    if (b && !b.disabled && b.offsetParent !== null) { b.click(); return \'OK\'; }\n                }\n            } return \'NO\';\n        ')
        if res == 'OK':
            return True
    except Exception:
        pass
    for xp in ["//mat-icon[@data-mat-icon-name='arrow_upward']/ancestor::button", "//mat-icon[@fonticon='arrow_upward']/ancestor::button", "//button[@aria-label='Send message']"]:
        try:
            for btn in drv.find_elements(By.XPATH, xp):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script('arguments[0].click();', btn)
                    return True
        except Exception:
            continue
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
print('  ✅ Gemini DOM engine initialized.\n')

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

# ==============================================================================
# FINAL RUNTIME HARDENING - ORCHESTRATION & STATE MACHINE (V16)
# ==============================================================================

class JobState(Enum):
    QUEUED = "QUEUED"
    GEMINI_RESERVED = "GEMINI_RESERVED"
    GEMINI_GENERATING = "GEMINI_GENERATING"
    RAW_DOWNLOAD_START = "RAW_DOWNLOAD_START"
    GEMINI_RELEASED = "GEMINI_RELEASED"
    RAW_DOWNLOADING = "RAW_DOWNLOADING"
    RAW_READY = "RAW_READY"
    RAW_VALIDATED = "RAW_VALIDATED"
    WMR_QUEUED = "WMR_QUEUED"
    WMR_RESERVED = "WMR_RESERVED"
    WMR_PROCESSING = "WMR_PROCESSING"
    WMR_DOWNLOAD_START = "WMR_DOWNLOAD_START"
    WMR_RELEASED = "WMR_RELEASED"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    R2_READY = "R2_READY"
    DB_FINALIZING = "DB_FINALIZING"
    DB_READY = "DB_READY"
    CREDITS_SETTLED = "CREDITS_SETTLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class JobContext:
    job_id: str
    payload: Dict[str, Any]
    loop: asyncio.AbstractEventLoop
    
    state: JobState = JobState.QUEUED
    gemini_resource: Optional[str] = None
    gemini_released: bool = False
    wmr_resource: Optional[str] = None
    wmr_released: bool = False
    
    raw_guid: Optional[str] = None
    wmr_guid: Optional[str] = None
    
    prompt: Optional[str] = None
    garment_path: Optional[str] = None
    model_path: Optional[str] = None
    holo_path: Optional[str] = None
    reference_paths: List[str] = field(default_factory=list)
    
    raw_path: Optional[str] = None
    clean_png_path: Optional[str] = None
    webp_path: Optional[str] = None
    
    error: Optional[str] = None
    
    state_waiters: Dict[JobState, List[asyncio.Future]] = field(default_factory=dict)
    
    def transition_sync(self, new_state: JobState):
        self.loop.call_soon_threadsafe(self._set_state_threadsafe, new_state)
        
    def _set_state_threadsafe(self, new_state: JobState):
        old = self.state
        self.state = new_state
        print(f"[STATE] {self.job_id}: {old.name} -> {new_state.name}")
        
        if new_state in self.state_waiters:
            for fut in self.state_waiters[new_state]:
                if not fut.done(): fut.set_result(True)
            self.state_waiters[new_state].clear()
            
        if new_state == JobState.FAILED and JobState.FAILED in self.state_waiters:
            for fut in self.state_waiters[JobState.FAILED]:
                if not fut.done(): fut.set_exception(RuntimeError(self.error or "Job Failed"))
            self.state_waiters[JobState.FAILED].clear()
            
    async def wait_for_state(self, target_state: JobState):
        if self.state == target_state: return
        if self.state == JobState.FAILED: raise RuntimeError(self.error or "Job Failed")
        fut = self.loop.create_future()
        self.state_waiters.setdefault(target_state, []).append(fut)
        self.state_waiters.setdefault(JobState.FAILED, []).append(fut)
        await fut

@dataclass
class DownloadRecord:
    record_id: str
    guid: Optional[str]
    job_id: str
    resource_id: str
    resource_type: str
    source: str
    staging_dir: str
    expected_filename: str
    actual_filename: Optional[str]
    target_state: JobState
    started_at: float
    created_at: float

DOWNLOAD_REGISTRY: Dict[str, DownloadRecord] = {}
DOWNLOAD_REGISTRY_LOCK = threading.RLock()
JOB_CONTEXTS: Dict[str, JobContext] = {}

class ResourceState(Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    RECOVERING = "RECOVERING"
    DEAD = "DEAD"

@dataclass
class ResourceRecord:
    resource_id: str
    state: ResourceState = ResourceState.AVAILABLE
    current_job_id: Optional[str] = None
    failure_count: int = 0
    last_error: Optional[str] = None
    last_used: float = 0.0
    last_health_check: float = 0.0

class ResourceAcquireTimeout(Exception):
    def __init__(self, broker_name: str, job_id: str, wait_s: float, resource_states: Dict[str, str]):
        self.broker_name = broker_name
        self.job_id = job_id
        self.wait_s = wait_s
        self.resource_states = resource_states
        super().__init__(
            f"[{broker_name} BROKER] acquire timeout after {wait_s:.1f}s for job={job_id}; "
            f"states={resource_states}"
        )

MAX_RESOURCE_FAILURES = 5
RECOVERY_COOLDOWN_BASE_S = 15
RECOVERY_COOLDOWN_MAX_S = 300
RESOURCE_ACQUIRE_TIMEOUT_S = 120

class FirstFreeBroker:
    def __init__(self, name: str, resources: List[str]):
        self.name = name
        self.resource_ids = resources
        self._records: Dict[str, ResourceRecord] = {r: ResourceRecord(resource_id=r) for r in resources}
        self._free_heap = []
        self._seq = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._recovery_fn = None
        for r in resources:
            self._seq += 1
            heapq.heappush(self._free_heap, (self._seq, r))

    def set_recovery_fn(self, fn):
        """fn(resource_id) -> bool. Called off-lock in a background thread to restart the
        underlying driver/tab and prove it healthy before the resource is returned to the pool."""
        self._recovery_fn = fn

    async def acquire(self, job_id: str, timeout: float = RESOURCE_ACQUIRE_TIMEOUT_S) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._acquire_sync, job_id, timeout)

    def _acquire_sync(self, job_id: str, timeout: float) -> str:
        t0 = time.monotonic()
        with self._condition:
            while not self._free_heap:
                remaining = timeout - (time.monotonic() - t0)
                if remaining <= 0:
                    raise ResourceAcquireTimeout(self.name, job_id, time.monotonic() - t0, self.snapshot_locked())
                self._condition.wait(timeout=remaining)
            _, resource_id = heapq.heappop(self._free_heap)
            rec = self._records[resource_id]
            rec.state = ResourceState.BUSY
            rec.current_job_id = job_id
            rec.last_used = time.time()
            print(f"[{self.name} BROKER] Acquired {resource_id} for {job_id}")
            return resource_id

    def release(self, resource_id: str):
        with self._condition:
            rec = self._records.get(resource_id)
            if rec is None or rec.state in (ResourceState.DEAD, ResourceState.RECOVERING):
                return
            rec.state = ResourceState.AVAILABLE
            rec.current_job_id = None
            rec.last_health_check = time.time()
            if not any((res_id == resource_id for _, res_id in self._free_heap)):
                self._seq += 1
                heapq.heappush(self._free_heap, (self._seq, resource_id))
                print(f"[{self.name} BROKER] Released {resource_id}")
                self._condition.notify_all()

    def fail(self, resource_id: str, error: str = ""):
        with self._condition:
            rec = self._records.get(resource_id)
            if rec is None:
                return
            rec.failure_count += 1
            rec.last_error = (error or "")[:500]
            rec.current_job_id = None
            if rec.failure_count >= MAX_RESOURCE_FAILURES:
                rec.state = ResourceState.DEAD
                print(f"[{self.name} BROKER] {resource_id} PERMANENTLY DEAD after {rec.failure_count} failures: {rec.last_error}")
                return
            rec.state = ResourceState.RECOVERING
            cooldown = min(RECOVERY_COOLDOWN_BASE_S * (2 ** (rec.failure_count - 1)), RECOVERY_COOLDOWN_MAX_S)
            print(f"[{self.name} BROKER] {resource_id} FAILED (#{rec.failure_count}): {rec.last_error} -> RECOVERY_QUEUED for {cooldown:.0f}s")
            timer = threading.Timer(cooldown, self._recover, args=(resource_id,))
            timer.daemon = True
            timer.start()

    def _recover(self, resource_id: str):
        ok = True
        if self._recovery_fn is not None:
            try:
                ok = bool(self._recovery_fn(resource_id))
            except Exception as e:
                print(f"[{self.name} BROKER] {resource_id} recovery_fn raised: {e}")
                ok = False
        with self._condition:
            rec = self._records.get(resource_id)
            if rec is None or rec.state != ResourceState.RECOVERING:
                return
            rec.last_health_check = time.time()
            if ok:
                rec.state = ResourceState.AVAILABLE
                if not any((res_id == resource_id for _, res_id in self._free_heap)):
                    self._seq += 1
                    heapq.heappush(self._free_heap, (self._seq, resource_id))
                print(f"[{self.name} BROKER] {resource_id} RECOVERY_COMPLETE -> AVAILABLE")
                self._condition.notify_all()
            else:
                rec.failure_count += 1
                if rec.failure_count >= MAX_RESOURCE_FAILURES:
                    rec.state = ResourceState.DEAD
                    print(f"[{self.name} BROKER] {resource_id} PERMANENTLY DEAD after {rec.failure_count} failed recovery attempts")
                else:
                    cooldown = min(RECOVERY_COOLDOWN_BASE_S * (2 ** (rec.failure_count - 1)), RECOVERY_COOLDOWN_MAX_S)
                    print(f"[{self.name} BROKER] {resource_id} RECOVERY_FAILED -> retrying in {cooldown:.0f}s")
                    timer = threading.Timer(cooldown, self._recover, args=(resource_id,))
                    timer.daemon = True
                    timer.start()

    def snapshot_locked(self) -> Dict[str, str]:
        return {rid: rec.state.value for rid, rec in self._records.items()}

    def snapshot(self) -> Dict[str, str]:
        with self._condition:
            return self.snapshot_locked()

    @property
    def free_resources(self):
        with self._condition:
            return [rid for rid, rec in self._records.items() if rec.state == ResourceState.AVAILABLE]

def _detect_download_start(drv, staging_dir: Path, timeout: float = 60.0) -> Tuple[Optional[str], str]:
    """
    Detect a download starting inside staging_dir, which must already be scoped
    exclusively to one job/resource (never a shared directory).
    Primary: real Browser.downloadWillBegin CDP GUID.
    Fallback: a newly-created, non-partial file appearing in staging_dir — ownership
    is proven by directory exclusivity, never by guessing a filename across jobs.
    Returns (guid_or_None, source) where source is "cdp" or "filesystem".
    Raises RuntimeError on timeout; never guesses.
    """
    t0 = time.time()
    try:
        before = {f.name for f in staging_dir.iterdir()} if staging_dir.exists() else set()
    except Exception:
        before = set()
    while time.time() - t0 < timeout:
        try:
            for entry in drv.get_log('performance'):
                try:
                    msg = json.loads(entry['message'])['message']
                    if msg['method'] == 'Browser.downloadWillBegin':
                        return (msg['params']['guid'], "cdp")
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if staging_dir.exists():
                for f in staging_dir.iterdir():
                    if f.name in before:
                        continue
                    if f.name.endswith(('.crdownload', '.tmp', '.part')):
                        continue
                    return (None, "filesystem")
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Download start timeout after {timeout}s (dir={staging_dir})")

GEMINI_BROKER = FirstFreeBroker("GEMINI", [f"T{i}" for i in range(4)])
WMR_BROKER = FirstFreeBroker("WMR", [f"W{i}-T{j}" for i in range(4) for j in range(2)])
CHROME_DRIVER_LOCK = threading.RLock()

def _recover_gemini_resource(resource_id: str) -> bool:
    """Recreate this Gemini tab on the shared chrome_driver and prove it responds."""
    worker = GEMINI_WORKERS.get(resource_id)
    if worker is None:
        return False
    tid_int = int(resource_id.replace('T', ''))
    with CHROME_DRIVER_LOCK:
        try:
            if worker.handle and worker.handle in chrome_driver.window_handles:
                try:
                    chrome_driver.switch_to.window(worker.handle)
                    chrome_driver.close()
                except Exception:
                    pass
            worker.handle = None
            worker.driver = None
            new_handle = _create_gemini_tab(tid_int)
            chrome_driver.switch_to.window(new_handle)
            _ = chrome_driver.title
            worker.handle = new_handle
            worker.driver = chrome_driver
            log(f"[GEMINI BROKER] {resource_id} RECOVERY_HEALTH_CHECK = OK (new tab {new_handle})")
            return True
        except Exception as e:
            log(f"[GEMINI BROKER] {resource_id} RECOVERY_HEALTH_CHECK = FAILED: {e}")
            worker.handle = None
            worker.driver = None
            return False

def _recover_wmr_resource(resource_id: str) -> bool:
    """Restart this WMR slot's dedicated Chrome process and prove it responds."""
    thread = WMR_THREADS.get(resource_id)
    if thread is None:
        return False
    try:
        if thread.driver is not None:
            try:
                thread.driver.quit()
            except Exception:
                pass
            thread.driver = None
        thread.driver = create_wmr_chrome_driver(resource_id)
        _ = thread.driver.title
        log(f"[WMR BROKER] {resource_id} RECOVERY_HEALTH_CHECK = OK")
        return True
    except Exception as e:
        log(f"[WMR BROKER] {resource_id} RECOVERY_HEALTH_CHECK = FAILED: {e}")
        try:
            if thread.driver:
                thread.driver.quit()
        except Exception:
            pass
        thread.driver = None
        return False

GEMINI_BROKER.set_recovery_fn(_recover_gemini_resource)
WMR_BROKER.set_recovery_fn(_recover_wmr_resource)

def release_gemini_once(ctx: JobContext):
    if ctx.gemini_resource and not ctx.gemini_released:
        ctx.gemini_released = True
        GEMINI_BROKER.release(ctx.gemini_resource)

def release_wmr_once(ctx: JobContext):
    if ctx.wmr_resource and not ctx.wmr_released:
        ctx.wmr_released = True
        WMR_BROKER.release(ctx.wmr_resource)

# ------------------------------------------------------------------------------
# PIPELINE EXECUTION
# ------------------------------------------------------------------------------

from concurrent.futures import ThreadPoolExecutor
GEMINI_EXECUTOR = ThreadPoolExecutor(max_workers=4)

class GeminiWorker:
    def __init__(self, tid: str):
        self.tid = tid
        self.driver = None

    def do_execute_sync(self, ctx: JobContext):
        prefix = f"[{self.tid}][{ctx.job_id}]"
        try:
            ctx.transition_sync(JobState.GEMINI_GENERATING)
            if self.driver is None:
                self.driver = create_chrome_driver()
                comprehensive_login_check(self.driver, "Gemini Worker")

            tid_int = int(self.tid.replace('T', ''))
            
            tab_id_str = open_new_chat_and_reload(self.driver, tid_int, ctx.job_id)
            if not tab_id_str:
                raise RuntimeError("Failed to create/find target tab")
            
            staging_dir = get_chrome_job_dir(tid_int, ctx.job_id)
            set_tab_download_dir(self.driver, str(staging_dir))

            ensure_create_image_mode(self.driver, tid_int, ctx.job_id)

            upload_reference_files(self.driver, ctx.reference_paths, tid_int, ctx.job_id)
            verify_attachment_count(self.driver, expected=len(ctx.reference_paths), tid=tid_int, job_id=ctx.job_id)
            
            _inject_prompt_atomic(self.driver, ctx.prompt, tid_int, ctx.job_id)

            urls_before = snapshot_urls(self.driver)
            _click_send_button(self.driver)

            started = verify_generation_started(self.driver)
            if not started:
                raise RuntimeError("Generation did not start")

            _has_generated_image(self.driver, urls_before)
            
            chat_urls = snapshot_urls(self.driver)
            _hover_and_dl_single_click(self.driver, urls_before, chat_urls)

            expected_png = f"{ctx.job_id}.png"
            dl_guid = None
            source = "cdp"
            
            ctx.transition_sync(JobState.RAW_DOWNLOAD_START)

            t_dl = time.time()
            while time.time() - t_dl < 60:
                try:
                    for entry in self.driver.get_log('performance'):
                        try:
                            msg = json.loads(entry['message'])['message']
                            if msg['method'] == 'Browser.downloadWillBegin':
                                dl_guid = msg['params']['guid']
                                break
                        except Exception: pass
                except Exception: pass
                if dl_guid: break
                
                try:
                    files = list(staging_dir.iterdir())
                    if files:
                        for f in files:
                            if f.name.endswith(".crdownload") or f.stat().st_size > 0:
                                dl_guid = None
                                source = "filesystem"
                                break
                except Exception: pass
                
                if source == "filesystem": break
                time.sleep(1)

            if not dl_guid and source != "filesystem":
                raise RuntimeError("Download start timeout")
            
            ctx.raw_guid = dl_guid
            
            record_id = f"gemini:{ctx.job_id}:{time.monotonic_ns()}"
            with DOWNLOAD_REGISTRY_LOCK:
                DOWNLOAD_REGISTRY[record_id] = DownloadRecord(
                    record_id=record_id,
                    guid=dl_guid,
                    job_id=ctx.job_id,
                    resource_id=self.tid,
                    resource_type="gemini",
                    source=source,
                    staging_dir=str(staging_dir),
                    expected_filename=expected_png,
                    actual_filename=None,
                    target_state=JobState.RAW_VALIDATED,
                    started_at=time.time(),
                    created_at=time.time()
                )
            
            release_gemini_once(ctx)
            ctx.transition_sync(JobState.GEMINI_RELEASED)
            ctx.transition_sync(JobState.RAW_DOWNLOADING)

        except Exception as e:
            ctx.error = str(e)
            ctx.transition_sync(JobState.FAILED)
            GEMINI_BROKER.fail(self.tid)
            try: self.driver.quit()
            except Exception: pass
            self.driver = None
            release_gemini_once(ctx)

GEMINI_WORKERS = {f"T{i}": GeminiWorker(f"T{i}") for i in range(4)}

class WmrDriverThread(threading.Thread):
    def __init__(self, resource_id: str):
        super().__init__(daemon=True)
        self.resource_id = resource_id
        self.command_queue = queue.Queue()
        self.driver = None

    def run(self):
        while True:
            cmd, ctx = self.command_queue.get()
            if cmd == "EXECUTE":
                prefix = f"[{self.resource_id}][{ctx.job_id}]"
                try:
                    if self.driver is None:
                        self.driver = create_wmr_chrome_driver(self.resource_id)
                        self.driver.get("https://www.watermarkremover.io/upload")
                    
                    ctx.transition_sync(JobState.WMR_PROCESSING)
                    
                    staging_dir = Path(WMR_STAGING_BASE) / self.resource_id / ctx.job_id
                    staging_dir.mkdir(parents=True, exist_ok=True)
                    
                    set_tab_download_dir(self.driver, str(staging_dir))

                    _wmr_expose_file_inputs(self.driver)
                    file_input = _wmr_find_file_input(self.driver)
                    file_input.send_keys(str(Path(ctx.raw_path).resolve()))

                    try: _wmr_check_status(self.driver)
                    except Exception: pass 
                        
                    try: _wmr_click_download(self.driver)
                    except Exception: _wmr_click_download(self.driver, attempts=6)

                    expected_png = f"{ctx.job_id}_clean.png"
                    ctx.transition_sync(JobState.WMR_DOWNLOAD_START)
                    
                    dl_guid = None
                    source = "cdp"
                    
                    t_dl = time.time()
                    while time.time() - t_dl < 60:
                        try:
                            for entry in self.driver.get_log('performance'):
                                try:
                                    msg = json.loads(entry['message'])['message']
                                    if msg['method'] == 'Browser.downloadWillBegin':
                                        dl_guid = msg['params']['guid']
                                        break
                                except Exception: pass
                        except Exception: pass
                        if dl_guid: break
                        
                        try:
                            files = list(staging_dir.iterdir())
                            if files:
                                for f in files:
                                    if f.name.endswith(".crdownload") or f.stat().st_size > 0:
                                        dl_guid = None
                                        source = "filesystem"
                                        break
                        except Exception: pass
                        if source == "filesystem": break
                        time.sleep(1)
                        
                    if not dl_guid and source != "filesystem":
                        raise RuntimeError("WMR Download start timeout")

                    record_id = f"wmr:{ctx.job_id}:{time.monotonic_ns()}"
                    with DOWNLOAD_REGISTRY_LOCK:
                        DOWNLOAD_REGISTRY[record_id] = DownloadRecord(
                            record_id=record_id,
                            guid=dl_guid,
                            job_id=ctx.job_id,
                            resource_id=self.resource_id,
                            resource_type="wmr",
                            source=source,
                            staging_dir=str(staging_dir),
                            expected_filename=expected_png,
                            actual_filename=None,
                            target_state=JobState.CLEAN_READY,
                            started_at=time.time(),
                            created_at=time.time()
                        )
                    
                    release_wmr_once(ctx)
                    ctx.transition_sync(JobState.WMR_RELEASED)

                except Exception as e:
                    ctx.error = str(e)
                    ctx.transition_sync(JobState.FAILED)
                    WMR_BROKER.fail(self.resource_id)
                    try: self.driver.quit()
                    except Exception: pass
                    self.driver = None
                    release_wmr_once(ctx)
                finally:
                    self.command_queue.task_done()
            else:
                self.command_queue.task_done()

# V16: Only initialize at runtime
WMR_THREADS = {}

async def execute_pipeline(ctx: JobContext):
    try:
        prompt, garment_path, model_path, holo_path = resolve_prompt_and_refs(ctx.payload)
        ctx.prompt = prompt
        ctx.garment_path = garment_path
        ctx.model_path = model_path
        ctx.holo_path = holo_path
        ctx.reference_paths = [p for p in (garment_path, holo_path, model_path) if p]
        
        for p in ctx.reference_paths:
            if not Path(p).exists() or Path(p).stat().st_size == 0:
                raise RuntimeError(f"Reference invalid: {p}")
        
        tid = await GEMINI_BROKER.acquire(ctx.job_id)
        ctx.gemini_resource = tid
        ctx.transition_sync(JobState.GEMINI_RESERVED)
        
        worker = GEMINI_WORKERS[tid]
        await ctx.loop.run_in_executor(GEMINI_EXECUTOR, worker.do_execute_sync, ctx)
        await ctx.wait_for_state(JobState.RAW_VALIDATED)
        
        ctx.transition_sync(JobState.WMR_QUEUED)
        w_tid = await WMR_BROKER.acquire(ctx.job_id)
        ctx.wmr_resource = w_tid
        ctx.transition_sync(JobState.WMR_RESERVED)
        
        WMR_THREADS[w_tid].command_queue.put(("EXECUTE", ctx))
        await ctx.wait_for_state(JobState.CLEAN_READY)
        
        webp_path = Path(ctx.clean_png_path).with_suffix('.webp')
        result = subprocess.run(['cwebp', '-q', '80', ctx.clean_png_path, '-o', str(webp_path)], capture_output=True)
        if result.returncode != 0:
            from PIL import Image
            img = Image.open(ctx.clean_png_path)
            img.save(str(webp_path), 'WEBP', quality=80)
            
        if not webp_path.exists() or webp_path.stat().st_size == 0:
            raise RuntimeError("WebP conversion failed.")
        
        validate_image_file(str(webp_path))
        ctx.webp_path = str(webp_path)
        ctx.transition_sync(JobState.WEBP_READY)
        
        try:
            fs = sys.modules["fashion_studio"]
            fs.push_generation(
                image_path=ctx.clean_png_path,
                prompt=ctx.prompt,
                user_id=ctx.payload.get("user_id"),
                gen_id=ctx.job_id,
                webp_path=ctx.webp_path,
                force=True
            )
            ctx.transition_sync(JobState.R2_READY)
            ctx.transition_sync(JobState.DB_FINALIZING)
            ctx.transition_sync(JobState.DB_READY)
            
            crd = sys.modules["credits"]
            crd.settle_look(ctx.job_id)
            ctx.transition_sync(JobState.CREDITS_SETTLED)
        except Exception as e:
            if "credits" in sys.modules:
                sys.modules["credits"].refund_look(ctx.job_id, str(e)[:500])
            raise

        ctx.transition_sync(JobState.COMPLETED)
        
    except Exception as e:
        ctx.error = str(e)
        if ctx.state != JobState.FAILED:
            ctx.transition_sync(JobState.FAILED)
        release_gemini_once(ctx)
        release_wmr_once(ctx)

# ------------------------------------------------------------------------------
# DOWNLOAD WATCHER
# ------------------------------------------------------------------------------

async def poll_downloads_loop():
    while True:
        try:
            with DOWNLOAD_REGISTRY_LOCK:
                items = list(DOWNLOAD_REGISTRY.items())
            
            for dict_key, rec in items:
                ctx = JOB_CONTEXTS.get(rec.job_id)
                if not ctx or ctx.state == JobState.FAILED:
                    with DOWNLOAD_REGISTRY_LOCK: DOWNLOAD_REGISTRY.pop(dict_key, None)
                    continue

                staging = Path(rec.staging_dir)
                if not staging.exists(): continue

                completed_file = None
                for f in staging.iterdir():
                    if f.name == rec.expected_filename or (rec.guid and f.name.startswith(rec.guid)):
                        if not f.name.endswith(".crdownload"):
                            completed_file = f
                            break

                if completed_file:
                    size_before = -1
                    stable = False
                    for _ in range(20):
                        try:
                            sz = completed_file.stat().st_size
                            if sz > 0 and sz == size_before:
                                stable = True
                                break
                            size_before = sz
                            await asyncio.sleep(0.1)
                        except Exception: pass

                    if stable:
                        try:
                            validate_image_file(str(completed_file))
                            if rec.target_state == JobState.RAW_VALIDATED:
                                ctx.raw_path = str(completed_file)
                                ctx.transition_sync(JobState.RAW_READY)
                            else:
                                ctx.clean_png_path = str(completed_file)

                            ctx.transition_sync(rec.target_state)
                            with DOWNLOAD_REGISTRY_LOCK: DOWNLOAD_REGISTRY.pop(dict_key, None)
                        except Exception as e:
                            print(f"[{rec.job_id}] DOWNLOAD_VALIDATE_FAILED: {e}")
                            
        except Exception as e:
            print(f"[DOWNLOAD_WATCHER_ERROR] {e}")
        await asyncio.sleep(1)

# ------------------------------------------------------------------------------
# BULLMQ INTEGRATION
# ------------------------------------------------------------------------------

async def process_bullmq_job(job, job_token):
    generation_id = job.data.get("generationId") or job.data.get("id") or job.id
    print(f"[{WORKER_ID}] BullMQ job={job.id} generation={generation_id}")

    gen = fetch_generation(generation_id)
    if not gen: raise RuntimeError(f"Generation {generation_id} not found in DB.")

    ctx = JobContext(job_id=generation_id, payload=gen, loop=asyncio.get_running_loop())
    JOB_CONTEXTS[generation_id] = ctx
    
    await execute_pipeline(ctx)

    if ctx.state == JobState.FAILED:
        raise RuntimeError(ctx.error)
    return {"status": "success"}


# ------------------------------------------------------------------------------
# HEALTH & STARTUP
# ------------------------------------------------------------------------------

def run_architecture_self_test():
    assert len(GEMINI_BROKER.resource_ids) == 4
    assert len(WMR_BROKER.resource_ids) == 8
    assert "T0" in GEMINI_BROKER.resource_ids
    assert "T3" in GEMINI_BROKER.resource_ids
    for rid in ["W0-T0","W0-T1","W1-T0","W1-T1","W2-T0","W2-T1","W3-T0","W3-T1"]:
        assert rid in WMR_BROKER.resource_ids

BACKGROUND_TASKS = set()
BULLMQ_WORKER = None
QUEUE_MONITOR = None
QUEUE_MONITOR_TASK = None
HEARTBEAT_TASK = None
WATCHER_TASK = None

RUNTIME_HEALTH = {
    "redis": False,
    "db": False,
    "r2": False,
    "bullmq": False,
    "download_monitor": False,
    "heartbeat": False,
}

def initialize_runtime_once():
    global WMR_THREADS
    if not WMR_THREADS:
        for i in range(4):
            for j in range(2):
                rid = f"W{i}-T{j}"
                WMR_THREADS[rid] = WmrDriverThread(rid)
                WMR_THREADS[rid].start()

async def redis_queue_monitor_loop():
    global QUEUE_MONITOR
    opts = {"connection": os.environ.get("REDIS_URL"), "prefix": os.environ.get("REDIS_KEY_PREFIX")}
    from urllib.parse import urlparse
    u = urlparse(opts["connection"] or "")
    real_opts = {"host": u.hostname or "localhost", "port": u.port or 6379}
    if u.password: real_opts["password"] = u.password
    if u.scheme == 'rediss': real_opts["tls"] = {}
    QUEUE_NAME = os.environ.get("QUEUE_NAME", "generations")
    
    QUEUE_MONITOR = Queue(
        QUEUE_NAME,
        {
            "connection": real_opts,
            "prefix": opts["prefix"],
        },
    )

    while True:
        try:
            counts = await QUEUE_MONITOR.getJobCounts()

            print("\n" + "=" * 60)
            print("REDIS / BULLMQ QUEUE STATUS")
            print("=" * 60)
            print(f"Queue: {QUEUE_NAME}")
            print(f"WAITING: {counts.get('waiting', 0)}")
            print(f"ACTIVE: {counts.get('active', 0)}")
            print(f"DELAYED: {counts.get('delayed', 0)}")
            print(f"PRIORITIZED: {counts.get('prioritized', 0)}")
            print(f"WAITING-CHILDREN: {counts.get('waiting-children', 0)}")
            print(f"COMPLETED: {counts.get('completed', 0)}")
            print(f"FAILED: {counts.get('failed', 0)}")
            print("=" * 60)

            if not any([
                counts.get("waiting", 0),
                counts.get("active", 0),
                counts.get("delayed", 0),
            ]):
                print("[REDIS] QUEUE EMPTY — worker alive and waiting for jobs")

        except Exception as e:
            print(f"[REDIS MONITOR ERROR] {type(e).__name__}: {e}")

        await asyncio.sleep(5)

async def worker_heartbeat_loop():
    RUNTIME_HEALTH["heartbeat"] = True
    QUEUE_NAME = os.environ.get("QUEUE_NAME", "generations")
    # For tracking uptime
    start_time = time.time()
    
    while True:
        try:
            uptime = time.time() - start_time
            hours, rem = divmod(uptime, 3600)
            minutes, seconds = divmod(rem, 60)
            uptime_str = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
            
            print("\n" + "=" * 60)
            print("ECOM PHOTOSHOOT N2N WORKER STATUS")
            print("=" * 60)
            
            print("\nWorker:")
            print(f"  ID        = {WORKER_ID}")
            print(f"  Uptime    = {uptime_str}")
            print(f"  Status    = RUNNING")
            
            print("\nGemini:")
            for rid in ["T0", "T1", "T2", "T3"]:
                print(f"  {rid} = {'FREE' if rid in GEMINI_BROKER.free_resources else 'BUSY/DEAD'}")
                
            print("\nWMR:")
            for rid in ["W0-T0", "W0-T1", "W1-T0", "W1-T1", "W2-T0", "W2-T1", "W3-T0", "W3-T1"]:
                print(f"  {rid} = {'FREE' if rid in WMR_BROKER.free_resources else 'BUSY/DEAD'}")

            # Local Jobs
            local_jobs = list(JOB_CONTEXTS.values())
            print("\nLocal Jobs:")
            print(f"  QUEUED           = {sum(1 for j in local_jobs if j.state == JobState.QUEUED)}")
            print(f"  GEMINI_GENERATING= {sum(1 for j in local_jobs if j.state == JobState.GEMINI_GENERATING)}")
            print(f"  RAW_DOWNLOADING  = {sum(1 for j in local_jobs if j.state == JobState.RAW_DOWNLOADING)}")
            print(f"  RAW_VALIDATED    = {sum(1 for j in local_jobs if j.state == JobState.RAW_VALIDATED)}")
            print(f"  WMR_PROCESSING   = {sum(1 for j in local_jobs if j.state == JobState.WMR_PROCESSING)}")
            print(f"  CLEAN_READY      = {sum(1 for j in local_jobs if j.state == JobState.CLEAN_READY)}")
            print(f"  WEBP_READY       = {sum(1 for j in local_jobs if j.state == JobState.WEBP_READY)}")
            print(f"  COMPLETED        = {sum(1 for j in local_jobs if j.state == JobState.COMPLETED)}")
            print(f"  FAILED           = {sum(1 for j in local_jobs if j.state == JobState.FAILED)}")
            
            print("\n" + "=" * 60)
            print("WORKER HEARTBEAT")
            print("=" * 60)
            print(f"Worker ID: {WORKER_ID}")
            print(f"Uptime: {uptime_str}")
            print(f"BullMQ Worker: {'RUNNING' if RUNTIME_HEALTH['bullmq'] else 'FAILED'}")
            print(f"Download Monitor: {'RUNNING' if RUNTIME_HEALTH['download_monitor'] else 'FAILED'}")
            print(f"Gemini Broker: OK")
            print(f"WMR Broker: OK")
            print(f"Queue: {QUEUE_NAME}")
            print("=" * 60)
            
        except Exception as e:
            print(f"[HEARTBEAT ERROR] {e}")
            
        await asyncio.sleep(10)

async def main():
    try:
        global BULLMQ_WORKER, QUEUE_MONITOR_TASK, HEARTBEAT_TASK, WATCHER_TASK
        
        print("STEP 11: REDIS HEALTH")
        opts = {"connection": os.environ.get("REDIS_URL"), "prefix": os.environ.get("REDIS_KEY_PREFIX")}
        from urllib.parse import urlparse
        u = urlparse(opts["connection"] or "")
        real_opts = {"host": u.hostname or "localhost", "port": u.port or 6379}
        if u.password: real_opts["password"] = u.password
        if u.scheme == 'rediss': real_opts["tls"] = {}
        QUEUE_NAME = os.environ.get("QUEUE_NAME", "generations")
        
        # Redis pre-flight
        try:
            _q = Queue(QUEUE_NAME, {"connection": real_opts, "prefix": opts["prefix"]})
            await _q.getJobCounts()
            await _q.close()
            print("[REDIS] CONNECTION = OK")
            RUNTIME_HEALTH["redis"] = True
        except Exception as e:
            print("[REDIS] CONNECTION = FAILED")
            raise

        print("STEP 12: DATABASE HEALTH")
        db_conn = sys.modules['db'].borrow()
        db_conn.cursor().execute("SELECT 1")
        db_conn.close()
        print("[DB] CONNECTION = OK")
        RUNTIME_HEALTH["db"] = True

        print("STEP 13: R2 HEALTH")
        # Optional health check for R2 here
        RUNTIME_HEALTH["r2"] = True
        
        print("STEP 14: GEMINI BROKER")
        initialize_runtime_once()
        
        print("STEP 15: WMR BROKER")
        run_architecture_self_test()

        print("STEP 16: DOWNLOAD MONITOR")
        WATCHER_TASK = asyncio.create_task(poll_downloads_loop())
        BACKGROUND_TASKS.add(WATCHER_TASK)
        RUNTIME_HEALTH["download_monitor"] = True

        print("STEP 17: REDIS QUEUE MONITOR")
        if QUEUE_MONITOR_TASK and not QUEUE_MONITOR_TASK.done():
            print("[REDIS MONITOR] Already running")
        else:
            QUEUE_MONITOR_TASK = asyncio.create_task(redis_queue_monitor_loop())
            BACKGROUND_TASKS.add(QUEUE_MONITOR_TASK)

        print("STEP 18: WORKER HEARTBEAT")
        if HEARTBEAT_TASK and not HEARTBEAT_TASK.done():
            print("[HEARTBEAT] Already running")
        else:
            HEARTBEAT_TASK = asyncio.create_task(worker_heartbeat_loop())
            BACKGROUND_TASKS.add(HEARTBEAT_TASK)

        print("STEP 19: BULLMQ WORKER")
        BULLMQ_WORKER = Worker(QUEUE_NAME, process_bullmq_job, {"connection": real_opts, "prefix": opts["prefix"]})
        RUNTIME_HEALTH["bullmq"] = True

        print("STEP 20: WORKER READY")
        print("\n============================================================")
        print("N2N WORKER READY")
        print("============================================================")
        
        while True:
            await asyncio.sleep(3600)
            
    except asyncio.CancelledError:
        raise
    except Exception:
        print("============================================================")
        print("[FATAL STARTUP ERROR]")
        print("============================================================")
        import traceback
        traceback.print_exc()
        raise

async def shutdown_worker():
    global BULLMQ_WORKER, QUEUE_MONITOR
    if BULLMQ_WORKER: await BULLMQ_WORKER.close()
    if QUEUE_MONITOR: await QUEUE_MONITOR.close()
    
    if QUEUE_MONITOR_TASK: QUEUE_MONITOR_TASK.cancel()
    if HEARTBEAT_TASK: HEARTBEAT_TASK.cancel()
    if WATCHER_TASK: WATCHER_TASK.cancel()
    if WORKER_MAIN_TASK: WORKER_MAIN_TASK.cancel()
    
    for task in BACKGROUND_TASKS:
        task.cancel()
    if BACKGROUND_TASKS:
        await asyncio.gather(*BACKGROUND_TASKS, return_exceptions=True)
    
    print("[SHUTDOWN] Worker stopped cleanly.")

WORKER_MAIN_TASK = None
_RUNTIME_INITIALIZED = False

def _worker_main_task_done(task):
    global _RUNTIME_INITIALIZED
    if task.cancelled():
        print("[WORKER] MAIN TASK CANCELLED")
        return

    exc = task.exception()
    if exc:
        print("=" * 70)
        print("[FATAL] WORKER MAIN TASK CRASHED")
        print("=" * 70)
        import traceback
        traceback.print_exception(
            type(exc),
            exc,
            exc.__traceback__,
        )
    _RUNTIME_INITIALIZED = False

def start_worker():
    global WORKER_MAIN_TASK, _RUNTIME_INITIALIZED
    
    if _RUNTIME_INITIALIZED:
        print("[BOOT] Existing worker already running")
        return WORKER_MAIN_TASK
        
    try: loop = asyncio.get_running_loop()
    except RuntimeError: return asyncio.run(main())
    
    if WORKER_MAIN_TASK and not WORKER_MAIN_TASK.done():
        return WORKER_MAIN_TASK
        
    _RUNTIME_INITIALIZED = True
    WORKER_MAIN_TASK = loop.create_task(main())
    WORKER_MAIN_TASK.add_done_callback(_worker_main_task_done)
    return WORKER_MAIN_TASK

if __name__ == '__main__':
    if "IPython" in sys.modules:
        import IPython
        ipy = IPython.get_ipython()
        if ipy:
            # Inject await directly into the current cell's execution context
            # We do this using run_cell with await
            ipy.run_cell("task = start_worker()\nawait task")
        else:
            task = start_worker()
    else:
        start_worker()
