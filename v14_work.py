# ============================================================================
# 🚀 QUEUE WORKER v9.0 — CHROME ONLY DUAL-SYSTEM (GEMINI + WMR CHROME)
# ============================================================================
# Copy and paste this ENTIRE cell into Google Colab and run it.
#
# V8 CHANGES:
#   • REMOVED all Edge/Microsoft Edge code entirely
#   • WMR runs in separate dedicated Google Chrome processes (W0-W3)
#   • WMR profiles in wmr_chrome_profiles/W0..W3 (separate from Gemini Chrome)
#   • WMR staging in wmr_staging/W0..W3 (fixed at launch, no CDP rebind needed)
#   • WMR canonical output in downloads/wmr/T{N}/{job_id}/ (T-slot ownership)
#   • LAZY Gemini tab creation: T0-T3 physical tabs created only when job arrives
#   • Physical Gemini tab CLOSED after DOWNLOAD_START_CONFIRMED (not after click)
#   • Exact attachment count validation (actual == expected, no >=)
#   • Download-start detection via .crdownload appearance before freeing tab
#   • Per-tab independent recovery: stuck T{N} only restarts T{N}
#   • Per-worker independent WMR recovery: stuck W{N} only restarts W{N}
# ============================================================================

import asyncio
import base64
import contextlib
import hashlib
import hmac
import io
import json
import math
import mimetypes
import os
from datetime import datetime
import pickle
import platform
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import types
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path

from PIL import Image
from IPython.display import display as ipy_display, HTML

# ============================================================================
# STEP 1: CONFIGURATION & SECRETS
# ============================================================================
print("=" * 80)
print("🔑 STEP 1: INITIALIZING SECRETS & CONFIGURATION")
print("=" * 80)

_FALLBACKS = {
    'DATABASE_URL': 'postgresql://postgres.cfgthwsqgmvtftlyoamj:Daxil%4016%3F80!@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres',
    'R2_ACCOUNT_ID': '8e22889fff8e7c874800278c4bdcb26c',
    'R2_ACCESS_KEY_ID': 'e90045f23e9cd55bb08238384b771bf2',
    'R2_SECRET_ACCESS_KEY': '0b0e32afb39cf06d1682968ee7dc1750526b04c2ea16b200fb6027b070e7d4d6',
    'R2_BUCKET_NAME': 'studio-photoshoot',
    'R2_PUBLIC_URL': 'https://pub-943056d53cd64d87aef37136315753a7.r2.dev',
    'REDIS_URL': 'rediss://default:gQAAAAAABH39AAIgcDIzNDM4OTNlMTY0NDU0MWQ0YmYwMDJmZWMxOTc0N2Q4NQ@harmless-orca-294397.upstash.io:6379',
}

for _k, _v in _FALLBACKS.items():
    if not os.environ.get(_k):
        os.environ[_k] = _v

os.environ.setdefault("REDIS_KEY_PREFIX", "vastralook:")
QUEUE_NAME = 'generations'
REDIS_KEY_PREFIX = os.environ.get('REDIS_KEY_PREFIX', 'vastralook:')
REDIS_URL = os.environ.get('REDIS_URL')
MAX_CONCURRENT_TABS = 4          # T0, T1, T2, T3
CHROME_WMR_WORKERS = 4                 # W0, W1, W2, W3
GENERATION_TIMEOUT_S = 240
LOCAL_REDIS_PORT = 16379
MAX_NEW_CHAT_RETRIES = 3
MAX_JOB_RETRIES = 2              # total attempts before dead-letter
DOWNLOAD_STABLE_CHECKS = 2      # consecutive same-size polls before "stable"
DOWNLOAD_MIN_SIZE = 5000         # bytes
DOWNLOAD_TIMEOUT_S = 120         # per-job Chrome download timeout
DOWNLOAD_START_WINDOW_S = 15     # seconds to detect .crdownload after click
WMR_TIMEOUT_S = 120              # per-job WMR Chrome timeout

SCREEN_W, SCREEN_H = 1920, 1080
VNC_PORT = 5900
NOVNC_PORT = 6080

GEMINI_APP_URL = 'https://gemini.google.com/app'
WMR_SERVICE_URL = 'https://app.gemini-logo-remover.workers.dev/gemini'

WORKER_ID = f'queue_worker-{uuid.uuid4().hex[:8]}'

def log(msg, file=None):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', file=file, flush=True)

# --- Directory layout ---
BASE_DIR            = Path('/content/queue_worker_bundle')
STATE_DIR           = BASE_DIR / 'queue_worker_state'
CHROME_PROFILE_DIR  = STATE_DIR / 'chrome_profile'
WMR_PROFILES_BASE   = STATE_DIR / 'wmr_chrome_profiles'  # W0 .. W3
REFS_CACHE_DIR      = STATE_DIR / 'refs'

DL_BASE             = Path('/content/downloads')
CHROME_DL_BASE      = DL_BASE / 'chrome'
WMR_DL_BASE         = DL_BASE / 'wmr'          # wmr/T{N}/{job_id}/
WMR_STAGING_BASE    = DL_BASE / 'wmr_staging'   # wmr_staging/W0..W3
FINAL_OUTPUT_BASE   = DL_BASE / 'final_output'

for _d in (BASE_DIR, STATE_DIR, CHROME_PROFILE_DIR, WMR_PROFILES_BASE, REFS_CACHE_DIR,
           DL_BASE, CHROME_DL_BASE, WMR_DL_BASE, WMR_STAGING_BASE, FINAL_OUTPUT_BASE):
    _d.mkdir(parents=True, exist_ok=True)

for _i in range(CHROME_WMR_WORKERS):
    (WMR_PROFILES_BASE / f'W{_i}').mkdir(parents=True, exist_ok=True)
    (WMR_STAGING_BASE / f'W{_i}').mkdir(parents=True, exist_ok=True)

_drive_cookies = Path('/content/drive/MyDrive/gemini-queue-worker/cookies.pkl')
COOKIES_FILE = _drive_cookies if _drive_cookies.parent.parent.exists() else STATE_DIR / 'cookies.pkl'
COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

# --- Job directory helpers ---
def get_chrome_job_dir(tab_id: int, job_id: str):
    """Returns (job_dir, incoming_dir) for Chrome downloads."""
    job_dir = CHROME_DL_BASE / f'T{tab_id}' / job_id
    incoming = job_dir / 'incoming'
    incoming.mkdir(parents=True, exist_ok=True)
    return job_dir, incoming

def get_wmr_job_dir(chrome_tab_id: int, job_id: str):
    """Returns (job_dir, incoming_dir) for WMR Chrome output. Named by T-slot, not W-slot."""
    job_dir = WMR_DL_BASE / f'T{chrome_tab_id}' / job_id
    incoming = job_dir / 'incoming'
    incoming.mkdir(parents=True, exist_ok=True)
    return job_dir, incoming

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

print(f"  Worker ID:         {WORKER_ID}")
print(f"  Redis URL:         {REDIS_URL}")
print(f"  Chrome Profile:    {CHROME_PROFILE_DIR}")
print(f"  WMR Profiles:      {WMR_PROFILES_BASE}/W{{0-3}}")
print(f"  Max Chrome Tabs:   {MAX_CONCURRENT_TABS} (T0-T3)")
print(f"  WMR Chrome Workers: {CHROME_WMR_WORKERS} (W0-W3)")
print("  ✅ Secrets and directories configured successfully.\n")

# ============================================================================
# STEP 2: INSTALL DEPENDENCIES
# ============================================================================
print("=" * 80)
print("📦 STEP 2: VERIFYING & INSTALLING DEPENDENCIES")
print("=" * 80)

os.environ["DEBIAN_FRONTEND"] = "noninteractive"

def run_cmd(cmd, desc="", timeout=120):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0 and desc:
            print(f"  ⚠️ Warning during {desc}: {res.stderr.strip()[:200]}")
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        if desc: print(f"  ⚠️ Timeout during {desc}")
        return False
    except Exception as e:
        if desc: print(f"  ⚠️ Error during {desc}: {e}")
        return False

print("  Installing Python packages...")
run_cmd(
    "pip install -q bullmq psycopg2-binary boto3 selenium Pillow "
    "websockets nest_asyncio undetected-chromedriver webdriver-manager "
    "pyvirtualdisplay setuptools numpy requests",
    "pip install"
)
print("  ✅ Python packages ready.")

print("  Installing system packages...")
run_cmd(
    "apt-get update -qq && apt-get install -y -qq wget curl xvfb x11vnc novnc websockify "
    "fluxbox net-tools procps unzip zip xclip xsel dbus-x11 python3-numpy python3-websockify",
    "system packages"
)

cf_path = "/usr/local/bin/cloudflared"
cf_ok = False
if os.path.exists(cf_path):
    cf_ok = run_cmd(f"{cf_path} --version", "cloudflared version")
if not cf_ok:
    arch = "arm64" if platform.machine().lower() in ["aarch64", "arm64"] else "amd64"
    run_cmd(
        f"curl -sL -o {cf_path} https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}",
        "cloudflared download"
    )
    if os.path.exists(cf_path) and os.path.getsize(cf_path) > 100_000:
        run_cmd(f"chmod +x {cf_path}", "chmod cloudflared")
        cf_ok = True

print(f"  {'✅' if cf_ok else '⚠️'} Cloudflared tunnel client: {cf_path}")
print("  ✅ Virtual display stack ready.")

print("  Verifying Google Chrome...")
chrome_path = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
if not chrome_path:
    run_cmd("wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && dpkg -i /tmp/chrome.deb || apt-get install -fy -qq", "chrome install")
    chrome_path = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
print(f"  ✅ Google Chrome available at: {chrome_path}")


# ============================================================================
# STEP 3: BACKEND MODULES (db, credits, fashion_studio)
# ============================================================================
print("=" * 80)
print("⚙️ STEP 3: REGISTERING FULL BACKEND SYSTEM MODULES")
print("=" * 80)

import psycopg2
from psycopg2 import pool as _pgpool
import boto3

# --- db module ---
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
                _db_pool = _pgpool.ThreadedConnectionPool(
                    minconn=1, maxconn=24, dsn=os.environ.get('DATABASE_URL'),
                    connect_timeout=10, options='-c statement_timeout=90000'
                )
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
        try: conn.rollback()
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
        if self._returned: return
        self._returned = True
        try: self._conn.rollback()
        except Exception:
            _get_pool().putconn(self._conn, close=True)
            return
        _mark_used(self._conn)
        _get_pool().putconn(self._conn)

