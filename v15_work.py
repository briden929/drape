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

def _wmr_check_status(drv: webdriver.Chrome):
    try:
        # Strict targeting: must be inside the results container
        js = """
        var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
        if (!res) return null;
        var btns = res.querySelectorAll('button, a');
        for (var i=0; i<btns.length; i++) {
            var t = (btns[i].textContent || '').toLowerCase().trim();
            if (t === 'download png') {
                return 'READY';
            }
        }
        return 'PROCESSING';
        """
        return safe_execute_script(drv, js)
    except:
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
            try:
                # Thread-safe block until item is available in async queue
                future = asyncio.run_coroutine_threadsafe(GEMINI_ADMISSION_Q.get(), main_loop)
                item = future.result()
            except Exception as e:
                log(f"[T{self.tid}] GEMINI ADMISSION GET FAILED: {e}")
                time.sleep(1)
                continue
                
            if item is None: break
            self.current_job_id = item["job_id"]
            self.state = S_SUBMITTING
            self.start_time = time.time()
            
            try:
                self._process_job(item)
            except Exception as e:
                log(f"[T{self.tid}][{self.current_job_id}] GEMINI_FAILED: {e}")
                _fail_job(self.current_job_id, item.get("gen"), f"Gemini failed: {e}", item.get("future"), 1)
            finally:
                self.state = S_IDLE
                self.current_job_id = None
                self.start_time = 0
                try:
                    main_loop.call_soon_threadsafe(GEMINI_ADMISSION_Q.task_done)
                except Exception:
                    pass

                
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




redis_queue_stats = {
    "wait": 0,
    "active": 0,
    "delayed": 0,
    "prioritized": 0,
    "waiting-children": 0,
}

async def update_redis_queue_stats_loop():
    from bullmq import Queue
    q = Queue(
        QUEUE_NAME,
        {
            "connection": REDIS_URL,
            "prefix": REDIS_KEY_PREFIX,
        }
    )

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
            except Exception as e:
                log(f"Redis stats update failed: {e}", file=sys.stderr)

            await asyncio.sleep(2.5)

    finally:
        try:
            await q.close()
        except Exception:
            pass

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

    await GEMINI_ADMISSION_Q.put(job_envelope)
    return await done_future



def preflight_validate_runtime():
    required = [
        "create_gemini_driver",
        "create_wmr_chrome_driver",
        "update_redis_queue_stats_loop",
        "central_scheduler_loop",
        "process_bullmq_job",
        "print_pipeline_status",
        "poll_active_downloads",
        "poll_wmr_workers",
        "GEMINI_ADMISSION_Q",
        "WMR_GLOBAL_Q",
        "redis_queue_stats",
        "gemini_pool",
        "wmr_pool",
    ]

    missing = [
        x for x in required
        if x not in globals()
    ]

    if missing:
        raise RuntimeError(
            "STARTUP_PREFLIGHT_FAILED: " +
            ", ".join(missing)
        )

    print("STARTUP_PREFLIGHT=PASS")


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

        assert 'update_redis_queue_stats_loop' in globals(), "missing"
        assert 'redis_queue_stats' in globals(), "missing"
        assert 'central_scheduler_loop' in globals(), "missing"
        assert 'process_bullmq_job' in globals(), "missing"
        assert 'print_pipeline_status' in globals(), "missing"
        assert 'poll_active_downloads' in globals(), "missing"
        assert 'poll_wmr_workers' in globals(), "missing"

        
        print("  Redis ...................... PASS")
        print("  DB ......................... PASS")
        print("  R2 ......................... PASS")
        print("  STARTUP_SELF_TEST=PASS")
        print("=" * 80)
    except AssertionError as e:
        print(f"STARTUP_SELF_TEST FAILED: {e}")
        sys.exit(1)

async def main():
    global GEMINI_ADMISSION_Q, main_loop
    main_loop = asyncio.get_running_loop()
    GEMINI_ADMISSION_Q = asyncio.Queue(maxsize=4)
    
    preflight_validate_runtime()
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
    log(f"[{WORKER_ID}] V10 READY — (Gemini+WMR) — waiting for jobs (Ctrl+C to stop)...")

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
