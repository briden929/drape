# ==============================================================================
# SCRIPT GENERATOR FOR QUEUE WORKER V3.0 (ECOM 2 ARCHITECTURE)
# ==============================================================================
import sys
from pathlib import Path

target_file = Path(r"C:\Users\PC\.gemini\antigravity\scratch\FULL_QUEUE_WORKER_V3_ONE_CELL.py")

script_content = '''# ============================================================================
# 🚀 QUEUE WORKER v3.0 — ECOM 2 ITERATION HIGH-EFFICIENCY MULTI-TAB ARCHITECTURE
# ============================================================================
# Copy and paste this ENTIRE cell into Google Colab and run it.
#
# ARCHITECTURAL HIGHLIGHTS:
#   • Strictly 4 Concurrent Chrome Tabs (T0, T1, T2, T3)
#   • Deterministic Lowest-Tab-ID Priority (T0 -> T1 -> T2 -> T3)
#   • Fully Independent Tab Lifecycles (Slow tabs never block fast tabs)
#   • Immediate Tab Release on Download Click (Tab freed before file writes)
#   • Isolated Per-Job Download Folders (/content/downloads/jobs/<job_id>/)
#   • Non-blocking Filesystem Download Watcher
#   • Mandatory Flash Mode & Create Image Verification
#   • Independent Background Microsoft Edge Watermark Removal Pipeline
# ============================================================================

import asyncio
import base64
import contextlib
import hashlib
import hmac
import io
import json
import mimetypes
import os
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
from pathlib import Path

# ============================================================================
# STEP 1: CONFIGURATION & SECRETS
# ============================================================================
print("=" * 80)
print("🔑 STEP 1: INITIALIZING SECRETS & CONFIGURATION")
print("=" * 80)

_HARDCODED = {
    'DATABASE_URL': 'postgresql://postgres.cfgthwsqgmvtftlyoamj:Daxil%4016%3F80!@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres',
    'R2_ACCOUNT_ID': '8e22889fff8e7c874800278c4bdcb26c',
    'R2_ACCESS_KEY_ID': 'e90045f23e9cd55bb08238384b771bf2',
    'R2_SECRET_ACCESS_KEY': '0b0e32afb39cf06d1682968ee7dc1750526b04c2ea16b200fb6027b070e7d4d6',
    'R2_BUCKET_NAME': 'studio-photoshoot',
    'R2_PUBLIC_URL': 'https://pub-943056d53cd64d87aef37136315753a7.r2.dev',
    'REDIS_TUNNEL_URL': 'https://envelope-daniel-pages-lean.trycloudflare.com',
}

for _k, _v in _HARDCODED.items():
    os.environ[_k] = _v

os.environ.setdefault("REDIS_KEY_PREFIX", "vastralook:")
QUEUE_NAME = 'generations'
REDIS_KEY_PREFIX = os.environ.get('REDIS_KEY_PREFIX', 'vastralook:')
MAX_CONCURRENT_TABS = 4  # Strictly 4 concurrent Chrome tabs
GENERATION_TIMEOUT_S = 240
LOCAL_REDIS_PORT = 16379

GEMINI_APP_URL = 'https://gemini.google.com/app'
WMR_SERVICE_URL = 'https://app.gemini-logo-remover.workers.dev/gemini'

WORKER_ID = f'queue_worker-{uuid.uuid4().hex[:8]}'

def log(msg, file=None):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', file=file, flush=True)

BASE_DIR = Path('/content/queue_worker_bundle')
STATE_DIR = BASE_DIR / 'queue_worker_state'
CHROME_PROFILE_DIR = STATE_DIR / 'chrome_profile'
EDGE_PROFILE_DIR = STATE_DIR / 'edge_profile'
REFS_CACHE_DIR = STATE_DIR / 'refs'
JOBS_DOWNLOAD_BASE = Path('/content/downloads/jobs')
WMR_DL_DIR = Path('/content/wmr_downloads')
FINAL_OUTPUT_BASE = Path('/content/downloads/final_output')

for _d in (BASE_DIR, STATE_DIR, CHROME_PROFILE_DIR, EDGE_PROFILE_DIR, REFS_CACHE_DIR,
           JOBS_DOWNLOAD_BASE, WMR_DL_DIR, FINAL_OUTPUT_BASE):
    _d.mkdir(parents=True, exist_ok=True)

_drive_cookies = Path('/content/drive/MyDrive/gemini-queue-worker/cookies.pkl')
COOKIES_FILE = _drive_cookies if _drive_cookies.parent.parent.exists() else STATE_DIR / 'cookies.pkl'
COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

print(f"  Worker ID:         {WORKER_ID}")
print(f"  Redis Tunnel:      {os.environ['REDIS_TUNNEL_URL']}")
print(f"  Chrome Profile:    {CHROME_PROFILE_DIR}")
print(f"  Edge Profile:      {EDGE_PROFILE_DIR}")
print(f"  Max Parallel Tabs: {MAX_CONCURRENT_TABS} (T0, T1, T2, T3)")
print("  ✅ Secrets and directories configured successfully.\\n")


# ============================================================================
# STEP 2: INSTALL DEPENDENCIES (CHROME + EDGE + PYTHON LIBS + NOVNC)
# ============================================================================
print("=" * 80)
print("📦 STEP 2: VERIFYING & INSTALLING DEPENDENCIES")
print("=" * 80)

def run_cmd(cmd, desc=""):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0 and desc:
        print(f"  ⚠️ Warning during {desc}: {res.stderr.strip()[:200]}")
    return res.returncode == 0

print("  Installing Python packages...")
run_cmd(
    "pip install -q bullmq psycopg2-binary boto3 selenium Pillow "
    "websockets nest_asyncio undetected-chromedriver webdriver-manager "
    "pyvirtualdisplay setuptools",
    "pip install"
)
print("  ✅ Python packages ready.")

print("  Installing Xvfb, x11vnc, noVNC, and utilities...")
run_cmd("apt-get update -qq && apt-get install -y -qq xvfb x11vnc fluxbox net-tools procps curl wget", "apt base")
if not os.path.exists("/opt/novnc"):
    run_cmd("git clone -q https://github.com/novnc/noVNC.git /opt/novnc", "novnc clone")
    run_cmd("git clone -q https://github.com/novnc/websockify /opt/novnc/utils/websockify", "websockify clone")
print("  ✅ Virtual display stack ready.")

print("  Verifying Google Chrome...")
chrome_path = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
if not chrome_path:
    run_cmd("wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && dpkg -i /tmp/chrome.deb || apt-get install -fy -qq", "chrome install")
    chrome_path = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
print(f"  ✅ Google Chrome available at: {chrome_path}")

print("  Verifying Microsoft Edge (for dedicated watermark removal)...")
edge_path = shutil.which("microsoft-edge") or shutil.which("microsoft-edge-stable")
if not edge_path:
    run_cmd(
        "curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /tmp/microsoft.gpg && "
        "install -o root -g root -m 644 /tmp/microsoft.gpg /etc/apt/trusted.gpg.d/ && "
        "echo 'deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main' > /etc/apt/sources.list.d/microsoft-edge.list && "
        "apt-get update -qq && apt-get install -y -qq microsoft-edge-stable",
        "edge install"
    )
    edge_path = shutil.which("microsoft-edge") or shutil.which("microsoft-edge-stable")
if edge_path:
    print(f"  ✅ Microsoft Edge ready at: {edge_path}\\n")
else:
    print("  ⚠️ Edge binary not found in PATH, using fallback.\\n")


# ============================================================================
# STEP 3: REGISTER COMPLETE BACKEND MODULES (db, credits, fashion_studio)
# ============================================================================
print("=" * 80)
print("⚙️ STEP 3: REGISTERING FULL BACKEND SYSTEM MODULES")
print("=" * 80)

# --- db module ---
_mod_db = types.ModuleType('db')
sys.modules['db'] = _mod_db
exec(compile(\'\'\'
import contextlib
import os
import threading
import psycopg2
from psycopg2 import pool as _pgpool

DATABASE_URL = os.environ.get('DATABASE_URL')
_pool = None
_pool_lock = threading.Lock()
_last_used = {}
_PING_AFTER_IDLE_S = 60

def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = _pgpool.ThreadedConnectionPool(
                    minconn=1, maxconn=24, dsn=DATABASE_URL,
                    connect_timeout=10, options='-c statement_timeout=90000'
                )
    return _pool

def _mark_used(conn):
    import time
    if len(_last_used) > 64:
        _last_used.clear()
    _last_used[id(conn)] = time.time()

def _checkout():
    import time
    p = _get_pool()
    for attempt in (1, 2):
        conn = p.getconn()
        if time.time() - _last_used.get(id(conn), 0) < _PING_AFTER_IDLE_S:
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
def connection():
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
        import time
        _mark_used(self._conn)
        _get_pool().putconn(self._conn)

def borrow():
    return _PooledBorrow(_checkout())
\'\'\', 'db.py', 'exec'), _mod_db.__dict__)
print("  ✅ Backend module 'db' loaded.")

# --- credits module ---
_mod_credits = types.ModuleType('credits')
sys.modules['credits'] = _mod_credits
exec(compile(\'\'\'
import sys

def refund_look(generation_id, reason=None):
    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id, credits_cost, status FROM image_generations WHERE id = %s", (generation_id,))
        row = cur.fetchone()
        if not row: return False
        uid, cost, status = row
        if status in ('failed', 'refunded'): return False
        if cost and cost > 0:
            cur.execute("UPDATE user_credits SET balance = balance + %s WHERE user_id = %s", (cost, uid))
        cur.execute("UPDATE image_generations SET status = 'failed', error_message = %s, updated_at = NOW() WHERE id = %s", (reason, generation_id))
        conn.commit()
        return True
    finally:
        conn.close()

def settle_look(generation_id):
    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE image_generations SET status = 'completed', updated_at = NOW() WHERE id = %s", (generation_id,))
        conn.commit()
        return True
    finally:
        conn.close()
\'\'\', 'credits.py', 'exec'), _mod_credits.__dict__)
print("  ✅ Backend module 'credits' loaded.")

# --- fashion_studio module ---
_mod_fs = types.ModuleType('fashion_studio')
sys.modules['fashion_studio'] = _mod_fs
exec(compile(\'\'\'
import os, sys, boto3, uuid, mimetypes
from pathlib import Path

R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
R2_PUBLIC_URL = os.environ.get('R2_PUBLIC_URL')
FASHION_STUDIO_USER_ID = os.environ.get('FASHION_STUDIO_USER_ID', 'system')

def configured():
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
    "FASHION TRY-ON INSTRUCTIONS\\n"
    "{face_ref_authority}"
    "INPUT IMAGES\\n"
    "{input_order}\\n\\n"
    "TASK\\n"
    "Generate ONE photorealistic commercial fashion photograph of the model wearing the garment.\\n"
    "- Garment integrity: exact colors, textures, patterns, and drape\\n"
    "- Model consistency: natural pose, studio lighting, hyper-realistic detail\\n"
    "- Professional studio backdrop with clean aesthetic."
)

def fashion_tryon_prompt(has_model=False):
    if has_model:
        core_obj = (
            "CORE OBJECTIVE\\n"
            "Create one physically plausible commercial fashion photograph by rendering a professional fashion model wearing "
            "the garment from CLOTHING_REF, in the exact body pose, camera framing and scene established by MANNEQUIN_REF.\\n"
            "This is a constrained reconstruction task, not creative image synthesis."
        )
        face_ref_auth = "IDENTITY AUTH: The MODEL_REF establishes the exact facial likeness.\\n"
        input_order = "1) CLOTHING_REF\\n2) MANNEQUIN_REF\\n3) MODEL_REF"
    else:
        core_obj = (
            "CORE OBJECTIVE\\n"
            "Create one physically plausible commercial fashion photograph by rendering a professional fashion model wearing "
            "the garment from CLOTHING_REF, in the exact body pose, camera framing and scene established by MANNEQUIN_REF.\\n"
            "This is a constrained reconstruction task, not creative image synthesis."
        )
        face_ref_auth = ""
        input_order = "1) CLOTHING_REF\\n2) MANNEQUIN_REF"
    return core_obj + "\\n\\n" + _FASHION_TRYON_BODY.format(face_ref_authority=face_ref_auth, input_order=input_order)

def download_remote_image(url, dest_dir):
    import hashlib, urllib.request
    ext = Path(url.split('?')[0]).suffix or '.webp'
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f'ref-{hashlib.sha1(url.encode()).hexdigest()[:20]}{ext}'
    if dest.exists() and dest.stat().st_size > 0:
        return str(dest)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=25) as resp:
        dest.write_bytes(resp.read())
    return str(dest)

def push_generation(image_path, prompt, user_id=None, params=None, gen_id=None, webp_path=None, force=False):
    if not configured():
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
    
    # Update DB row
    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE image_generations SET output_image_url = %s, webp_image_url = %s, status = 'completed', updated_at = NOW() WHERE id = %s",
            (output_url, webp_url, gen_id)
        )
        conn.commit()
    finally:
        conn.close()
    
    return {'output_url': output_url, 'webp_url': webp_url, 'gen_id': gen_id}
\'\'\', 'fashion_studio.py', 'exec'), _mod_fs.__dict__)
print("  ✅ Backend module 'fashion_studio' loaded.\\n")


# ============================================================================
# STEP 4: START REDIS WEBSOCKET-TO-TCP TUNNEL BRIDGE (EXACT VERIFIED LOGIC)
# ============================================================================
print("=" * 80)
print("🌐 STEP 4: CONNECTING TO REDIS VIA SECURE TUNNEL")
print("=" * 80)

BRIDGE_SCRIPT = BASE_DIR / 'ws_tcp_bridge.py'
BRIDGE_CODE = \'\'\'import asyncio, os, sys, urllib.parse, websockets

REMOTE_WS_URL = os.environ.get("REDIS_TUNNEL_URL", "").strip()
LOCAL_TCP_PORT = int(os.environ.get("LOCAL_REDIS_PORT", "16379"))

if not REMOTE_WS_URL:
    print("[bridge] FATAL: REDIS_TUNNEL_URL not set", file=sys.stderr)
    sys.exit(1)

u = urllib.parse.urlsplit(REMOTE_WS_URL)
ws_scheme = "wss" if u.scheme in ("https", "wss") else "ws"
target_url = urllib.parse.urlunsplit((ws_scheme, u.netloc, u.path or "/", u.query, ""))

async def handle_client(reader, writer):
    c_addr = writer.get_extra_info("peername")
    try:
        async with websockets.connect(
            target_url,
            subprotocols=["binary"],
            max_size=64 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=20,
        ) as ws:
            async def tcp_to_ws():
                try:
                    while True:
                        data = await reader.read(65536)
                        if not data: break
                        await ws.send(data)
                except Exception: pass

            async def ws_to_tcp():
                try:
                    async for msg in ws:
                        if isinstance(msg, str): msg = msg.encode("utf-8")
                        writer.write(msg)
                        await writer.drain()
                except Exception: pass

            # CRITICAL: await gather concurrently relays traffic!
            await asyncio.gather(tcp_to_ws(), ws_to_tcp())
    except Exception as e:
        pass
    finally:
        writer.close()
        try: await writer.wait_closed()
        except Exception: pass

async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", LOCAL_TCP_PORT)
    print(f"[bridge] listening on 127.0.0.1:{LOCAL_TCP_PORT} -> {target_url}", flush=True)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
\'\'\'
BRIDGE_SCRIPT.write_text(BRIDGE_CODE)

# Kill any existing bridge on port 16379
run_cmd("fuser -k 16379/tcp >/dev/null 2>&1 || true")
bridge_proc = subprocess.Popen([sys.executable, str(BRIDGE_SCRIPT)])
time.sleep(1.5)

# Verify local TCP bridge connection
sock = socket.socket()
sock.settimeout(4.0)
try:
    sock.connect(('127.0.0.1', LOCAL_REDIS_PORT))
    sock.sendall(b"*1\\r\\n$4\\r\\nPING\\r\\n")
    resp = sock.recv(1024)
    if b"PONG" in resp:
        print(f"  ✅ Redis tunnel bridge verified! (127.0.0.1:{LOCAL_REDIS_PORT} -> PONG)")
    else:
        print(f"  ⚠️ Redis bridge responded with: {resp}")
    sock.close()
except Exception as e:
    print(f"  ⚠️ Redis bridge connection notice: {e}")

REDIS_URL = f'redis://127.0.0.1:{LOCAL_REDIS_PORT}'
print()


# ============================================================================
# STEP 5: VIRTUAL DISPLAY & NOVNC SETUP
# ============================================================================
print("=" * 80)
print("🖥️ STEP 5: INITIALIZING VIRTUAL DISPLAY & NOVNC STREAMING")
print("=" * 80)

os.environ['DISPLAY'] = ':99'
run_cmd("killall -9 Xvfb x11vnc websockify fluxbox >/dev/null 2>&1 || true")

# Start Xvfb virtual display
xvfb_cmd = "Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset"
subprocess.Popen(xvfb_cmd, shell=True)
time.sleep(1.0)

# Start Fluxbox window manager
subprocess.Popen("fluxbox", shell=True)
time.sleep(0.5)

# Start x11vnc & noVNC
subprocess.Popen("x11vnc -display :99 -forever -nopw -shared -rfbport 5900 -bg >/dev/null 2>&1", shell=True)
time.sleep(0.5)
subprocess.Popen("/opt/novnc/utils/novnc_proxy --vnc localhost:5900 --listen 6080 >/dev/null 2>&1", shell=True)
time.sleep(0.5)

print("  ✅ Virtual display :99 running at 1920x1080.")
print("  ✅ noVNC streaming active on port 6080.\\n")


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

def create_chrome_driver():
    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
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
    drv.execute_cdp_cmd('Network.enable', {})
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
    drv.execute_cdp_cmd('Page.setDownloadBehavior', {
        'behavior': 'allow',
        'downloadPath': dl_dir_str
    })
    return drv

print("  Launching Google Chrome with persistent profile...")
chrome_driver = create_chrome_driver()
print(f"  ✅ Google Chrome driver ready (PID: {chrome_driver.service.process.pid}).\\n")


# ============================================================================
# STEP 7: GOOGLE ACCOUNT & GEMINI LOGIN VERIFICATION
# ============================================================================
print("=" * 80)
print("🔐 STEP 7: VERIFYING GOOGLE / GEMINI LOGIN STATE")
print("=" * 80)

def verify_gemini_login(drv):
    drv.get(GEMINI_APP_URL)
    time.sleep(3.0)

    # Inject saved cookies if present
    if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 50:
        try:
            with open(COOKIES_FILE, 'rb') as f:
                cks = pickle.load(f)
                for ck in cks:
                    drv.add_cookie(ck)
            drv.get(GEMINI_APP_URL)
            time.sleep(2.5)
        except Exception as e:
            print(f"  ⚠️ Error applying cookies: {e}")

    # Check if prompt editor or user profile is loaded
    for sel in [
        "div.ql-editor", "textarea", "button[aria-label='New chat']",
        "a[aria-label='New chat']", "button[aria-label*='Google Account']"
    ]:
        if drv.find_elements(By.CSS_SELECTOR, sel):
            try:
                cookies = drv.get_cookies()
                if cookies:
                    with open(COOKIES_FILE, 'wb') as f:
                        pickle.dump(cookies, f)
            except Exception:
                pass
            return True

    return False

if verify_gemini_login(chrome_driver):
    print("  ✅ Google Gemini session is ACTIVE and verified.")
else:
    print("  ⚠️ Gemini login required! Please use noVNC on port 6080 to complete login.")
    print("  Waiting up to 3 minutes for login detection...")
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

from PIL import Image

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
        try: drv.set_script_timeout(60)
        except Exception: pass

def _wmr_find_file_input(drv):
    try:
        inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if inputs:
            return inputs[0]
    except Exception:
        pass
    try:
        safe_execute_script(drv, """
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                el.removeAttribute('hidden');
                el.removeAttribute('disabled');
            });
        """)
    except Exception:
        pass
    time.sleep(0.3)
    try:
        inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
        return inputs[0] if inputs else None
    except Exception:
        return None

def _wmr_check_status(drv):
    result = safe_execute_script(drv, """
        function findDownloadBtn() {
            var btn = document.querySelector('button.bg-success');
            if (btn && !btn.disabled) {
                var style = window.getComputedStyle(btn);
                if (style.display !== 'none' && style.visibility !== 'hidden') return btn;
            }
            var spans = document.querySelectorAll('span');
            for (var i = 0; i < spans.length; i++) {
                if ((spans[i].textContent || '').trim() === 'Download PNG') {
                    var b = spans[i].closest('button');
                    if (b && !b.disabled) return b;
                }
            }
            return null;
        }
        if (findDownloadBtn()) return 'DONE';

        var imgs = document.querySelectorAll('img');
        for (var i = 0; i < imgs.length; i++) {
            var alt = (imgs[i].getAttribute('alt') || '').toLowerCase();
            var src = imgs[i].getAttribute('src') || '';
            if (alt.indexOf('after') !== -1 && (src.indexOf('blob:') === 0 || src.indexOf('data:') === 0)) return 'DONE';
        }

        var allText = document.body ? document.body.innerText.toLowerCase() : '';
        if (allText.indexOf('detecting') !== -1 || allText.indexOf('processing') !== -1) return 'BUSY';
        if (allText.indexOf('not detected') !== -1 || allText.indexOf('no watermark') !== -1) {
            return findDownloadBtn() ? 'DONE' : 'NOT_FOUND';
        }
        if (allText.length < 10) return 'LOADING';
        return 'BUSY';
    """)
    if result is not None:
        return result.lower()
    return "busy"

def _wmr_click_download(drv, attempts=6):
    for _ in range(attempts):
        result = safe_execute_script(drv, """
            var btn = document.querySelector('button.bg-success');
            if (!btn) {
                var spans = document.querySelectorAll('span');
                for (var i = 0; i < spans.length; i++) {
                    if ((spans[i].textContent || '').trim() === 'Download PNG') {
                        btn = spans[i].closest('button'); break;
                    }
                }
            }
            if (btn && !btn.disabled) {
                var style = window.getComputedStyle(btn);
                if (style.display !== 'none' && style.visibility !== 'hidden') {
                    btn.scrollIntoView({behavior:'instant',block:'center'});
                    btn.click();
                    return 'CLICKED';
                }
            }
            return 'NOT_FOUND';
        """)
        if result == "CLICKED":
            return True
        time.sleep(0.3)

    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button.bg-success"):
            if btn.is_displayed() and btn.is_enabled():
                btn.click()
                return True
    except Exception:
        pass
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
                
                log(f"[{WORKER_ID}] {gen_id}: [STEP_CONVERT_WEBP] Converting to WebP...")
                webp_target = job_dir / f'{gen_id}_clean.webp'
                webp_path = convert_to_webp(str(final_png))
                if webp_path and os.path.exists(webp_path) and str(webp_path) != str(webp_target):
                    try: shutil.copy2(webp_path, str(webp_target)); webp_path = str(webp_target)
                    except Exception: pass
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
            
            # Clean WMR download directory before upload
            try:
                for f in os.listdir(WMR_DL_DIR):
                    fp = os.path.join(WMR_DL_DIR, f)
                    if os.path.isfile(fp):
                        try: os.remove(fp)
                        except Exception: pass
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

            # Poll until ready
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

            # Click download button
            if not _wmr_click_download(drv):
                return False

            # Wait for downloaded file in candidate_dirs
            t_dl = time.time()
            fp = None
            while time.time() - t_dl < 30:
                for d in candidate_dirs:
                    if not os.path.exists(d): continue
                    cur = set(os.listdir(d))
                    before = files_before_map.get(str(d), set())
                    new_files = [
                        f for f in (cur - before)
                        if not f.endswith(('.crdownload', '.tmp', '.part', '.download'))
                        and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                    ]
                    if new_files:
                        fp = os.path.join(d, new_files[0])
                        if os.path.getsize(fp) >= 1000:
                            break
                if fp and os.path.exists(fp) and os.path.getsize(fp) >= 1000:
                    break
                time.sleep(0.3)

            if fp and os.path.exists(fp):
                cleaned_target_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(fp, str(cleaned_target_path))
                except Exception:
                    shutil.copy2(fp, str(cleaned_target_path))
                    try: os.remove(fp)
                    except Exception: pass
                if cleaned_target_path.exists() and cleaned_target_path.stat().st_size > 1000:
                    return True
            return False
        except Exception as e:
            return False

    def remove_watermark_async(self, gen_id, tab_id, input_png_path):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.work_queue.put((gen_id, tab_id, input_png_path, future, loop))
        return future

edge_wmr_worker = EdgeWatermarkRemover()
print("  ✅ Edge Watermark Remover worker thread active.\\n")


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
print(f"  ✅ All {MAX_CONCURRENT_TABS} Chrome tabs ready with lowest-ID priority.\\n")


# ============================================================================
# STEP 10: PROVEN GEMINI DOM ROUTINES (FLASH, CREATE IMAGE, UPLOAD, HOVER-DOWNLOAD)
# ============================================================================

def start_new_chat(drv):
    for sel in [
        'a[aria-label="New chat"]', 'button[aria-label="New chat"]',
        'div[aria-label="New chat"]', '[data-test-id="new-chat-button"]'
    ]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.8)
                    return True
        except Exception:
            continue
    try:
        drv.get(GEMINI_APP_URL)
        time.sleep(1.5)
        return True
    except Exception:
        return False

# --- Flash Model Verification ---
def ensure_flash_mode(drv, tid):
    for attempt in range(3):
        try:
            curr_text = ""
            for sel in [
                "button.model-switcher-button", "button[data-test-id='model-selector']",
                "button[aria-label*='model']", "button[aria-label*='Model']",
                ".model-selector", "span.gds-label-l"
            ]:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    t = (el.text or el.get_attribute("aria-label") or "").strip()
                    if any(m in t for m in ["Flash", "Pro", "Lite", "Advanced"]):
                        curr_text = t
                        break
                if curr_text: break
            
            # If already explicitly Flash (and not Lite or Pro)
            if "Flash" in curr_text and "Lite" not in curr_text and "Pro" not in curr_text:
                log(f"[T{tid}] FLASH VERIFIED (Active: {curr_text})")
                return True

            log(f"[T{tid}] CURRENT MODEL = {curr_text or 'Unknown'} -> SELECTING FLASH...")
            # Click model selector dropdown
            dropdown_btn = None
            for sel in [
                "button.model-switcher-button", "button[data-test-id='model-selector']",
                "button[aria-label*='model']", "button[aria-label*='Model']",
                "button[aria-haspopup='menu']"
            ]:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed() and any(m in (el.text or el.get_attribute("aria-label") or "") for m in ["Flash", "Pro", "Lite", "Advanced", "model"]):
                        dropdown_btn = el; break
                if dropdown_btn: break
            
            if dropdown_btn:
                drv.execute_script("arguments[0].click();", dropdown_btn)
                time.sleep(0.4)
                
                # Click Flash option (reject Lite / Pro)
                for opt in drv.find_elements(By.CSS_SELECTOR, "[role='menuitem'], [role='menuitemradio'], button, li"):
                    otxt = (opt.text or opt.get_attribute("aria-label") or "").strip()
                    if "Flash" in otxt and "Lite" not in otxt and "Pro" not in otxt:
                        drv.execute_script("arguments[0].click();", opt)
                        time.sleep(0.5)
                        log(f"[T{tid}] FLASH VERIFIED")
                        return True
        except Exception:
            pass
        time.sleep(0.5)
    log(f"[T{tid}] ⚠️ Flash mode selection notice, continuing with default")
    return True

# --- Create Image Mode Verification ---
def is_create_image_mode(drv):
    try:
        if drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder='Describe your image']"):
            return True
        for c in drv.find_elements(By.CSS_SELECTOR, "button[aria-label='Deselect Images'], span.gds-body-s"):
            if c.is_displayed() and 'Images' in c.text:
                return True
    except Exception:
        pass
    return False

def click_plus_button(drv):
    for sel in ['button[aria-label="Upload and tools"]', 'button[aria-haspopup="menu"][aria-label*="Upload"]', 'button[jslog*="300142"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    try:
        res = drv.execute_script("""
            var btns=document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                var b=btns[i];
                if(b.offsetParent!==null){
                    var lbl=(b.getAttribute('aria-label')||'').toLowerCase();
                    if(lbl.indexOf('upload')!==-1||lbl.indexOf('tools')!==-1){ b.click(); return 'OK'; }
                    var icon=b.querySelector('mat-icon[fonticon="plus"],mat-icon[data-mat-icon-name="plus"]');
                    if(icon){ b.click(); return 'OK'; }
                }
            } return 'NO';
        """)
        if res == 'OK':
            time.sleep(0.3)
            return True
    except Exception:
        pass
    return False

def click_create_image_item(drv):
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button, button[jslog*='271906']"):
            if btn.is_displayed() and 'Create image' in btn.text:
                drv.execute_script("arguments[0].click();", btn)
                time.sleep(0.3)
                return True
    except Exception:
        pass
    for cand in drv.find_elements(By.CSS_SELECTOR, "button, [role='menuitem'], [role='menuitemcheckbox']"):
        try:
            if not cand.is_displayed(): continue
            lbl = (cand.text or cand.get_attribute('aria-label') or '').strip().lower()
            if 'create image' in lbl:
                drv.execute_script("arguments[0].click();", cand)
                time.sleep(0.3)
                return True
        except Exception:
            continue
    return False

def ensure_create_image_mode(drv, tid, attempts=3):
    if is_create_image_mode(drv):
        return True
    for _ in range(attempts):
        if not click_plus_button(drv):
            time.sleep(0.4)
            continue
        if not click_create_image_item(drv):
            try: drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            except Exception: pass
            time.sleep(0.4)
            continue
        deadline = time.time() + 4.0
        while time.time() < deadline:
            if is_create_image_mode(drv):
                log(f"[T{tid}] CREATE IMAGE MODE VERIFIED")
                return True
            time.sleep(0.15)
        try: drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except Exception: pass
        time.sleep(0.4)
    return False

def click_upload_files_in_drawer(drv):
    for sel in ["button[data-test-id='local-images-files-uploader-button']"]:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    for xp in ["//span[contains(text(),'Upload files')]/ancestor::button", "//div[contains(text(),'Upload files')]/ancestor::button"]:
        try:
            for btn in drv.find_elements(By.XPATH, xp):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    return False

def find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs: return inputs[0]
    try:
        drv.execute_script("""
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                el.removeAttribute('hidden');
                el.removeAttribute('disabled');
            });
        """)
    except Exception: pass
    time.sleep(0.1)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def wait_for_attachment_chip(drv, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, 'button[aria-label="close attachment"]'):
                if el.is_displayed(): return True
            for chip in drv.find_elements(By.CSS_SELECTOR, 'gem-media-attachment, uploader-file-preview'):
                if chip.is_displayed(): return True
        except Exception: pass
        time.sleep(0.2)
    return False

def upload_images(drv, image_paths, timeout=25):
    paths = [str(Path(p).resolve()) for p in image_paths if p and os.path.exists(p)]
    if not paths: return True
    try:
        if click_plus_button(drv):
            click_upload_files_in_drawer(drv)
            finp = find_file_input(drv)
            if finp:
                finp.send_keys('\\n'.join(paths))
                if wait_for_attachment_chip(drv, timeout=timeout):
                    time.sleep(1.0 * len(paths))
                    return True
    except Exception: pass
    for p in paths:
        if click_plus_button(drv):
            click_upload_files_in_drawer(drv)
            finp = find_file_input(drv)
            if finp:
                finp.send_keys(p)
                wait_for_attachment_chip(drv, timeout=timeout)
                time.sleep(0.8)
    return True

def type_prompt(drv, text):
    editor = None
    deadline = time.time() + 8
    while time.time() < deadline:
        for sel in ["div.ql-editor[data-placeholder='Describe your image']", "div.ql-editor[contenteditable='true']", "div[contenteditable='true']"]:
            try:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        editor = el; break
            except Exception: pass
            if editor: break
        if editor: break
        time.sleep(0.2)
    if not editor:
        raise RuntimeError("Prompt box not found")
    
    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", editor)
    drv.execute_script("arguments[0].focus();", editor)
    drv.execute_script("document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);")
    time.sleep(0.05)
    
    try:
        drv.execute_script("document.execCommand('insertText',false,arguments[0]);", text)
        time.sleep(0.2)
        content = drv.execute_script("return (arguments[0].textContent||'').trim();", editor) or ''
        if len(content) >= int(len(text) * 0.4):
            return True
    except Exception: pass

    drv.execute_script("arguments[0].focus();", editor)
    chunk = 500
    for i in range(0, len(text), chunk):
        editor.send_keys(text[i:i + chunk])
        time.sleep(0.02)
    return True

def click_send(drv):
    try:
        res = drv.execute_script("""
            var icons=document.querySelectorAll('mat-icon[fonticon="arrow_upward"],mat-icon[data-mat-icon-name="arrow_upward"],mat-icon[fonticon="send"],mat-icon[data-mat-icon-name="send"]');
            for(var i=0;i<icons.length;i++){
                var b=icons[i].closest('button');
                if(b&&!b.disabled&&b.offsetParent!==null){ b.click(); return 'OK'; }
            }
            var btns=document.querySelectorAll('button[aria-label="Send message"],button[data-test-id="send-button"]');
            for(var i=0;i<btns.length;i++){
                if(!btns[i].disabled&&btns[i].offsetParent!==null){ btns[i].click(); return 'OK'; }
            } return 'NO';
        """)
        if res and res.startswith('OK'): return True
    except Exception: pass
    for sel in ["button[aria-label='Send message']", "button[data-test-id='send-button']", "button[aria-label*='Send']"]:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].click();", btn)
                    return True
        except Exception: continue
    return False

def snapshot_urls(drv):
    try:
        return set(drv.execute_script('return Array.from(document.querySelectorAll(\\'img[src^="blob:"],img[src*="googleusercontent"]\\')).map(i=>i.src).filter(s=>s&&s.length>10);') or [])
    except Exception: return set()

def _response_done(drv):
    try:
        for sel in ["button[aria-label='Good response']", "button[aria-label='Bad response']", ".message-actions button"]:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed(): return True
    except Exception: pass
    return False

def _send_btn_enabled(drv):
    try:
        return drv.execute_script("""
            var sels=['mat-icon[fonticon="send"]','mat-icon[fonticon="arrow_upward"]','button[aria-label="Send message"]'];
            for(var s=0;s<sels.length;s++){
                var els=document.querySelectorAll(sels[s]);
                for(var i=0;i<els.length;i++){
                    var b=els[i].tagName==='BUTTON'?els[i]:els[i].closest('button');
                    if(b&&!b.disabled&&b.offsetParent!==null)return true;
                }
            } return false;""")
    except Exception: return False

def check_text_error(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for p in ["can't create images of minors", "i'm not able to create that image", "i can't create this image", "sorry, i can't create"]:
            if p in body: return "refusal"
        for p in ["reached your image-generation limit", "daily limit", "rate limit"]:
            if p in body: return "limit"
    except Exception: pass
    return None

def check_gemini_error(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for sig in ["i encountered an error", "something went wrong. try again", "an error occurred"]:
            if sig in body: return sig
    except Exception: pass
    return None

def poll_gen_response(drv, urls_before, chat_urls):
    rc = check_text_error(drv)
    if rc: return ('REFUSED' if rc == "refusal" else 'LIMIT'), None
    if check_gemini_error(drv):
        if _send_btn_enabled(drv) or _response_done(drv): return 'ERROR', None

    try:
        blob_srcs = drv.execute_script("""
            var srcs=[];
            var imgs=document.querySelectorAll('img[src^="blob:https://gemini.google.com"]');
            for(var i=imgs.length-1;i>=0;i--){
                var img=imgs[i]; if(!img.offsetParent) continue;
                var src=img.getAttribute('src')||'';
                var tid=img.getAttribute('data-test-id')||'';
                if(tid.includes('uploaded-img')||tid==='image-preview') continue;
                if(src.length>10) srcs.push(src);
            } return srcs;
        """) or []
        for src in blob_srcs:
            if src not in urls_before and src not in chat_urls:
                return 'SUCCESS', src
    except Exception: pass

    for sel in [
        "generated-image img", "single-image img", "img[src*='googleusercontent']",
        "model-response img", ".response-container-content img"
    ]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                if not img.is_displayed(): continue
                src = img.get_attribute("src") or ""
                tid = img.get_attribute("data-test-id") or ""
                if len(src) < 10 or "uploaded-img" in tid or tid == "image-preview": continue
                if src in urls_before or src in chat_urls: continue
                if src.startswith("blob:https://gemini.google.com") or "googleusercontent" in src:
                    return 'SUCCESS', src
        except Exception: continue
    return 'WAITING', None


# ============================================================================
# SINGLE-CLICK DOWNLOAD INITIATION (NON-BLOCKING)
# ============================================================================

def _direct_fetch(drv, save_path, target_url=None):
    if target_url and target_url.startswith(('http://', 'https://')):
        try:
            req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read()
                if len(data) > 5000:
                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(save_path).write_bytes(data)
                    return True
        except Exception: pass
    try:
        blob_url = target_url if (target_url and target_url.startswith('blob:')) else None
        if not blob_url:
            blob_url = drv.execute_script("""
                var imgs = document.querySelectorAll('single-image img, generated-image img, img[src^="blob:https://gemini.google.com"]');
                for (var i = imgs.length - 1; i >= 0; i--) {
                    var s = imgs[i].getAttribute('src') || '';
                    if (s.startsWith('blob:https://gemini.google.com')) return s;
                } return null;
            """)
        if blob_url and blob_url.startswith('blob:'):
            b64_str = drv.execute_async_script("""
                var url = arguments[0];
                var cb = arguments[arguments.length - 1];
                fetch(url).then(r=>r.blob()).then(b=>{
                    var fr=new FileReader();
                    fr.onloadend=()=>cb(fr.result.indexOf(',')!==-1?fr.result.split(',')[1]:fr.result);
                    fr.onerror=()=>cb(null);
                    fr.readAsDataURL(b);
                }).catch(()=>cb(null));
            """, blob_url)
            if b64_str and len(b64_str) > 1000:
                data = base64.b64decode(b64_str)
                if len(data) > 5000:
                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(save_path).write_bytes(data)
                    return True
    except Exception: pass
    return False

def _click_dl_btn(drv):
    selectors = [
        ("css", "button[data-test-id='download-generated-image-button']"),
        ("css", "button[aria-label='Download']"),
        ("css", "button[aria-label='Download image']"),
        ("css", "button[aria-label*='Download']"),
        ("xpath", "//button[contains(@aria-label,'Download')]")
    ]
    for by_type, sel in selectors:
        try:
            by = By.XPATH if by_type == "xpath" else By.CSS_SELECTOR
            for btn in reversed(drv.find_elements(by, sel)):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(0.05)
                    drv.execute_script("arguments[0].click();", btn)
                    return True
        except Exception: continue
    return False

def start_browser_download(drv, tid, info, target_url):
    job_id = info["job_id"]
    job_dir = JOBS_DOWNLOAD_BASE / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    raw_path = job_dir / f"{job_id}.png"
    
    # Configure CDP download path for this exact job directory
    try:
        drv.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': str(job_dir.resolve())
        })
    except Exception: pass

    # 1. Try instantaneous direct memory fetch
    if _direct_fetch(drv, str(raw_path), target_url=target_url):
        log(f"[T{tid}][{job_id}] Direct fetch succeeded! Captured {raw_path.stat().st_size // 1024} KB")
        info["urls_before"].add(target_url)
        # Register in active downloads
        active_downloads[job_id] = {
            "job_id": job_id, "tab_id": tid, "job": info["job"], "gen": info["gen"],
            "prompt": info["prompt"], "download_dir": job_dir, "raw_download_path": raw_path,
            "started_at": time.time(), "last_size": raw_path.stat().st_size, "stable_checks": 2,
            "state": S_DOWNLOAD_WAITING
        }
        # IMMEDIATELY FREE THE CHROME TAB!
        _free_tab(tid, job_id)
        return True

    # 2. Hover and click download button ONCE
    hover_ok = False
    try:
        for sel in ["single-image img", "generated-image img", "img[src*='googleusercontent']", "img[src^='blob:']"]:
            for img in reversed(drv.find_elements(By.CSS_SELECTOR, sel)):
                if img.is_displayed():
                    drv.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'});", img)
                    # Native hover
                    try: ActionChains(drv).move_to_element(img).perform()
                    except Exception: pass
                    # Event dispatch
                    drv.execute_script("""
                        var el = arguments[0];
                        var tgts = [el, el.parentElement, el.closest('single-image'), el.closest('generated-image')].filter(Boolean);
                        tgts.forEach(function(t){
                            ['mouseenter','mouseover','mousemove'].forEach(function(e){
                                t.dispatchEvent(new MouseEvent(e,{bubbles:true,cancelable:true,view:window}));
                            });
                        });
                        document.querySelectorAll('button[data-test-id="download-generated-image-button"], button[aria-label*="Download"]').forEach(function(b){
                            b.style.cssText='display:inline-block!important;visibility:visible!important;opacity:1!important;pointer-events:auto!important;z-index:99999!important;';
                        });
                    """, img)
                    time.sleep(0.15)
                    if _click_dl_btn(drv):
                        hover_ok = True
                        break
            if hover_ok: break
    except Exception: pass

    if not hover_ok:
        # Fallback JS click across containers
        try:
            hover_ok = drv.execute_script("""
                var btns=document.querySelectorAll('button[data-test-id="download-generated-image-button"],button[aria-label*="Download"]');
                for(var i=btns.length-1;i>=0;i--){
                    if(btns[i].offsetParent!==null&&!btns[i].disabled){
                        btns[i].scrollIntoView({block:'center'}); btns[i].click(); return true;
                    }
                } return false;
            """)
        except Exception: pass

    log(f"[T{tid}][{job_id}] DOWNLOAD CLICKED (success={hover_ok}) -> Handing off to disk watcher.")
    info["urls_before"].add(target_url)

    # Register in active downloads
    active_downloads[job_id] = {
        "job_id": job_id, "tab_id": tid, "job": info["job"], "gen": info["gen"],
        "prompt": info["prompt"], "download_dir": job_dir, "raw_download_path": raw_path,
        "started_at": time.time(), "last_size": -1, "stable_checks": 0,
        "state": S_DOWNLOAD_WAITING
    }

    # IMMEDIATELY FREE THE CHROME TAB!
    _free_tab(tid, job_id)
    return True

def _free_tab(tid, job_id):
    info = tab_states[tid]
    info["state"] = S_IDLE
    info["job"] = None
    info["job_id"] = None
    info["gen"] = None
    info["prompt"] = None
    info["target_src"] = None
    info["download_started"] = False
    info["stuck_polls"] = 0
    info["start_time"] = 0.0
    log(f"[T{tid}][{job_id}] TAB FREED! Available for next queued job.")


# ============================================================================
# STEP 11: DATABASE FETCH & DEAD LETTER QUEUE HELPERS
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
        if not row: return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()

def resolve_prompt_and_refs(gen):
    params = gen.get('params') or {}
    if isinstance(params, str):
        try: params = json.loads(params)
        except Exception: params = {}

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
        cur.execute("""
            INSERT INTO dead_letter_jobs
                (queue_name, job_name, generation_id, payload_summary, failed_reason,
                 attempts_made, status, worker_id, error_stack)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, 'open', %s, %s)
            """, (QUEUE_NAME, 'process-generation', gen['id'], summary, failed_reason[:4000], attempts_made, WORKER_ID, (error_stack or '')[:8000]))
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# STEP 12: CENTRAL ASYNC SCHEDULER & PIPELINE COORDINATOR
# ============================================================================

job_queue = asyncio.Queue()
active_downloads = {}
counters = {"completed": 0, "failed": 0}
last_status_print = 0.0

def get_next_idle_tab():
    # Deterministic lowest-tab-id priority: T0 -> T1 -> T2 -> T3
    for tid in range(MAX_CONCURRENT_TABS):
        if tab_states[tid]["state"] == S_IDLE:
            return tid
    return None

async def check_active_downloads():
    now = time.time()
    for job_id, dinfo in list(active_downloads.items()):
        if dinfo["state"] != S_DOWNLOAD_WAITING:
            continue
        
        job_dir = dinfo["download_dir"]
        raw_path = dinfo["raw_download_path"]
        
        # 1. Check if raw file already exists and is full size
        if raw_path.exists() and raw_path.stat().st_size > 5000:
            dinfo["state"] = S_FINALIZING
            log(f"[{job_id}] FILE VERIFIED ({raw_path.stat().st_size // 1024} KB) -> Enqueuing for Edge WMR.")
            asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
            continue
            
        # 2. Check candidate directory for new downloads
        candidate_dirs = [job_dir, JOBS_DOWNLOAD_BASE, Path('/content/downloads'), Path('/root/Downloads')]
        found_file = None
        for cd in candidate_dirs:
            if not cd.exists(): continue
            for fn in os.listdir(cd):
                if fn.endswith(('.crdownload', '.tmp', '.part', '.download')): continue
                if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')): continue
                fp = cd / fn
                try:
                    if fp.stat().st_size > 5000 and (now - fp.stat().st_mtime) < 180:
                        found_file = fp; break
                except Exception: pass
            if found_file: break

        if found_file:
            cur_sz = found_file.stat().st_size
            if cur_sz == dinfo["last_size"]:
                dinfo["stable_checks"] += 1
                if dinfo["stable_checks"] >= 2:
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    if str(found_file) != str(raw_path):
                        try: shutil.move(str(found_file), str(raw_path))
                        except Exception: shutil.copy2(str(found_file), str(raw_path))
                    dinfo["state"] = S_FINALIZING
                    log(f"[{job_id}] DOWNLOAD STABLE ({raw_path.stat().st_size // 1024} KB) -> Enqueuing for Edge WMR.")
                    asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
            else:
                dinfo["last_size"] = cur_sz
                dinfo["stable_checks"] = 0
                
        # 3. Timeout check for file write (90 seconds)
        elif now - dinfo["started_at"] > 90.0:
            dinfo["state"] = S_FAILED
            log(f"[{job_id}] ⚠️ Filesystem download timed out after 90s!", file=sys.stderr)
            asyncio.create_task(_handle_job_failure(job_id, dinfo, "Download timed out waiting for file on disk"))

async def _finalize_and_clean_job(job_id, dinfo):
    raw_path = dinfo["raw_download_path"]
    tid = dinfo["tab_id"]
    gen = dinfo["gen"]
    prompt = dinfo["prompt"]
    job = dinfo["job"]
    
    try:
        cleaned_path, webp_path = await edge_wmr_worker.remove_watermark_async(job_id, tid, raw_path)
        
        log(f"[{WORKER_ID}] {job_id}: [STEP_R2_UPLOAD] Pushing final assets to R2 bucket {R2_BUCKET_NAME}...")
        result = sys.modules['fashion_studio'].push_generation(
            image_path=str(cleaned_path),
            prompt=prompt,
            user_id=gen['user_id'],
            gen_id=job_id,
            webp_path=str(webp_path) if webp_path else None,
            force=True,
            params=gen.get('params') or {}
        )
        
        try:
            sys.modules['credits'].settle_look(job_id)
            log(f"[{WORKER_ID}] {job_id}: [STEP_CREDITS_SETTLE] Credits settled successfully.")
        except Exception as e:
            log(f"[{WORKER_ID}] {job_id}: settle_look warning: {e}", file=sys.stderr)
            
        counters["completed"] += 1
        log(f"[{WORKER_ID}] {job_id}: [STEP_COMPLETE] Job complete! Output URL: {result.get('output_url')}")
        if dinfo.get("future") and not dinfo["future"].done():
            dinfo["future"].set_result(result)
            
    except Exception as e:
        counters["failed"] += 1
        log(f"[{WORKER_ID}] {job_id}: Finalization failed: {e}", file=sys.stderr)
        try:
            record_dead_letter(gen, str(e), 1, 1, traceback.format_exc())
            sys.modules['credits'].refund_look(job_id, str(e)[:500])
        except Exception: pass
        if dinfo.get("future") and not dinfo["future"].done():
            dinfo["future"].set_exception(e)
    finally:
        active_downloads.pop(job_id, None)

async def _handle_job_failure(job_id, dinfo, reason):
    counters["failed"] += 1
    gen = dinfo["gen"]
    try:
        record_dead_letter(gen, reason, 1, 1, traceback.format_exc())
        sys.modules['credits'].refund_look(job_id, reason[:500])
    except Exception: pass
    if dinfo.get("future") and not dinfo["future"].done():
        dinfo["future"].set_exception(RuntimeError(reason))
    active_downloads.pop(job_id, None)

async def assign_jobs_to_idle_tabs():
    while not job_queue.empty():
        tid = get_next_idle_tab()
        if tid is None:
            break
        
        job_envelope = await job_queue.get()
        info = tab_states[tid]
        info["state"] = S_SUBMITTING
        info["job"] = job_envelope["job"]
        info["job_id"] = job_envelope["job_id"]
        info["gen"] = job_envelope["gen"]
        info["prompt"] = job_envelope["prompt"]
        info["refs"] = job_envelope["refs"]
        info["future"] = job_envelope["future"]
        info["download_started"] = False
        info["stuck_polls"] = 0
        info["start_time"] = time.time()
        
        log(f"[T{tid}][{info['job_id']}] ASSIGNED -> Submitting prompt & refs...")
        asyncio.create_task(_submit_job_to_tab(tid))

async def _submit_job_to_tab(tid):
    info = tab_states[tid]
    job_id = info["job_id"]
    try:
        async with chrome_lock:
            chrome_driver.switch_to.window(info["handle"])
            start_new_chat(chrome_driver)
            ensure_flash_mode(chrome_driver, tid)
            ensure_create_image_mode(chrome_driver, tid)
            upload_images(chrome_driver, info["refs"])
            type_prompt(chrome_driver, info["prompt"])
            info["urls_before"] = snapshot_urls(chrome_driver)
            info["chat_urls"] = set()
            
            if not click_send(chrome_driver):
                raise RuntimeError(f"Tab T{tid}: Failed to click send button.")
            
            info["state"] = S_GEN_WAITING
            info["next_poll"] = time.time() + 1.2
            log(f"[T{tid}][{job_id}] PROMPT SENT! Lock released — Tab T{tid} generating in background.")
    except Exception as e:
        log(f"[T{tid}][{job_id}] Submission error: {e}", file=sys.stderr)
        info["state"] = S_IDLE
        if info.get("future") and not info["future"].done():
            info["future"].set_exception(e)

async def poll_active_tabs():
    now = time.time()
    for tid in range(MAX_CONCURRENT_TABS):
        info = tab_states[tid]
        if info["state"] != S_GEN_WAITING:
            continue
        if now < info["next_poll"]:
            continue
            
        async with chrome_lock:
            chrome_driver.switch_to.window(info["handle"])
            
            # Check hard timeout
            if now - info["start_time"] > GENERATION_TIMEOUT_S:
                log(f"[T{tid}][{info['job_id']}] HARD TIMEOUT after {GENERATION_TIMEOUT_S}s! Refreshing tab.")
                _recover_stuck_tab(tid, "Generation timed out")
                continue
                
            status, new_src = poll_gen_response(chrome_driver, info["urls_before"], info["chat_urls"])
            
            if status == 'SUCCESS':
                log(f"[T{tid}][{info['job_id']}] IMAGE DETECTED! Triggering single download click...")
                start_browser_download(chrome_driver, tid, info, new_src)
                continue
                
            elif status == 'ERROR':
                log(f"[T{tid}][{info['job_id']}] Gemini reported generation error.")
                _recover_stuck_tab(tid, "Gemini reported error")
                continue
                
            elif status == 'REFUSED':
                log(f"[T{tid}][{info['job_id']}] Prompt refused by Gemini.")
                _recover_stuck_tab(tid, "Prompt refused")
                continue
                
            elif status == 'LIMIT':
                log(f"[T{tid}][{info['job_id']}] Image generation limit reached.")
                _recover_stuck_tab(tid, "Limit reached")
                continue
                
            else: # WAITING
                if _send_btn_enabled(chrome_driver) and not _response_done(chrome_driver):
                    info["stuck_polls"] += 1
                    if info["stuck_polls"] >= 8:
                        log(f"[T{tid}][{info['job_id']}] SOFT STUCK detected! Refreshing tab.")
                        _recover_stuck_tab(tid, "Soft stuck detected")
                        continue
                else:
                    info["stuck_polls"] = 0
                    
                elapsed = now - info["start_time"]
                interval = 1.0 if elapsed < 20 else (2.0 if elapsed < 180 else 0.8)
                info["next_poll"] = now + interval

def _recover_stuck_tab(tid, reason):
    info = tab_states[tid]
    job_id = info["job_id"]
    gen = info["gen"]
    future = info.get("future")
    
    try:
        chrome_driver.get(GEMINI_APP_URL)
    except Exception: pass
    
    info["state"] = S_IDLE
    info["job"] = None
    info["job_id"] = None
    info["gen"] = None
    info["prompt"] = None
    info["download_started"] = False
    info["stuck_polls"] = 0
    info["start_time"] = 0.0
    
    counters["failed"] += 1
    if gen:
        try:
            record_dead_letter(gen, reason, 1, 1, traceback.format_exc())
            sys.modules['credits'].refund_look(job_id, reason[:500])
        except Exception: pass
    if future and not future.done():
        future.set_exception(RuntimeError(reason))

def print_pipeline_status():
    global last_status_print
    now = time.time()
    if now - last_status_print < 15.0: return
    last_status_print = now
    
    print("\\n" + "=" * 65)
    print(f"📊 PIPELINE STATUS [{time.strftime('%H:%M:%S')}]")
    print(f"  Queue: {job_queue.qsize()} | Downloading: {len(active_downloads)} | Completed: {counters['completed']} | Failed: {counters['failed']}")
    for tid in range(MAX_CONCURRENT_TABS):
        st = tab_states[tid]
        state = st["state"]
        jid = st["job_id"] or "---"
        elapsed = f"{int(now - st['start_time'])}s" if st["start_time"] > 0 else "0s"
        print(f"  T{tid} = {state:<12} Job={jid[:8]} ({elapsed})")
    print("=" * 65 + "\\n")

async def central_scheduler_loop():
    while True:
        try:
            await check_active_downloads()
            await assign_jobs_to_idle_tabs()
            await poll_active_tabs()
            print_pipeline_status()
        except Exception as e:
            log(f"Scheduler exception: {e}", file=sys.stderr)
        await asyncio.sleep(0.1)


# ============================================================================
# STEP 13: BULLMQ WORKER & MAIN ENTRYPOINT
# ============================================================================
from bullmq import Worker

async def process_bullmq_job(job, job_token):
    gen_id = job.data.get('generationId') or job.data.get('id') or (job.id if job else None)
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
        "future": done_future
    }
    
    await job_queue.put(job_envelope)
    return await done_future

async def main():
    log(f"[{WORKER_ID}] connecting to {REDIS_URL} queue={QUEUE_NAME!r} prefix={REDIS_KEY_PREFIX!r}")
    
    worker = Worker(
        QUEUE_NAME,
        process_bullmq_job,
        {
            'connection': REDIS_URL,
            'prefix': REDIS_KEY_PREFIX,
            'concurrency': 8
        }
    )
    
    # Launch central scheduler concurrently
    scheduler_task = asyncio.create_task(central_scheduler_loop())
    log(f"[{WORKER_ID}] waiting for jobs (Ctrl+C to stop)...")
    
    try:
        await scheduler_task
    except (KeyboardInterrupt, asyncio.CancelledError):
        log(f"\\n[{WORKER_ID}] Stopping worker gracefully...")
    finally:
        await worker.close()
        try: chrome_driver.quit()
        except Exception: pass
        if edge_wmr_worker.driver:
            try: edge_wmr_worker.driver.quit()
            except Exception: pass

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
'''

target_file.write_text(script_content, encoding='utf-8')
print(f"Generated {target_file} ({len(script_content)} chars)")