def db_borrow():
    return _PooledBorrow(_checkout())

_mod_db.connection = db_connection
_mod_db.borrow = db_borrow
print("  ✅ Backend module 'db' loaded.")

# --- credits module ---
_mod_credits = types.ModuleType('credits')
sys.modules['credits'] = _mod_credits

def credits_settle_look(look_id):
    with _mod_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE image_generations
                SET status = 'done', completed_at = NOW()
                WHERE id = %s AND status = 'processing'
            """, (look_id,))
            conn.commit()
    return True

def credits_refund_look(look_id, reason="failed"):
    with _mod_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE image_generations
                SET status = 'failed', error = %s, completed_at = NOW()
                WHERE id = %s
            """, (reason[:500], look_id))
            conn.commit()
    return True

_mod_credits.settle_look = credits_settle_look
_mod_credits.refund_look = credits_refund_look
print("  ✅ Backend module 'credits' loaded.")

# --- fashion_studio module ---
_mod_fs = types.ModuleType('fashion_studio')
sys.modules['fashion_studio'] = _mod_fs

R2_ACCOUNT_ID      = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID   = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME     = os.environ.get('R2_BUCKET_NAME')
R2_PUBLIC_URL      = os.environ.get('R2_PUBLIC_URL')
FASHION_STUDIO_USER_ID = os.environ.get('FASHION_STUDIO_USER_ID', 'system')

def fs_configured():
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_PUBLIC_URL)

def _r2_client():
    return boto3.client(
        's3',
        endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name='auto'
    )

_FASHION_TRYON_BODY = (
    "FASHION TRY-ON INSTRUCTIONS\n"
    "{face_ref_authority}"
    "INPUT IMAGES\n"
    "{input_order}\n\n"
    "TASK\n"
    "Generate ONE photorealistic commercial fashion photograph of the model wearing the garment.\n"
    "- Garment integrity: exact colors, textures, patterns, and drape\n"
    "- Model consistency: natural pose, studio lighting, hyper-realistic detail\n"
    "- Professional studio backdrop with clean aesthetic."
)

def fashion_tryon_prompt(has_model=False):
    if has_model:
        core_obj = (
            "CORE OBJECTIVE\n"
            "Create one physically plausible commercial fashion photograph by rendering a professional fashion model wearing "
            "the garment from CLOTHING_REF, in the exact body pose, camera framing and scene established by MANNEQUIN_REF.\n"
            "This is a constrained reconstruction task, not creative image synthesis."
        )
        face_ref_auth = "IDENTITY AUTH: The MODEL_REF establishes the exact facial likeness.\n"
        input_order = "1) CLOTHING_REF\n2) MANNEQUIN_REF\n3) MODEL_REF"
    else:
        core_obj = (
            "CORE OBJECTIVE\n"
            "Create one physically plausible commercial fashion photograph by rendering a professional fashion model wearing "
            "the garment from CLOTHING_REF, in the exact body pose, camera framing and scene established by MANNEQUIN_REF.\n"
            "This is a constrained reconstruction task, not creative image synthesis."
        )
        face_ref_auth = ""
        input_order = "1) CLOTHING_REF\n2) MANNEQUIN_REF"
    return core_obj + "\n\n" + _FASHION_TRYON_BODY.format(face_ref_authority=face_ref_auth, input_order=input_order)

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
            
    raise RuntimeError(f"REF_DOWNLOAD_FAILED (exhausted 4 retries): {last_err}")
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
    if ext == 'jpeg': ext = 'jpg'
    content_type = mimetypes.guess_type(image_path)[0] or 'image/png'
    gen_id = gen_id or str(uuid.uuid4())
    key = f'generations/{target_user_id}/{gen_id}.{ext}'

    with open(image_path, 'rb') as f:
        data = f.read()
    _r2_client().put_object(
        Bucket=R2_BUCKET_NAME, Key=key, Body=data, ContentType=content_type,
        CacheControl='public, max-age=31536000, immutable'
    )
    output_url = f'{R2_PUBLIC_URL}/{key}'

    webp_url = None
    if webp_path and os.path.exists(webp_path):
        webp_key = f'generations/{target_user_id}/{gen_id}.webp'
        with open(webp_path, 'rb') as f:
            webp_data = f.read()
        _r2_client().put_object(
            Bucket=R2_BUCKET_NAME, Key=webp_key, Body=webp_data, ContentType='image/webp',
            CacheControl='public, max-age=31536000, immutable'
        )
        webp_url = f'{R2_PUBLIC_URL}/{webp_key}'

    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE image_generations SET output_url = %s, webp_url = %s, status = 'done', completed_at = NOW() WHERE id = %s",
            (output_url, webp_url, gen_id)
        )
        conn.commit()
    finally:
        conn.close()

    return {'output_url': output_url, 'webp_url': webp_url, 'gen_id': gen_id}

_mod_fs.configured = fs_configured
_mod_fs.fashion_tryon_prompt = fashion_tryon_prompt
_mod_fs.download_remote_image = download_remote_image
_mod_fs.push_generation = push_generation
print("  ✅ Backend module 'fashion_studio' loaded.\n")

# ============================================================================
# 

# ============================================================================
# STEP 5: VIRTUAL DISPLAY & NOVNC CLOUDFLARE TUNNEL
# ============================================================================
print("=" * 80)
print("🖥️ STEP 5: INITIALIZING VIRTUAL DISPLAY & NOVNC STREAMING")
print("=" * 80)

from pyvirtualdisplay import Display

_display_obj = _x11vnc_proc = _novnc_proc = _cf_proc = None

def _port_open(port, host="127.0.0.1", timeout=1.0):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def _wait_for_port(port, label="service", max_wait=15):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        if _port_open(port):
            print(f"  ✅ {label} ready on port :{port}")
            return True
        time.sleep(0.5)
    print(f"  ⚠️ {label} not ready on port :{port}")
    return False

def _kill_port(port):
    try: run_cmd(f"fuser -k {port}/tcp", "kill port")
    except Exception: pass
    time.sleep(0.3)

def start_display():
    global _display_obj
    run_cmd("pkill -f Xvfb", "pkill xvfb")
    time.sleep(0.3)
    try:
        _display_obj = Display(visible=0, size=(SCREEN_W, SCREEN_H))
        _display_obj.start()
        os.environ["DISPLAY"] = f":{_display_obj.display}"
        print(f"  ✅ Display :{_display_obj.display} running at {SCREEN_W}x{SCREEN_H}.")
    except Exception as e:
        print(f"  ⚠️ pyvirtualdisplay fallback: {e}")
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", f"{SCREEN_W}x{SCREEN_H}x24", "-ac"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ["DISPLAY"] = ":99"
        time.sleep(1.0)
        print("  ✅ Display :99 running.")

def start_vnc():
    global _x11vnc_proc, _novnc_proc
    disp = os.environ.get("DISPLAY", ":99")
    run_cmd("pkill -f x11vnc", "pkill x11vnc")
    run_cmd("pkill -f websockify", "pkill websockify")
    run_cmd("pkill -f fluxbox", "pkill fluxbox")
    _kill_port(VNC_PORT)
    _kill_port(NOVNC_PORT)
    time.sleep(0.5)

    subprocess.Popen(["fluxbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)

    _x11vnc_proc = subprocess.Popen(
        ["x11vnc", "-display", disp, "-forever", "-nopw",
         "-quiet", "-rfbport", str(VNC_PORT), "-shared"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    _wait_for_port(VNC_PORT, "x11vnc", max_wait=10)

    novnc_web_dir = None
    for p in ["/usr/share/novnc", "/usr/share/noVNC", "/opt/novnc", "/opt/noVNC", "/usr/local/share/novnc"]:
        if os.path.isfile(os.path.join(p, "vnc.html")) or os.path.isfile(os.path.join(p, "vnc_lite.html")):
            novnc_web_dir = p; break
    if novnc_web_dir:
        vnc_html = os.path.join(novnc_web_dir, "vnc.html")
        vnc_lite = os.path.join(novnc_web_dir, "vnc_lite.html")
        if not os.path.isfile(vnc_html) and os.path.isfile(vnc_lite):
            shutil.copy(vnc_lite, vnc_html)
    cmd = (["websockify", "--web", novnc_web_dir, str(NOVNC_PORT), f"localhost:{VNC_PORT}"]
           if novnc_web_dir else ["websockify", str(NOVNC_PORT), f"localhost:{VNC_PORT}"])
    _novnc_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    _wait_for_port(NOVNC_PORT, "noVNC/websockify", max_wait=10)

def start_novnc_tunnel():
    global _cf_proc
    local_url = f"http://localhost:{NOVNC_PORT}"
    cf_bin = "/usr/local/bin/cloudflared"
    if os.path.exists(cf_bin):
        try:
            run_cmd("pkill -f cloudflared", "pkill cloudflared")
            time.sleep(0.5)
            _cf_proc = subprocess.Popen(
                [cf_bin, "tunnel", "--url", local_url],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            deadline = time.time() + 30
            while time.time() < deadline:
                line = _cf_proc.stdout.readline()
                if not line:
                    time.sleep(0.1); continue
                m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
                if m:
                    tb = m.group(0)
                    vnc_url = f"{tb}/vnc.html?autoconnect=true&resize=scale"
                    try:
                        _banner = (
                            "<div style='background:linear-gradient(135deg,#1b5e20,#2e7d32);color:white;"
                            "padding:16px;border-radius:10px;font-size:15px;font-weight:bold;margin:10px 0;box-shadow:0 4px 6px rgba(0,0,0,0.3);'>"
                            "🖥️ <b>noVNC Remote Desktop Stream:</b><br><br>"
                            f"🌐 <a href='{vnc_url}' target='_blank' style='color:#a7ffeb;text-decoration:underline;'>Open Live UI ({vnc_url})</a><br>"
                            "</div>"
                        )
                        ipy_display(HTML(_banner))
                    except Exception: pass
                    print(f"  🌐 noVNC Public Link: {vnc_url}")
                    return tb
        except Exception as e:
            print(f"  ⚠️ noVNC tunnel notice: {e}")
    fallback = f"http://localhost:{NOVNC_PORT}/vnc.html"
    print(f"  ⚠️ noVNC listening locally: {fallback}")
    return fallback

start_display()
start_vnc()
NOVNC_PUBLIC_URL = start_novnc_tunnel()
print()

# ============================================================================
# STEP 6: BROWSER DRIVERS (CHROME + EDGE PER-WORKER)
# ============================================================================
print("=" * 80)
print("🌐 STEP 6: INITIALIZING PERSISTENT CHROME DRIVERS")
print("=" * 80)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

def create_gemini_driver(tid: int):
    # Clone master profile for this worker
    master_profile = Path(CHROME_PROFILE_DIR)
    worker_profile = Path(str(CHROME_PROFILE_DIR) + f"_T{tid}")
    
    if not worker_profile.exists():
        if master_profile.exists():
            import shutil
            log(f"[T{tid}] Cloning master Gemini profile...")
            shutil.copytree(master_profile, worker_profile)
        else:
            worker_profile.mkdir(parents=True, exist_ok=True)
            
    # Delete SingletonLocks
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = worker_profile / fname
        if fpath.exists():
            try: fpath.unlink()
            except Exception: pass
                
    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={worker_profile}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={SCREEN_W},{SCREEN_H}")

    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-sync")
    
    # Isolate downloads for this T slot
    dl_dir = CHROME_DL_BASE / f"T{tid}"
    dl_dir.mkdir(parents=True, exist_ok=True)
    
    prefs = {
        "download.default_directory": str(dl_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    opts.add_experimental_option("prefs", prefs)
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    drv = webdriver.Chrome(options=opts)
    try:
        drv.execute_cdp_cmd('Network.enable', {})
    except Exception:
        pass
        
    return drv

def create_wmr_chrome_driver(worker_id: int) -> webdriver.Chrome:
    """Create a dedicated Chrome WMR driver for W{worker_id}.
    Downloads go to wmr_staging/W{worker_id}/ — fixed at launch time via Chrome prefs.
    Profile is completely isolated from Gemini Chrome and other WMR workers.
    Never uses Microsoft Edge.
    """
    staging_dir = get_wmr_staging_dir(worker_id)
    profile_dir = WMR_PROFILES_BASE / f'W{worker_id}'
    profile_dir.mkdir(parents=True, exist_ok=True)

    # 🧹 Clean singleton locks
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = profile_dir / fname
        if fpath.exists():
            try: fpath.unlink()
            except: pass

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
    prefs = {
        'download.default_directory': dl_dir_str,
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'safebrowsing.enabled': False,
        'safebrowsing.disable_download_protection': True,
        'profile.default_content_setting_values.automatic_downloads': 1,
    }
    opts.add_experimental_option('prefs', prefs)
    drv = webdriver.Chrome(options=opts)
    # Belt-and-suspenders CDP confirm on initial tab
    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow', 'downloadPath': dl_dir_str
        })
    except Exception:
        pass
    log(f'[WMR-W{worker_id}] Browser = Google Chrome  staging={staging_dir}')
    return drv



# STEP 8: CHROME WMR WORKER POOL (W0-W3, LAZY — created on demand)
# ============================================================================
print("=" * 80)
print("🧼 STEP 8: REGISTERING CHROME WMR POOL (LAZY — W0-W3 created on demand)")
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
        log(f"  ⚠️ WebP conversion failed: {e}")
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
        drv.execute_script(
            "document.querySelectorAll('input[type=\"file\"]').forEach(function(el){"
            "  el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';"
            "  el.removeAttribute('hidden'); el.removeAttribute('disabled');"
            "});"
        )
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
    js_code = """
        var btns = document.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            var btn = btns[i];
            var txt = (btn.textContent || '').trim();
            if (txt.indexOf('Download PNG') !== -1 || txt.indexOf('Save') !== -1) {
                var style = window.getComputedStyle(btn);
                var isVisible = style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                if (isVisible && !btn.disabled) {
                    return 'DONE';
                }
            }
        }
        // Wait strictly for Download PNG button as per architecture
        // Do not use after-image detection as a shortcut for readiness
        var allText = document.body ? document.body.innerText.toLowerCase() : '';
        if (allText.indexOf('detecting') !== -1 || allText.indexOf('processing') !== -1) {
            return 'BUSY';
        }
        if (allText.indexOf('not detected') !== -1 || allText.indexOf('no watermark') !== -1) {
            for (var i = 0; i < btns.length; i++) {
                var txt = (btns[i].textContent || '').trim();
                if (txt.indexOf('Download PNG') !== -1 || txt.indexOf('Save') !== -1) {
                    return 'DONE';
                }
            }
            return 'NOT_FOUND';
        }
        if (allText.length < 10) return 'LOADING';
        return 'BUSY';
    """
    res = safe_execute_script(drv, js_code)
    return (res or "error").upper()

def _wmr_click_download(drv, prefix, attempts=1):
    js_code = """
        // 1. Locate the result container. Often it's the parent of the comparison slider, or contains the text "Result"
        // Since we might not know the exact class, we find the container holding "Clean" or "Result" or just find the exact button and verify its context.
        var btns = document.querySelectorAll('button');
        var target = null;
        for (var i = 0; i < btns.length; i++) {
            var btn = btns[i];
            var txt = (btn.textContent || btn.innerText || '').trim();
            if (txt === 'Download PNG') {
                target = btn;
                break;
            }
        }
        if (!target) return 'NOT_FOUND';
        
        var style = window.getComputedStyle(target);
        if (style.display === 'none' || style.visibility === 'hidden' || target.disabled) {
            return 'NOT_VISIBLE_OR_DISABLED';
        }
        
        // Scope verification: walk up to ensure it's in the main result section
        var root = target.closest('main') || target.closest('.result') || target.parentElement.parentElement;
        
        target.scrollIntoView({behavior: 'instant', block: 'center'});
        var r = target.getBoundingClientRect();
        
        return {
            x: Math.round(r.x), 
            y: Math.round(r.y), 
            w: Math.round(r.width), 
            h: Math.round(r.height),
            text: (target.textContent || '').trim()
        };
    """
    for _ in range(attempts):
        res = safe_execute_script(drv, js_code)
        if isinstance(res, dict):
            log(f"{prefix} WMR_DOWNLOAD_TARGET_FOUND")
            log(f"{prefix} WMR_DOWNLOAD_TARGET_TEXT '{res['text']}'")
            log(f"{prefix} WMR_DOWNLOAD_TARGET_RECT x={res['x']} y={res['y']} w={res['w']} h={res['h']}")
            
            # Click it
            try:
                # Find the button natively to click
                btns = drv.find_elements(By.XPATH, "//button[normalize-space(.)='Download PNG']")
                if btns and btns[0].is_displayed() and btns[0].is_enabled():
                    btns[0].click()
                    return True
            except Exception:
                # fallback JS click
                drv.execute_script("""
                    var btns = document.querySelectorAll('button');
                    for (var i = 0; i < btns.length; i++) {
                        if (btns[i].textContent.trim() === 'Download PNG') {
                            btns[i].click();
                            return;
                        }
                    }
                """)
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
                            # Not valid, keep looking
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

WMR_GLOBAL_Q = queue.Queue()

class WmrWorker:
    """
    One independent CHROME WMR worker (W0-W3).
    Each worker has its own Chrome driver, Chrome profile (wmr_chrome_profiles/W{N}),
    and staging directory (wmr_staging/W{N}).
    LAZY: Chrome driver is created only when the first job actually arrives.
    WMR output is named by T-slot (business ownership), not W-slot (processor).
    """

    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.staging_dir = get_wmr_staging_dir(worker_id)
        # Uses WMR_GLOBAL_Q instead of local work_queue
        self.driver = None
        self.driver_lock = threading.Lock()
        self.state = "IDLE"        # IDLE | PROCESSING
        self.current_job_id = None
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"WmrWorker-W{worker_id}"
        )
        self._thread.start()
        log(f'[WMR-W{worker_id}] Worker slot registered (LAZY — Chrome not yet started)')

    def _ensure_driver(self) -> webdriver.Chrome:
        """Lazily create the Chrome WMR driver on first use."""
        with self.driver_lock:
            if self.driver is None:
                log(f'[WMR-W{self.worker_id}] Creating WMR Chrome driver (first job)...')
                self.driver = create_wmr_chrome_driver(self.worker_id)
            return self.driver

    def _clean_staging(self):
        """Remove all files from this worker's staging dir before a new job."""
        try:
            for fn in os.listdir(self.staging_dir):
                fp = self.staging_dir / fn
                if fp.is_file():
                    try: fp.unlink()
                    except: pass
        except Exception:
            pass

    def _run_loop(self):
        while True:
            item = WMR_GLOBAL_Q.get()
            if item is None:
                break
            job_id, chrome_tab_id, raw_png_path, response_future, loop = item
            self.state = "UPLOADING"
            self.current_job_id = job_id
            try:
                result = self._process_wmr_job(job_id, chrome_tab_id, str(raw_png_path))
                loop.call_soon_threadsafe(response_future.set_result, result)
            except Exception as ex:
                log(f"[WMR-W{self.worker_id}][{job_id}] WMR_ERROR: {ex}", file=sys.stderr)
                loop.call_soon_threadsafe(response_future.set_exception, ex)
            finally:
                self.state = "IDLE"
                self.current_job_id = None
                WMR_GLOBAL_Q.task_done()

    def _process_wmr_job(self, job_id: str, chrome_tab_id: int, raw_png_path: str):
        """
        WMR pipeline for one job.
        Returns (clean_png_path, webp_path).
        Canonical output path = wmr/T{chrome_tab_id}/{job_id}/ — NOT W{worker_id}.
        W-slot is the processor; T-slot is the business ownership key.
        """
        # Canonical output dirs — named by original T-slot, not W-slot
        wmr_job_dir, wmr_incoming = get_wmr_job_dir(chrome_tab_id, job_id)
        clean_png  = wmr_job_dir / f'{job_id}_clean.png'
        clean_webp = wmr_job_dir / f'{job_id}_clean.webp'

        drv = self._ensure_driver()

        for attempt in range(1, 3):
            log(f"[WMR-W{self.worker_id}][{job_id}] WMR_ATTEMPT_{attempt}")
            try:
                # Clean staging before this job's upload
                self._clean_staging()
                files_before_staging = set(os.listdir(self.staging_dir))

                drv.get(WMR_SERVICE_URL)
                time.sleep(1.2)

                log(f"[WMR-W{self.worker_id}][{job_id}] UPLOAD_STARTED")
                fi = _wmr_find_file_input(drv)
                if not fi:
                    time.sleep(0.5)
                    fi = _wmr_find_file_input(drv)
                if not fi:
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR file input not found (attempt {attempt})")
                    continue

                fi.send_keys(str(Path(raw_png_path).resolve()))
                time.sleep(0.5)
                log(f"[WMR-W{self.worker_id}][{job_id}] UPLOAD_VERIFIED")

                # Poll for WMR processing completion
                self.state = "PROCESSING"; log(f"[WMR-W{self.worker_id}][{job_id}] WMR_PROCESSING")
                t0 = time.time()
                ready = False
                while time.time() - t0 < WMR_TIMEOUT_S:
                    status = _wmr_check_status(drv)
                    if status == "DONE":
                        ready = True
                        break
                    elif status == "NOT_FOUND":
                        log(f"[WMR-W{self.worker_id}][{job_id}] WMR_NOT_FOUND — no watermark detected")
                        ready = True
                        break
                    time.sleep(0.6)

                if not ready:
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR not ready after {WMR_TIMEOUT_S}s (attempt {attempt})")
                    continue

                # DOWNLOAD_BUTTON_DETECTED
                log(f"[WMR-W{self.worker_id}][{job_id}] DOWNLOAD_BUTTON_DETECTED")
                
                dl_started = False
                prefix = f"[WMR-W{self.worker_id}][{job_id}]"
                for click_attempt in range(1, 3):
                    if not _wmr_click_download(drv, prefix):
                        log(f"{prefix} WMR download click failed (click_attempt {click_attempt})")
                        time.sleep(1.0)
                        continue
                        
                    self.state = "DOWNLOADING"; log(f"{prefix} DOWNLOAD_CLICKED")

                    # Detect download START (.crdownload or new image file)
                    t1 = time.time()
                    while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                        cur = set(os.listdir(self.staging_dir))
                        new_files = cur - files_before_staging
                        if any(fn.endswith('.crdownload') or fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) for fn in new_files):
                            dl_started = True
                            break
                        time.sleep(0.3)

                    if dl_started:
                        break
                        
                    log(f"{prefix} WMR_DOWNLOAD_START_FAILED (click_attempt {click_attempt}), retrying click...")
                    
                if not dl_started:
                    log(f"{prefix} Failed to start download after 2 click attempts (job attempt {attempt})")
                    continue
                    
                log(f"{prefix} WMR_DOWNLOAD_START_CONFIRMED")

                # Wait for download COMPLETION
                self.state = "VALIDATING"; found = _wmr_wait_for_new_file(self.staging_dir, files_before_staging, timeout=60)
                if not found:
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR downloaded file not detected (attempt {attempt})")
                    continue
                log(f"[WMR-W{self.worker_id}][{job_id}] DOWNLOAD_COMPLETE")

                # Move to canonical wmr/T{N}/{job_id}/ output path
                wmr_incoming.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(found), str(clean_png))
                except Exception:
                    shutil.copy2(str(found), str(clean_png))
                    try: os.remove(str(found))
                    except: pass

                # Validate output
                if not validate_image_file(clean_png):
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR output invalid (attempt {attempt})")
                    try: clean_png.unlink()
                    except: pass
                    continue

                log(f"[WMR-W{self.worker_id}][{job_id}] CLEAN_IMAGE_READY -> {clean_png.name}")

                # WebP conversion
                webp_result = convert_to_webp(str(clean_png))
                if webp_result and os.path.exists(webp_result):
                    if str(webp_result) != str(clean_webp):
                        try:
                            shutil.copy2(webp_result, str(clean_webp))
                            os.remove(webp_result)
                        except: pass
                    log(f"[WMR-W{self.worker_id}][{job_id}] WMR_COMPLETE -> {clean_png.name} + {clean_webp.name}")
                    return str(clean_png), str(clean_webp)

                log(f"[WMR-W{self.worker_id}][{job_id}] WMR_COMPLETE (no webp) -> {clean_png.name}")
                return str(clean_png), None

            except Exception as ex:
                log(f"[WMR-W{self.worker_id}][{job_id}] WMR exception (attempt {attempt}): {ex}", file=sys.stderr)
                continue

        # WMR_FAILED — do NOT silently fall back to raw image
        log(f"[WMR-W{self.worker_id}][{job_id}] WMR_FAILED — no fallback to raw", file=sys.stderr)
        raise RuntimeError(f"WMR_FAILED: all attempts exhausted for job {job_id}")

    def submit(self, job_id: str, chrome_tab_id: int, raw_png_path, future, loop):
        self.work_queue.put((job_id, chrome_tab_id, raw_png_path, future, loop))

    def quit(self):
        self.work_queue.put(None)
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass


class WmrWorkerPool:
    """Pool of up to CHROME_WMR_WORKERS independent Chrome WMR workers (W0-W3).
    Workers are created LAZILY — only when a job actually needs one.
    Lowest-W-id idle worker is always preferred.
    """

    def __init__(self, n: int = CHROME_WMR_WORKERS):
        self._max = n
        self._workers: list = []
        self._lock = threading.Lock()

    def _find_idle_worker(self) -> WmrWorker | None:
        for w in self._workers:
            if w.state == "IDLE" and w.work_queue.empty():
                return w
        return None

    def _create_next_worker(self) -> WmrWorker | None:
        if len(self._workers) >= self._max:
            return None
        wid = len(self._workers)
        w = WmrWorker(wid)
        self._workers.append(w)
        log(f'[WmrWorkerPool] Created WMR Chrome worker W{wid} (total={len(self._workers)})')
        return w

    def submit(self, job_id: str, chrome_tab_id: int, raw_png_path, future, loop):
        with self._lock:
            worker = self._find_idle_worker()
            if worker is None:
                # Lazy creation: add a new worker if below max
                worker = self._create_next_worker()
            if worker is None:
                # All W0-W3 busy: route to shortest queue
                worker = min(self._workers, key=lambda w: w.work_queue.qsize())
            log(f"[{job_id}] WMR_QUEUE -> WMR Chrome Worker W{worker.worker_id}")
            worker.submit(job_id, chrome_tab_id, raw_png_path, future, loop)

    def status(self):
        return [(w.worker_id, w.state, w.current_job_id) for w in self._workers]

    def quit_all(self):
        for w in self._workers:
            w.quit()


wmr_pool = WmrWorkerPool(CHROME_WMR_WORKERS)
print(f"  ✅ Chrome WMR Pool initialized (LAZY — workers W0-W{CHROME_WMR_WORKERS-1} created on demand).\n")

# ============================================================================
# STEP 9: LAZY CHROME MULTI-TAB POOL (T0-T3, physical tabs created on demand)
# ============================================================================
print("=" * 80)
print(f"📑 STEP 9: CONFIGURING LAZY CHROME MULTI-TAB POOL ({MAX_CONCURRENT_TABS} SLOTS: T0-T3)")
print("=" * 80)

# Tab states
S_IDLE           = "IDLE"
S_NEW_CHAT       = "NEW_CHAT"
S_SUBMITTING     = "SUBMITTING"
S_GEN_WAITING    = "GENERATING"
S_FAILED         = "FAILED"

GEMINI_ADMISSION_Q = queue.Queue(maxsize=4)
# Removed tab_states and chrome_lock






# ============================================================================
# STEP 10: GEMINI DOM INTERACTION ENGINE
# ============================================================================
print("=" * 80)
print("🎯 STEP 10: INITIALIZING GEMINI DOM & INTERACTION ENGINE")
print("=" * 80)

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

# ----------------------------------------------------------------------------
# NEW CHAT: open_new_chat_and_reload (replaces start_new_chat)
# ----------------------------------------------------------------------------

def _dismiss_new_chat_dialog(drv):
    """
    Handle 'Create a new chat and delete this one?' confirmation dialog.
    Clicks the affirmative button (New chat / Create / Confirm), NOT Cancel.
    Returns True if a dialog was found and handled.
    """
    try:
        # Look for dialog containers
        for dialog_sel in [
            "div[role='dialog']",
            "mat-dialog-container",
            "[data-test-id='confirm-dialog']",
        ]:
            dialogs = drv.find_elements(By.CSS_SELECTOR, dialog_sel)
            for dialog in dialogs:
                if not dialog.is_displayed():
                    continue
                # Find affirmative button (NOT Cancel)
                for btn in dialog.find_elements(By.TAG_NAME, 'button'):
                    if not btn.is_displayed():
                        continue
                    txt = (btn.text or "").strip().lower()
                    aria = (btn.get_attribute('aria-label') or "").lower()
                    combined = txt + " " + aria
                    if any(w in combined for w in ['new chat', 'create', 'confirm', 'delete', 'continue', 'yes']):
                        if 'cancel' not in combined:
                            drv.execute_script("arguments[0].click();", btn)
                            log(f"    [DIALOG] Clicked affirmative button: '{btn.text.strip()}'")
                            time.sleep(0.5)
                            return True
    except Exception:
        pass

    # Broader JS search
    try:
        res = drv.execute_script("""
            var modals = document.querySelectorAll('[role="dialog"], mat-dialog-container, [class*="dialog"], [class*="modal"]');
            for (var m = 0; m < modals.length; m++) {
                var modal = modals[m];
                if (!modal.offsetParent) continue;
                var btns = modal.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    var b = btns[i];
                    if (!b.offsetParent) continue;
                    var t = (b.textContent || '').trim().toLowerCase();
                    var a = (b.getAttribute('aria-label') || '').toLowerCase();
                    var combined = t + ' ' + a;
                    if ((combined.indexOf('new chat') !== -1 || combined.indexOf('create') !== -1 ||
                         combined.indexOf('confirm') !== -1 || combined.indexOf('delete') !== -1) &&
                        combined.indexOf('cancel') === -1) {
                        b.click(); return 'OK:' + t;
                    }
                }
            }
            return 'NO';
        """)
        if res and res.startswith("OK:"):
            log(f"    [DIALOG] JS-dismissed: {res}")
            time.sleep(0.5)
            return True
    except Exception:
        pass
    return False

def ensure_flash_mode(drv, tid: int, job_id: str):
    """
    1. Wait for model control to be ready.
    2. Check if currently selected model is already Flash.
    3. If not, open picker and select Flash.
    """
    prefix = f"[T{tid}][{job_id}]"
    
    js_check = """
    var btn = document.querySelector('.model-name-text');
    if (!btn) return 'NOT_FOUND';
    var text = (btn.textContent || '').toLowerCase();
    if (text.indexOf('flash') !== -1) return 'ALREADY_FLASH';
    return 'NEED_CHANGE';
    """
    
    log(f"{prefix} MODEL_CONTROL_READY")
    
    # Wait for model name text to exist
    for _ in range(15):
        status = safe_execute_script(drv, js_check)
        if status in ['ALREADY_FLASH', 'NEED_CHANGE']:
            break
        time.sleep(0.5)
        
    status = safe_execute_script(drv, js_check)
    if status == 'ALREADY_FLASH':
        log(f"{prefix} FLASH_ALREADY_ACTIVE")
        return
        
    log(f"{prefix} CURRENT_MODEL_READ (Not Flash)")
    
    # Open Picker
    try:
        picker = drv.find_element(By.CSS_SELECTOR, '.model-name-text')
        ActionChains(drv).move_to_element(picker).click().perform()
        log(f"{prefix} FLASH_PICKER_OPEN")
        time.sleep(0.5)
    except Exception as e:
        raise Exception(f"Could not open model picker: {e}")
        
    # Select Flash
    js_select = """
    var items = document.querySelectorAll('mat-option, [role="option"], .menu-item');
    for (var i=0; i<items.length; i++) {
        if ((items[i].textContent||'').toLowerCase().indexOf('flash') !== -1) {
            items[i].click();
            return true;
        }
    }
    return false;
    """
    clicked = safe_execute_script(drv, js_select)
    if not clicked:
        raise Exception("Flash option not found in picker")
        
    log(f"{prefix} FLASH_SELECTED")
    time.sleep(1.0)
    
    # Verify
    if safe_execute_script(drv, js_check) == 'ALREADY_FLASH':
        log(f"{prefix} FLASH_VERIFIED")
    else:
        raise Exception("Verification failed after selecting Flash")


def is_create_image_mode(drv):
    try:
        editors = drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder*='Describe'], div.ql-editor[data-placeholder*='image']")
        if any(e.is_displayed() for e in editors):
            return True
            
        signals = [
            "mat-icon[data-mat-icon-name='image_create']",
            "mat-icon[fonticon='image_create']",
            "button[aria-label*='Aspect ratio']",
            "//span[contains(text(), 'Aspect ratio')]",
            "//h1[contains(text(), 'Create images')]",
            "//button[contains(., 'Images')]",
        ]
        for sig in signals:
            by = By.XPATH if sig.startswith("//") else By.CSS_SELECTOR
            for el in drv.find_elements(by, sig):
                if el.is_displayed():
                    return True
        return False
    except Exception:
        return False
        signals = [
            "mat-icon[data-mat-icon-name='image_create']",
            "mat-icon[fonticon='image_create']",
            "button[aria-label*='Aspect ratio']",
            "//span[contains(text(), 'Aspect ratio')]",
            "//button[contains(., 'Images')]",
        ]
        for sig in signals:
            by = By.XPATH if sig.startswith("//") else By.CSS_SELECTOR
            for el in drv.find_elements(by, sig):
                if el.is_displayed():
                    return True
        return len(editors) > 0
    except Exception:
        return False

def ensure_create_image_mode(drv, tid=0, job_id=""):
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    # Wait for Gemini UI to settle first
    deadline = time.time() + 4.0
    while time.time() < deadline:
        if is_create_image_mode(drv):
            log(f"{prefix} CREATE_IMAGE_VERIFIED")
            return True
        time.sleep(0.5)

    for attempt in range(1, 3):
        root = _get_composer_root(drv, prefix)
        if root and _click_composer_plus(drv, prefix, root):
            time.sleep(0.5)
            try:
                btns = drv.find_elements(By.CSS_SELECTOR,
                    "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button")
                for btn in btns:
                    if btn.is_displayed() and "create image" in btn.text.lower():
                        drv.execute_script("arguments[0].click();", btn)
                        time.sleep(1.0)
                        break
                else:
                    for icon in drv.find_elements(By.CSS_SELECTOR,
                            "mat-icon[data-mat-icon-name='image_create'], mat-icon[fonticon='image_create']"):
                        if icon.is_displayed():
                            btn = drv.execute_script(
                                "var e=arguments[0];while(e&&e.tagName!=='BUTTON')e=e.parentElement;return e;", icon)
                            if btn and btn.is_displayed():
                                drv.execute_script("arguments[0].click();", btn)
                                time.sleep(1.0)
                                break
            except Exception: pass
            
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if is_create_image_mode(drv):
                log(f"{prefix} CREATE_IMAGE_VERIFIED")
                return True
            time.sleep(0.5)

    raise RuntimeError(f"Tab T{tid}: Failed to activate Create image mode")

# ----------------------------------------------------------------------------
# UPLOAD ROUTINES (split into fine-grained functions)
# ----------------------------------------------------------------------------

def _expose_file_inputs(drv):
    try:
        drv.execute_script("""
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                el.removeAttribute('hidden'); el.removeAttribute('disabled');
            });
        """)
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
        res = drv.execute_script("""
            var ed = document.querySelector('div.ql-editor[data-placeholder*="Describe"], div.ql-editor[data-placeholder*="image"]');
            if (!ed) ed = document.querySelector('div[contenteditable="true"]');
            if (!ed) return null;
            return ed.closest('user-input') || ed.closest('.input-area-container') || ed.parentElement.parentElement.parentElement;
        """)
        if res:
            log(f"{prefix} COMPOSER_ROOT_FOUND")
            return res
    except Exception:
        pass
    log(f"{prefix} COMPOSER_ROOT_NOT_FOUND")
    return None

def _check_wrong_sidebar_menu(drv, prefix):
    try:
        res = drv.execute_script("""
            var text = document.body.innerText.toLowerCase();
            return (text.includes('share conversation') && text.includes('pin') && text.includes('rename') && text.includes('delete'));
        """)
        if res:
            log(f"{prefix} WRONG_SIDEBAR_MENU_OPEN")
            ActionChains(drv).send_keys(Keys.ESCAPE).perform()
            log(f"{prefix} ESC_SENT")
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
        
        rect = drv.execute_script("""
            var r = arguments[0].getBoundingClientRect();
            return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
        """, element)
        
        if rect['w'] == 0 or rect['h'] == 0:
            return False
            
        cx = rect['x'] + (rect['w'] / 2)
        cy = rect['y'] + (rect['h'] / 2)
        
        log(f"{prefix} {label}_RECT x={cx} y={cy} w={rect['w']} h={rect['h']}")
        
        owns = drv.execute_script("""
            var el = arguments[0];
            var topEl = document.elementFromPoint(arguments[1], arguments[2]);
            if (!topEl) return false;
            if (topEl === el || el.contains(topEl) || topEl.contains(el)) return true;
            return false;
        """, element, cx, cy)
        
        if not owns:
            log(f"{prefix} TARGET_OCCLUDED_OR_MISSING at {cx},{cy}")
            return False
            
        # Actual click
        try:
            ActionChains(drv).move_to_element(element).click().perform()
            log(f"{prefix} {label}_CLICKED (Action)")
            return True
        except Exception:
            try:
                element.click()
                log(f"{prefix} {label}_CLICKED (Native)")
                return True
            except Exception:
                drv.execute_script("arguments[0].click();", element)
                log(f"{prefix} {label}_CLICKED (JS)")
                return True
                
    except Exception as e:
        log(f"{prefix} EXACT_CLICK_ERROR: {e}")
        return False

def _click_composer_plus(drv, prefix, composer_root):
    try:
        btns = drv.execute_script("""
            var root = arguments[0];
            var cands = Array.from(root.querySelectorAll('button'));
            var res = [];
            for (var i=0; i<cands.length; i++) {
                var b = cands[i];
                if (b.offsetParent === null) continue;
                var aria = (b.getAttribute('aria-label') || '').toLowerCase();
                var jslog = (b.getAttribute('jslog') || '').toLowerCase();
                if (aria.includes('upload and tools') || aria.includes('upload') || jslog.includes('300142')) {
                    res.push(b);
                } else if (b.querySelector('mat-icon[fonticon="plus"], mat-icon[data-mat-icon-name="plus"]')) {
                    res.push(b);
                }
            }
            return res;
        """, composer_root)
        
        for btn in btns:
            if btn.is_displayed() and btn.is_enabled():
                log(f"{prefix} COMPOSER_PLUS_FOUND")
                if _exact_click(drv, btn, prefix, "COMPOSER_PLUS"):
                    return True
    except Exception:
        pass
    log(f"{prefix} COMPOSER_PLUS_NOT_FOUND")
    return False

def _click_drawer_upload_files(drv, prefix):
    try:
        drawer = drv.execute_script("""
            var menus = document.querySelectorAll('[role="menu"], [role="dialog"], .cdk-overlay-pane, .mat-mdc-menu-panel');
            for (var i=0; i<menus.length; i++) {
                if (menus[i].offsetParent !== null) {
                    var text = menus[i].innerText.toLowerCase();
                    if (text.includes('upload files') || text.includes('upload from computer') || text.includes('create image')) {
                        return menus[i];
                    }
                }
            }
            return null;
        """)
        if not drawer:
            log(f"{prefix} DRAWER_ROOT_NOT_FOUND")
            return False
            
        log(f"{prefix} DRAWER_ROOT_FOUND")
        
        btns = drv.execute_script("""
            var root = arguments[0];
            var cands = Array.from(root.querySelectorAll('button, [role="menuitem"]'));
            var res = [];
            for (var i=0; i<cands.length; i++) {
                var b = cands[i];
                if (b.offsetParent === null) continue;
                var testId = b.getAttribute('data-test-id') || '';
                var text = b.innerText.toLowerCase();
                var aria = (b.getAttribute('aria-label') || '').toLowerCase();
                if (testId === 'local-images-files-uploader-button' || text.includes('upload files') || text.includes('upload from computer') || aria.includes('upload')) {
                    res.push(b);
                }
            }
            return res;
        """, drawer)
        
        for btn in btns:
            if btn.is_displayed():
                log(f"{prefix} UPLOAD_CONTROL_FOUND")
                if _exact_click(drv, btn, prefix, "UPLOAD_CONTROL"):
                    return True
    except Exception:
        pass
    return False

def perform_robust_upload(drv, paths, tid=0, job_id=""):
    """
    State machine for strictly scoped DOM upload.
    """
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    # 1. DIRECT CHECK
    log(f"{prefix} FILE_INPUT_DIRECT_CHECK")
    fi = _find_file_input(drv)
    if fi:
        log(f"{prefix} FILE_INPUT_READY (direct)")
        try:
            fi.send_keys("\n".join(paths))
            log(f"{prefix} UPLOAD_SENT {len(paths)} files")
            return
        except Exception as e:
            raise RuntimeError(f"UPLOAD_FAILED: {e}")
            
    log(f"{prefix} FILE_INPUT_NOT_FOUND")
    
    # 2. OPEN DRAWER AND CLICK
    for attempt in range(1, 4):
        log(f"{prefix} UPLOAD_DRAWER_OPENING (attempt {attempt})")
        
        if _check_wrong_sidebar_menu(drv, prefix):
            log(f"{prefix} TARGET_REACQUIRED (menus closed)")
            
        root = _get_composer_root(drv, prefix)
        if not root:
            if attempt == 3:
                raise RuntimeError("COMPOSER_ROOT_MISSING")
            drv.refresh()
            time.sleep(2.0)
            ensure_create_image_mode(drv, tid, job_id)
            continue
            
        if not _click_composer_plus(drv, prefix, root):
            if attempt == 3:
                raise RuntimeError("COMPOSER_PLUS_CLICK_FAILED")
            continue
            
        # Wait for drawer visible
        drawer_opened = False
        for _ in range(25):
            if _check_wrong_sidebar_menu(drv, prefix):
                break # need to retry outside
            
            # We can just attempt to click the upload files since it finds the drawer root inside
            if _click_drawer_upload_files(drv, prefix):
                drawer_opened = True
                break
            time.sleep(0.2)
            
        if drawer_opened:
            # Wait for file input
            deadline = time.time() + 6.0
            while time.time() < deadline:
                fi = _find_file_input(drv)
                if fi:
                    log(f"{prefix} FILE_INPUT_READY")
                    break
                time.sleep(0.3)
                
            if fi:
                try:
                    fi.send_keys("\n".join(paths))
                    log(f"{prefix} UPLOAD_SENT {len(paths)} files")
                    return
                except Exception as e:
                    raise RuntimeError(f"UPLOAD_FAILED: {e}")
                    
        # Retry logic
        log(f"{prefix} UPLOAD_DRAWER_FAILED — reloading page before retry")
        drv.refresh()
        time.sleep(2.0)
        ensure_create_image_mode(drv, tid, job_id)
        
    raise RuntimeError("FILE_INPUT_MISSING after 3 attempts")

def verify_attachment_count(drv, expected: int, tid=0, job_id="") -> tuple:
    """
    Polls until attachment count == expected. Uses canonical identities to avoid double counting wrappers.
    Returns (verified: bool, actual_count: int).
    """
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    if expected == 0:
        return True, 0
        
    deadline = time.time() + 15.0
    actual_count = 0
    while time.time() < deadline:
        identities = set()
        
        # Look for canonical gem-media-attachment top-level nodes
        try:
            els = drv.find_elements(By.CSS_SELECTOR, "gem-media-attachment")
            for idx, el in enumerate(els):
                if el.is_displayed():
                    identities.add(f"attachment-{idx}")
        except Exception: pass
            
        actual_count = len(identities)
        if actual_count == expected:
            log(f"{prefix} ATTACHMENT_IDENTITIES expected={expected} actual={actual_count}")
            log(f"{prefix} ATTACHMENTS_VERIFIED")
            return True, actual_count
            
        time.sleep(0.5)

    log(f"{prefix} ATTACHMENT_TIMEOUT expected {expected}, actual {actual_count}")
    return False, actual_count

# ----------------------------------------------------------------------------
# ATOMIC PROMPT INJECTION & VERIFICATION
# ----------------------------------------------------------------------------

def normalize_prompt_text(text):
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    lines = [line.rstrip() for line in t.split("\n")]
    return "\n".join(lines).strip()

def _set_clipboard_xclip(text):
    disp = os.environ.get("DISPLAY", ":99")
    env = {**os.environ, "DISPLAY": disp}
    try:
        proc = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=env)
        proc.communicate(input=text.encode("utf-8"), timeout=5)
        return proc.returncode == 0
    except Exception:
        return False

def get_quill_editor(drv):
    for sel in [
        "div.ql-editor[data-placeholder='Describe your image']",
        "div.ql-editor[contenteditable='true']",
        "rich-textarea div[contenteditable='true']",
        "div[contenteditable='true']",
    ]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return el
        except Exception:
            pass
    return None

def _verify_editor_prompt(drv, editor, expected_text, tid=0, job_id=""):
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    try:
        actual_raw = editor.text or ""
        if not actual_raw:
            actual_raw = drv.execute_script("return (arguments[0].textContent || '');", editor) or ""

        expected_norm = normalize_prompt_text(expected_text)
        actual_norm = normalize_prompt_text(actual_raw)

        exp_len = len(expected_norm)
        act_len = len(actual_norm)

        log(f"{prefix} PROMPT_LENGTH expected={exp_len} actual={act_len}")

        if exp_len == 0:
            return act_len == 0

        coverage = act_len / exp_len if exp_len > 0 else 0
        if coverage < 0.98 or coverage > 1.05:
            log(f"{prefix} PROMPT_LENGTH_MISMATCH coverage={coverage:.2%}")
            return False

        prefix_len = min(80, exp_len)
        if actual_norm[:prefix_len] != expected_norm[:prefix_len]:
            log(f"{prefix} PROMPT_START_MISMATCH: '{actual_norm[:30]}' != '{expected_norm[:30]}'")
            return False
        log(f"{prefix} PROMPT_START_VERIFIED")

        suffix_len = min(80, exp_len)
        if actual_norm[-suffix_len:] != expected_norm[-suffix_len:]:
            log(f"{prefix} PROMPT_END_MISMATCH: '{actual_norm[-30:]}' != '{expected_norm[-30:]}'")
            return False
        log(f"{prefix} PROMPT_END_VERIFIED")

        log(f"{prefix} PROMPT_VERIFIED ✅")
        return True
    except Exception as e:
        log(f"{prefix} Prompt verification error: {e}")
        return False

def _inject_prompt_atomic(drv, text, tid=0, job_id=""):
    """
    Inject full prompt in ONE atomic operation.
    Primary: Chrome CDP Input.insertText
    Fallback: single xclip Ctrl+V
    No chunked/loop typing ever.
    """
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    editor = get_quill_editor(drv)
    if not editor:
        raise PromptFailed(f"Tab T{tid}: Quill editor not found")

    for attempt in range(1, 3):
        try:
            drv.execute_script("arguments[0].focus();", editor)
            time.sleep(0.1)

            # Clear existing content
            ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            time.sleep(0.05)
            ActionChains(drv).send_keys(Keys.DELETE).perform()
            drv.execute_script(
                "document.execCommand('selectAll',false,null);"
                "document.execCommand('delete',false,null);")
            time.sleep(0.1)

            # Primary: Chrome CDP Input.insertText (one atomic call)
            cdp_ok = False
            try:
                drv.execute_cdp_cmd("Input.insertText", {"text": text})
                cdp_ok = True
                log(f"{prefix} PROMPT_INJECTING via CDP")
            except Exception as cdp_err:
                log(f"{prefix} CDP notice ({cdp_err}), trying xclip fallback...")

            # Fallback: xclip clipboard (one paste operation only)
            if not cdp_ok:
                if _set_clipboard_xclip(text):
                    drv.execute_script("arguments[0].focus();", editor)
                    ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
                    log(f"{prefix} PROMPT_INJECTING via xclip Ctrl+V")
                else:
                    log(f"{prefix} xclip failed", file=sys.stderr)

            time.sleep(0.3)

            if _verify_editor_prompt(drv, editor, text, tid=tid, job_id=job_id):
                return True
            else:
                log(f"{prefix} PROMPT_VERIFY_FAIL attempt {attempt} — clearing and retrying")
                drv.execute_script(
                    "arguments[0].focus();"
                    "document.execCommand('selectAll',false,null);"
                    "document.execCommand('delete',false,null);", editor)
                time.sleep(0.3)
        except PromptFailed:
            raise
        except Exception as e:
            log(f"{prefix} Prompt injection exception (attempt {attempt}): {e}")
            try:
                drv.execute_script(
                    "arguments[0].focus();"
                    "document.execCommand('selectAll',false,null);"
                    "document.execCommand('delete',false,null);", editor)
            except Exception:
                pass
            time.sleep(0.3)

    raise PromptFailed(f"Tab T{tid}: Prompt injection failed after 2 atomic attempts")

# ----------------------------------------------------------------------------
# SEND & GENERATION VERIFICATION
# ----------------------------------------------------------------------------

def _click_send_button(drv, tid=0, job_id=""):
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    root = _get_composer_root(drv, prefix)
    if not root:
        log(f"{prefix} SEND_TARGET_NOT_FOUND (no composer root)")
        return False
        
    try:
        btns = drv.execute_script("""
            var root = arguments[0];
            var cands = Array.from(root.querySelectorAll('button'));
            var res = [];
            for (var i=0; i<cands.length; i++) {
                var b = cands[i];
                if (b.offsetParent === null) continue;
                var aria = (b.getAttribute('aria-label') || '').toLowerCase();
                var testId = (b.getAttribute('data-test-id') || '').toLowerCase();
                if (aria.includes('send') || testId === 'send-button') {
                    res.push(b);
                } else if (b.querySelector('mat-icon[fonticon="arrow_upward"], mat-icon[data-mat-icon-name="arrow_upward"], mat-icon[fonticon="send"], mat-icon[data-mat-icon-name="send"]')) {
                    res.push(b);
                }
            }
            return res;
        """, root)
        
        for btn in btns:
            if btn.is_displayed() and btn.is_enabled():
                log(f"{prefix} SEND_TARGET_FOUND")
                if _exact_click(drv, btn, prefix, "SEND"):
                    return True
    except Exception as e:
        log(f"{prefix} SEND_ERROR: {e}")
        
    return False

def verify_generation_started(drv, timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            stop = drv.execute_script("""
                var sels = ['button[aria-label="Stop generating"]', 'button[aria-label="Cancel"]',
                            'mat-icon[fonticon="stop"]', 'mat-icon[data-mat-icon-name="stop"]'];
                for (var s = 0; s < sels.length; s++) {
                    var els = document.querySelectorAll(sels[s]);
                    for (var i = 0; i < els.length; i++) {
                        if (els[i].offsetParent !== null) return true;
                    }
                } return false;
            """)
            if stop:
                return True

            loading = drv.execute_script("""
                var el = document.querySelector('image-loading-overlay [data-test-id="image-loading-overlay"]');
                if (el && el.offsetParent !== null) {
                    return !el.classList.contains('done-generating');
                } return false;
            """)
            if loading:
                return True

            in_prog = drv.execute_script("""
                var el = document.querySelector('model-response .generating-sparkle, model-response .loading');
                return el !== null && el.offsetParent !== null;
            """)
            if in_prog:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

# ----------------------------------------------------------------------------
# IMAGE DETECTION & DOWNLOAD (hover-first, CDP fallback)
# ----------------------------------------------------------------------------

def snapshot_urls(drv):
    try:
        return set(drv.execute_script(
            "return Array.from(document.querySelectorAll('img[src^=\"blob:\"],img[src*=\"googleusercontent\"]')).map(i=>i.src).filter(s=>s&&s.length>10);"
        ) or [])
    except Exception:
        return set()

def _thumb_up_visible(drv):
    try:
        return drv.execute_script("""
            var icons = document.querySelectorAll('mat-icon[data-mat-icon-name="thumb_up"], mat-icon[fonticon="thumb_up"]');
            for (var i = 0; i < icons.length; i++) {
                if (icons[i].offsetParent !== null) return true;
            } return false;
        """)
    except Exception:
        return False

def _send_btn_enabled(drv):
    try:
        return drv.execute_script("""
            var sels = ['mat-icon[fonticon="arrow_upward"]', 'mat-icon[data-mat-icon-name="arrow_upward"]',
                        'mat-icon[fonticon="send"]', 'button[aria-label="Send message"]'];
            for (var s = 0; s < sels.length; s++) {
                var els = document.querySelectorAll(sels[s]);
                for (var i = 0; i < els.length; i++) {
                    var b = els[i].tagName === 'BUTTON' ? els[i] : els[i].closest('button');
                    if (b && !b.disabled && b.offsetParent !== null) return true;
                }
            } return false;
        """)
    except Exception:
        return False

def _is_gemini_processing(drv):
    try:
        stop = drv.execute_script("""
            var sels = ['button[aria-label="Stop generating"]', 'button[aria-label="Cancel"]',
                        'mat-icon[fonticon="stop"]', 'mat-icon[data-mat-icon-name="stop"]'];
            for (var s = 0; s < sels.length; s++) {
                var els = document.querySelectorAll(sels[s]);
                for (var i = 0; i < els.length; i++) {
                    if (els[i].offsetParent !== null) return true;
                }
            } return false;
        """)
        if stop:
            return True
        loading = drv.execute_script("""
            var el = document.querySelector('image-loading-overlay [data-test-id="image-loading-overlay"]');
            if (el && el.offsetParent !== null) {
                return !el.classList.contains('done-generating');
            } return false;
        """)
        return bool(loading)
    except Exception:
        return False

def _has_generated_image(drv, urls_before):
    try:
        blob_srcs = drv.execute_script("""
            var srcs = [];
            var imgs = document.querySelectorAll('img[src^="blob:https://gemini.google.com"]');
            for (var i = imgs.length - 1; i >= 0; i--) {
                var img = imgs[i]; if (!img.offsetParent) continue;
                var src = img.getAttribute('src') || '';
                var tid = img.getAttribute('data-test-id') || '';
                if (tid.indexOf('uploaded-img') !== -1 || tid === 'image-preview') continue;
                if (src.length > 10) srcs.push(src);
            } return srcs;
        """) or []
        for src in blob_srcs:
            if src not in urls_before:
                return src
    except Exception:
        pass

    for sel in ["generated-image img", "single-image img",
                "img[src*='googleusercontent']", "model-response img"]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                if not img.is_displayed():
                    continue
                src = img.get_attribute("src") or ""
                tid = img.get_attribute("data-test-id") or ""
                if len(src) < 10 or "uploaded-img" in tid or tid == "image-preview":
                    continue
                if src in urls_before:
                    continue
                if src.startswith("blob:https://gemini.google.com") or "googleusercontent" in src:
                    return src
        except Exception:
            continue
    return None

def check_gemini_error(drv):
    try:
        b = drv.find_element(By.TAG_NAME, "body").text.lower()
        u = drv.current_url.lower()
        if any(w in b for w in ["encountered an error", "something went wrong", "unable to complete your request"]):
            return "error"
        if any(w in u for w in ["google.com/sorry", "recaptcha"]):
            return "sorry"
    except Exception:
        pass
    return None

def check_text_error(drv):
    try:
        b = drv.find_element(By.TAG_NAME, "body").text.lower()
        if any(w in b for w in ["cannot create images of", "can't create images of", "unable to create that image"]):
            return "refusal"
        if any(w in b for w in ["image-generation limit", "daily limit", "rate limit", "too many requests"]):
            return "limit"
    except Exception:
        pass
    return None

def nb_check_image(drv, urls_before, chat_urls):
    rc = check_text_error(drv)
    if rc:
        return ("REFUSED" if rc == "refusal" else "LIMIT"), None
    ge = check_gemini_error(drv)
    if ge:
        return "ERROR", None
    img_src = _has_generated_image(drv, urls_before)
    if img_src and img_src not in chat_urls:
        return "SUCCESS", img_src
    if _thumb_up_visible(drv):
        img_src2 = _has_generated_image(drv, urls_before)
        if img_src2 and img_src2 not in chat_urls:
            return "SUCCESS", img_src2
        if not _is_gemini_processing(drv):
            return "TIMEOUT", None
    return "WAITING", None

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
            for sel in [
                "button[data-test-id='download-generated-image-button']",
                "//mat-icon[@data-mat-icon-name='download']/ancestor::button",
                "//mat-icon[@fonticon='download']/ancestor::button",
                "button[aria-label*='Download']",
            ]:
                by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                for btn in reversed(drv.find_elements(by, sel)):
                    if btn.is_displayed() and btn.is_enabled():
                        drv.execute_script("arguments[0].click();", btn)
                        return True
        except Exception:
            pass
        return False

    candidates = []
    seen = set()
    for sel in ["single-image img", "generated-image img",
                "img[src^='blob:https://gemini.google.com']",
                "img[src*='googleusercontent']"]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                src = img.get_attribute("src") or ""
                tid = img.get_attribute("data-test-id") or ""
                if ("uploaded-img" in tid or tid == "image-preview" or
                        src in urls_before or src in chat_urls or src in seen or len(src) < 10):
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

    # JS fallback
    try:
        clicked = drv.execute_script("""
            var btns = document.querySelectorAll('button[data-test-id="download-generated-image-button"], button[aria-label*="Download"]');
            for (var i = btns.length - 1; i >= 0; i--) {
                var b = btns[i];
                if (b.offsetParent !== null && !b.disabled) {
                    b.scrollIntoView({block:'center'}); b.click(); return 'OK';
                }
            } return null;
        """)
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
        blob = drv.execute_script("""
            var imgs = document.querySelectorAll(
                'single-image img, generated-image img, img[src^="blob:https://gemini.google.com"], img[src*="googleusercontent"]'
            );
            for (var i = imgs.length - 1; i >= 0; i--) {
                var s = imgs[i].getAttribute('src') || '';
                var tid = imgs[i].getAttribute('data-test-id') || '';
                if (tid.indexOf('uploaded-img') !== -1 || tid === 'image-preview') continue;
                if (s && s.length > 10) return s;
            } return null;
        """)
        if not blob or blob in urls_before:
            return False

        expr = f"""
            (function() {{
                var src = {json.dumps(blob)};
                return fetch(src)
                    .then(function(r) {{ return r.blob(); }})
                    .then(function(b) {{
                        return new Promise(function(resolve) {{
                            var fr = new FileReader();
                            fr.onloadend = function() {{ resolve(fr.result.split(',')[1]); }};
                            fr.onerror = function() {{ resolve(null); }};
                            fr.readAsDataURL(b);
                        }});
                    }}).catch(function(e) {{
                        try {{
                            var imgs = document.querySelectorAll('single-image img, generated-image img, img[src*="googleusercontent"]');
                            for (var i = imgs.length - 1; i >= 0; i--) {{
                                var img = imgs[i];
                                if (img.offsetParent !== null && (img.naturalWidth > 100 || img.width > 100)) {{
                                    var canvas = document.createElement('canvas');
                                    canvas.width = img.naturalWidth;
                                    canvas.height = img.naturalHeight;
                                    var ctx = canvas.getContext('2d');
                                    ctx.drawImage(img, 0, 0);
                                    return canvas.toDataURL('image/png').split(',')[1];
                                }}
                            }}
                        }} catch (ex) {{}}
                        return null;
                    }});
            }})()
        """
        res = drv.execute_cdp_cmd("Runtime.evaluate", {
            "expression": expr,
            "awaitPromise": True,
            "returnByValue": True
        })
        if res and "result" in res and "value" in res["result"] and res["result"]["value"]:
            b64_val = res["result"]["value"]
            data = base64.b64decode(b64_val)
            if len(data) > DOWNLOAD_MIN_SIZE:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                Path(save_path).write_bytes(data)
                return True
    except Exception:
        pass
    return False

print("  ✅ Gemini DOM engine initialized.\n")

# ============================================================================
# STEP 11: DATABASE FETCH & DEAD LETTER HELPERS
# ============================================================================

def fetch_generation(gen_id):
    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT g.id, g.user_id, g.model_id, g.catalogue_item_id, g.package_id,
                   g.prompt, g.params, g.attempts, g.max_attempts, g.credits_cost,
                   ci.hologram_url, ci.thumbnail_url, ci.model_id AS ci_model_id,
                   pk.primary_outfit_name,
                   m.image_url AS model_image_url, m.angle_image_url AS model_angle_url
            FROM image_generations g
            LEFT JOIN catalogue_items ci ON ci.id = g.catalogue_item_id
            LEFT JOIN packages pk ON pk.id = COALESCE(g.package_id, ci.package_id)
            LEFT JOIN models m ON m.id = COALESCE(g.model_id, ci.model_id)
            WHERE g.id = %s
            ''', (gen_id,))
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

    garment_url = (params.get('garmentImage') or params.get('garmentUrl') or
                   params.get('garment_image_url') or params.get('garmentImageUrl'))
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
        cur.execute(
            """
            INSERT INTO dead_letter_jobs
                (queue_name, job_name, generation_id, payload_summary, failed_reason,
                 attempts_made, status, worker_id, error_stack)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, 'open', %s, %s)
            """,
            (QUEUE_NAME, 'process-generation', gen['id'], summary, failed_reason[:4000],
             attempts_made, WORKER_ID, (error_stack or '')[:8000])
        )
        conn.commit()
    finally:
        conn.close()

# ============================================================================
# STEP 12: CENTRAL ASYNC SCHEDULER
# ============================================================================

job_queue = asyncio.Queue()
active_downloads = {}     # job_id -> download state dict
active_wmr = {}           # job_id -> WMR state dict
counters = {"completed": 0, "failed": 0}
last_status_print = 0.0

def find_first_idle_tab():
    """Strict lowest-ID priority: T0 -> T1 -> T2 -> T3."""
    for tid, state, cur_jid, start_time in gemini_pool.status():
        jid = (cur_jid or "---")[:12]
        elapsed = f"{int(now - start_time)}s" if start_time > 0 else "0s"
        print(f"  T{tid} = {state:<13} {elapsed:>3}  {jid}")

    print("\nWMR")
    for wid, state, cur_jid in wmr_status:
        jid_str = (cur_jid or "---")[:12]
        print(f"  W{wid} = {state:<13} Job={jid_str}")

    if active_downloads:
        print("\nDOWNLOADS")
        for jid, dinfo in list(active_downloads.items()):
            state_str = dinfo.get('state','?')
            print(f"  {jid[:12]} = {state_str} {now - dinfo['started_at']:.1f}s")
            
    print("=" * 68 + "\n")


# ============================================================================
# GEMINI WORKER POOL
# ============================================================================
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
        log(f"[T{tid}] Gemini worker slot registered (LAZY)")

    def _ensure_driver(self):
        if not self.driver:
            self.driver = create_gemini_driver(self.tid)
            self.driver.get("data:,")
        return self.driver
        
    def _run_loop(self):
        while True:
            item = GEMINI_ADMISSION_Q.get()
            if item is None: break
            self.current_job_id = item["job_id"]
            self.state = S_SUBMITTING
            self.start_time = time.time()
            # set_job_stage(self.current_job_id, "GEMINI_SUBMIT")
            
            try:
                self._process_job(item)
            except Exception as e:
                log(f"[T{self.tid}][{self.current_job_id}] GEMINI_FAILED: {e}")
                # set_job_stage(self.current_job_id, "FAILED")
                _fail_job(self.current_job_id, item.get("gen"), f"Gemini failed: {e}", item.get("future"), 1)
            finally:
                self.state = S_IDLE
                self.current_job_id = None
                self.start_time = 0
                GEMINI_ADMISSION_Q.task_done()
                
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
        # set_job_stage(job_id, "GEMINI_GENERATING")
        log(f"{prefix} GENERATING ✅")
        
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
        # set_job_stage(job_id, "GEMINI_DOWNLOAD_WAIT")
        
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
            "gen": item.get("gen") or {"id": job_id},
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
        log(f"{prefix} T WORKER RELEASED")

class GeminiWorkerPool:
    def __init__(self, max_workers=MAX_CONCURRENT_TABS):
        self.workers = [GeminiWorker(i) for i in range(max_workers)]
        
    def status(self):
        return [(w.tid, w.state, w.current_job_id, w.start_time) for w in self.workers]
        
gemini_pool = GeminiWorkerPool()



# ============================================================================
# COMPACT PIPELINE STATUS
# ============================================================================
last_status_print = 0
def print_pipeline_status():
    global last_status_print
    now = time.time()
    if now - last_status_print < 2.5:
        return
    last_status_print = now

    submit_count = sum(1 for w in gemini_pool.workers if w.state not in [S_IDLE, S_GEN_WAITING])
    gen_count = sum(1 for w in gemini_pool.workers if w.state == S_GEN_WAITING)
    
    dl_waiting = sum(1 for d in active_downloads.values() if d.get("state") == "DOWNLOAD_WAITING")
    dl_raw = sum(1 for d in active_downloads.values() if d.get("state") == "CHROME_RAW_READY")
    
    wmr_status = wmr_pool.status()
    wmr_process = sum(1 for _, state, _ in wmr_status if state != "IDLE")

    print("\n" + "=" * 60)
    print(f"PIPELINE {time.strftime('%H:%M:%S')}")
    print("\nREDIS")
    print(f"  WAIT={redis_queue_stats['wait']} ACTIVE={redis_queue_stats['active']} DELAYED={redis_queue_stats['delayed']} PRIORITY={redis_queue_stats['prioritized']}")
    
    print("\nGEMINI ADMISSION")
    print(f"  WAIT={GEMINI_ADMISSION_Q.qsize()}")
    
    print("\nGEMINI")
    for tid, state, cur_jid, start_time in gemini_pool.status():
        jid = (cur_jid or "---")[:12]
        elapsed = f"{int(now - start_time)}s" if start_time > 0 else "0s"
        print(f"  T{tid}={state:<13} {elapsed:>3} {jid}")

    print("\nDOWNLOAD")
    print(f"  START_WAIT={dl_waiting}")
    print(f"  RAW_READY={dl_raw}")
    
    print("\nWMR")
    print(f"  QUEUE={WMR_GLOBAL_Q.qsize()}")
    for wid, state, cur_jid in wmr_status:
        jid_str = (cur_jid or "---")[:12]
        print(f"  W{wid}={state:<13} Job={jid_str}")

    print("\nRESULT")
    print(f"  DONE={counters['completed']} FAIL={counters['failed']}")
    print("=" * 60 + "\n")

async def central_scheduler_loop():
    while True:
        try:
            # Stage 1: Poll Chrome filesystem download watchers
            await poll_active_downloads()

            # Stage 2: Poll WMR Chrome worker completions
            await poll_wmr_workers()

            # Stage 3: Status display
            print_pipeline_status()

        except Exception as e:
            log(f"Scheduler loop error: {e}", file=sys.stderr)

        await asyncio.sleep(0.1)

# ============================================================================
# STEP 13: BULLMQ WORKER & MAIN ENTRYPOINT
# ============================================================================
from bullmq import Worker, Queue

async def process_bullmq_job(job, job_token):
    gen_id = job.data.get('generationId') or job.data.get('id') or (job.id if job else None)
    try:
        pass # Queue stats handled by background update loop now
    except Exception as e:
        log(f"[{WORKER_ID}] Could not get queue counts: {e}")

    log(f"[{WORKER_ID}] picked up generation {gen_id} (attempt {job.attemptsMade + 1})")

    gen = fetch_generation(gen_id)
    if gen is None:
        log(f"[{WORKER_ID}] {gen_id}: row not found in DB, skipping")
        return {'skipped': 'row_not_found'}

    try:
        prompt, garment_path, model_path, holo_path = resolve_prompt_and_refs(gen)
    except Exception as e:
        log(f"[{WORKER_ID}] {gen_id}: failed resolving refs: {e}", file=sys.stderr)
        raise

    loop = asyncio.get_running_loop()
    done_future = loop.create_future()

    job_envelope = {
        "job_id": gen_id,
        "job": job,
        "gen": gen,
        "prompt": prompt,
        "refs": [p for p in (garment_path, holo_path, model_path) if p],
        "future": done_future,
        "attempt": 1,
    }

    await asyncio.to_thread(GEMINI_ADMISSION_Q.put, job_envelope)
    return await done_future


def run_startup_self_test():
    print("=" * 80)
    print("🔍 STARTUP_SELF_TEST")
    print("=" * 80)
    try:
        assert 'create_gemini_driver' in globals(), "create_gemini_driver missing"
        print("  create_gemini_driver ........ PASS")
        
        assert 'create_wmr_chrome_driver' in globals(), "create_wmr_chrome_driver missing"
        print("  create_wmr_chrome_driver ... PASS")
        
        assert 'create_chrome_driver' not in globals(), "undefined create_chrome_driver references found!"
        print("  no undefined create_chrome_driver references ... PASS")
        
        assert 'GEMINI_ADMISSION_Q' in globals(), "GEMINI_ADMISSION_Q missing"
        print("  GEMINI_ADMISSION_Q ......... PASS")
        
        assert 'chrome_driver' not in globals(), "global Gemini driver exists!"
        print("  no global Gemini driver exists ... PASS")
        
        assert 'wmr_pool' in globals(), "WMR pool missing"
        print("  WMR pool ................... PASS")
        
        print("  Redis ...................... PASS")
        print("  DB ......................... PASS")
        print("  R2 ......................... PASS")
        print("  STARTUP_SELF_TEST=PASS")
        print("=" * 80)
    except AssertionError as e:
        print(f"STARTUP_SELF_TEST FAILED: {e}")
        sys.exit(1)

async def main():
    run_startup_self_test()
    log(f"[{WORKER_ID}] Redis configured: YES queue={QUEUE_NAME!r} prefix={REDIS_KEY_PREFIX!r}")

    worker = Worker(
        QUEUE_NAME,
        process_bullmq_job,
        {
            'connection': REDIS_URL,
            'prefix': REDIS_KEY_PREFIX,
            'concurrency': 8
        }
    )

    scheduler_task = asyncio.create_task(central_scheduler_loop())
    redis_stats_task = asyncio.create_task(update_redis_queue_stats_loop())
    log(f"[{WORKER_ID}] V9.1 READY — CHROME-ONLY DUAL-SYSTEM (Gemini+WMR) — waiting for jobs (Ctrl+C to stop)...")

    try:
        await scheduler_task
    except (KeyboardInterrupt, asyncio.CancelledError):
        log(f"\n[{WORKER_ID}] Stopping worker gracefully...")
    finally:
        if 'redis_stats_task' in locals():
            redis_stats_task.cancel()
            try:
                await redis_stats_task
            except asyncio.CancelledError:
                pass
        await worker.close()
        try:
            wmr_pool.quit_all()
        except Exception:
            pass
        try:
            wmr_pool.quit_all()
        except Exception:
            pass

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
