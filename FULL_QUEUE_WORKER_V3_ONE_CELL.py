# ============================================================================
# 🚀 QUEUE WORKER v3.0 — ECOM 2 ITERATION HIGH-EFFICIENCY MULTI-TAB ARCHITECTURE
# ============================================================================
# Copy and paste this ENTIRE cell into Google Colab and run it.
#
# ARCHITECTURAL HIGHLIGHTS:
#   • Strictly 4 Concurrent Chrome Tabs (T0, T1, T2, T3) with Lowest-ID Priority
#   • Real-time noVNC Cloudflare Tunnel with Clickable HTML Link in Colab
#   • Exact ECOM 2 Flash Selector (Strictly Flash, rejecting Lite / Pro)
#   • Verified "Create Image" Drawer Activation & Multi-file Attachment
#   • Ultra-fast Clipboard (xclip) Prompt Injection (<200ms)
#   • Instant CDP Direct-Memory / Canvas Image Fetch (<150ms)
#   • Single Hover-Click Fallback with Dedicated Per-Tab Download Folders
#   • Immediate Chrome Tab Release on Download Initiation -> Instant Next Job
#   • Immediate Name Change to <job_id>_raw.png on Detection
#   • Independent Background Microsoft Edge Watermark Removal Pipeline
#   • Automatic WebP Conversion, Cloudflare R2 Upload & DB Credits Settle
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
    'REDIS_TUNNEL_URL': 'https://envelope-daniel-pages-lean.trycloudflare.com',
}

for _k, _v in _FALLBACKS.items():
    if not os.environ.get(_k):
        os.environ[_k] = _v

os.environ.setdefault("REDIS_KEY_PREFIX", "vastralook:")
QUEUE_NAME = 'generations'
REDIS_KEY_PREFIX = os.environ.get('REDIS_KEY_PREFIX', 'vastralook:')
MAX_CONCURRENT_TABS = 4  # Strictly 4 concurrent Chrome tabs (T0, T1, T2, T3)
GENERATION_TIMEOUT_S = 240
LOCAL_REDIS_PORT = 16379

SCREEN_W, SCREEN_H = 1920, 1080
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
EDGE_PROFILE_DIR = STATE_DIR / 'edge_profile'
REFS_CACHE_DIR = STATE_DIR / 'refs'
JOBS_DOWNLOAD_BASE = Path('/content/downloads/jobs')
WMR_DL_DIR = Path('/content/wmr_downloads')
FINAL_OUTPUT_BASE = Path('/content/downloads/final_output')
CHROME_DL_BASE = Path('/content/downloads')

for _d in (BASE_DIR, STATE_DIR, CHROME_PROFILE_DIR, EDGE_PROFILE_DIR, REFS_CACHE_DIR,
           JOBS_DOWNLOAD_BASE, WMR_DL_DIR, FINAL_OUTPUT_BASE, CHROME_DL_BASE):
    _d.mkdir(parents=True, exist_ok=True)

def tab_dl_dir(tid):
    d = Path(f"/content/downloads/tab_{tid}")
    d.mkdir(parents=True, exist_ok=True)
    return d

for tid in range(MAX_CONCURRENT_TABS):
    tab_dl_dir(tid)

_drive_cookies = Path('/content/drive/MyDrive/gemini-queue-worker/cookies.pkl')
COOKIES_FILE = _drive_cookies if _drive_cookies.parent.parent.exists() else STATE_DIR / 'cookies.pkl'
COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

print(f"  Worker ID:         {WORKER_ID}")
print(f"  Redis Tunnel:      {os.environ['REDIS_TUNNEL_URL']}")
print(f"  Chrome Profile:    {CHROME_PROFILE_DIR}")
print(f"  Edge Profile:      {EDGE_PROFILE_DIR}")
print(f"  Max Parallel Tabs: {MAX_CONCURRENT_TABS} (T0, T1, T2, T3)")
print("  ✅ Secrets and directories configured successfully.\n")

# ============================================================================
# STEP 2: INSTALL DEPENDENCIES (CHROME + EDGE + PYTHON LIBS + NOVNC + CLOUDFLARED)
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

print("  Installing Xvfb, x11vnc, noVNC, xclip, and utilities...")
run_cmd(
    "apt-get update -qq && apt-get install -y -qq wget curl xvfb x11vnc novnc websockify "
    "fluxbox net-tools procps unzip zip xclip xsel dbus-x11 python3-numpy python3-websockify",
    "system packages"
)

# Download Cloudflared binary for noVNC public web access
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
    print(f"  ✅ Microsoft Edge ready at: {edge_path}\n")
else:
    print("  ⚠️ Edge binary not found in PATH, using fallback.\n")

# ============================================================================
# STEP 3: REGISTER COMPLETE BACKEND MODULES (db, credits, fashion_studio)
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
                SET status = 'completed', updated_at = NOW()
                WHERE id = %s AND status = 'processing'
            """, (look_id,))
            conn.commit()
    return True

def credits_refund_look(look_id, reason="failed"):
    with _mod_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE image_generations
                SET status = 'failed', failed_reason = %s, updated_at = NOW()
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

R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
R2_PUBLIC_URL = os.environ.get('R2_PUBLIC_URL')
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
            "UPDATE image_generations SET output_image_url = %s, webp_image_url = %s, status = 'completed', updated_at = NOW() WHERE id = %s",
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
# STEP 4: START REDIS WEBSOCKET-TO-TCP TUNNEL BRIDGE
# ============================================================================
print("=" * 80)
print("🌐 STEP 4: CONNECTING TO REDIS VIA SECURE TUNNEL")
print("=" * 80)

BRIDGE_SCRIPT = BASE_DIR / 'ws_tcp_bridge.py'
bridge_lines = [
    "import asyncio, os, sys, urllib.parse, websockets",
    "REMOTE_WS_URL = os.environ.get('REDIS_TUNNEL_URL', '').strip()",
    "LOCAL_TCP_PORT = int(os.environ.get('LOCAL_REDIS_PORT', '16379'))",
    "if not REMOTE_WS_URL:",
    "    print('[bridge] FATAL: REDIS_TUNNEL_URL not set', file=sys.stderr); sys.exit(1)",
    "u = urllib.parse.urlsplit(REMOTE_WS_URL)",
    "ws_scheme = 'wss' if u.scheme in ('https', 'wss') else 'ws'",
    "target_url = urllib.parse.urlunsplit((ws_scheme, u.netloc, u.path or '/', u.query, ''))",
    "async def handle_client(reader, writer):",
    "    try:",
    "        async with websockets.connect(target_url, subprotocols=['binary'], max_size=64*1024*1024, ping_interval=20, ping_timeout=20) as ws:",
    "            async def tcp_to_ws():",
    "                try:",
    "                    while True:",
    "                        d = await reader.read(65536)",
    "                        if not d: break",
    "                        await ws.send(d)",
    "                except Exception: pass",
    "            async def ws_to_tcp():",
    "                try:",
    "                    async for msg in ws:",
    "                        if isinstance(msg, str): msg = msg.encode('utf-8')",
    "                        writer.write(msg); await writer.drain()",
    "                except Exception: pass",
    "            await asyncio.gather(tcp_to_ws(), ws_to_tcp())",
    "    except Exception: pass",
    "    finally:",
    "        writer.close()",
    "        try: await writer.wait_closed()",
    "        except Exception: pass",
    "async def main():",
    "    server = await asyncio.start_server(handle_client, '127.0.0.1', LOCAL_TCP_PORT)",
    "    print(f'[bridge] listening on 127.0.0.1:{LOCAL_TCP_PORT} -> {target_url}', flush=True)",
    "    async with server: await server.serve_forever()",
    "if __name__ == '__main__':",
    "    try: asyncio.run(main())",
    "    except KeyboardInterrupt: pass"
]
BRIDGE_SCRIPT.write_text('\n'.join(bridge_lines) + '\n')

run_cmd("fuser -k 16379/tcp >/dev/null 2>&1 || true")
bridge_proc = subprocess.Popen([sys.executable, str(BRIDGE_SCRIPT)])
time.sleep(1.5)

sock = socket.socket()
sock.settimeout(4.0)
try:
    sock.connect(('127.0.0.1', LOCAL_REDIS_PORT))
    sock.sendall(b"*1\r\n$4\r\nPING\r\n")
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
# STEP 5: VIRTUAL DISPLAY & NOVNC CLOUDFLARE TUNNEL (WITH CLICKABLE COLAB LINK)
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
                    vnc_url_1 = f"{tb}/vnc.html?autoconnect=true&resize=scale"
                    vnc_url_2 = f"{tb}"
                    try:
                        _banner = (
                            "<div style='background:linear-gradient(135deg,#1b5e20,#2e7d32);color:white;"
                            "padding:16px;border-radius:10px;font-size:15px;font-weight:bold;margin:10px 0;box-shadow:0 4px 6px rgba(0,0,0,0.3);'>"
                            "🖥️ <b>noVNC Remote Desktop Stream:</b><br><br>"
                            f"🌐 <a href='{vnc_url_1}' target='_blank' style='color:#a7ffeb;text-decoration:underline;'>Open Live UI ({vnc_url_1})</a><br>"
                            "</div>"
                        )
                        ipy_display(HTML(_banner))
                    except Exception: pass
                    print(f"  🌐 noVNC Public Link: {vnc_url_1}")
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


# ============================================================================
# STEP 10: PROVEN GEMINI DOM ROUTINES (ATOMIC PROMPT, STRICT FLASH, CREATE IMAGE)
# ============================================================================
print("=" * 80)
print("🎯 STEP 10: INITIALIZING GEMINI DOM & INTERACTION ENGINE")
print("=" * 80)

class ModelLimitReached(Exception):
    pass

def start_new_chat(drv):
    for sel in ['a[aria-label="New chat"]', 'button[aria-label="New chat"]', 'div[aria-label="New chat"]', '[data-test-id="new-chat-button"]']:
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
        time.sleep(1.2)
        return True
    except Exception:
        return False

# ----------------------------------------------------------------------------
# FLASH MODEL ROUTINES
# ----------------------------------------------------------------------------

def _get_current_model_text(drv):
    selectors = [
        "div[data-test-id='logo-pill-label-container'] span.picker-primary-text",
        "div[data-test-id='logo-pill-label-container'] span.gds-body-m",
        "span.picker-primary-text",
    ]
    for sel in selectors:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    txt = (el.text or "").strip()
                    if txt:
                        return txt
        except Exception:
            continue
    try:
        txt = drv.execute_script(
            "var el=document.querySelector("
            "  'div[data-test-id=\"logo-pill-label-container\"] span.picker-primary-text,"
            "   div[data-test-id=\"logo-pill-label-container\"] span.gds-body-m');"
            "return el ? el.textContent.trim() : '';"
        )
        return (txt or "").strip()
    except Exception:
        return ""

def _open_model_picker(drv):
    try:
        btn = drv.find_element(By.CSS_SELECTOR, "button[data-test-id='bard-mode-menu-button']")
        if btn and btn.is_displayed():
            drv.execute_script("arguments[0].click();", btn)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        el = drv.find_element(By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container']")
        if el and el.is_displayed():
            drv.execute_script("arguments[0].click();", el)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        icon = drv.find_element(By.CSS_SELECTOR,
            "div[data-test-id='logo-pill-label-container'] mat-icon[fonticon='keyboard_arrow_down'],"
            "div[data-test-id='logo-pill-label-container'] mat-icon[data-mat-icon-name='keyboard_arrow_down']")
        if icon and icon.is_displayed():
            drv.execute_script("arguments[0].click();", icon)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[aria-label]"):
            lbl = (btn.get_attribute("aria-label") or "").lower()
            if ("mode picker" in lbl or "open mode" in lbl or "flash" in lbl or "pro" in lbl):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.45)
                    return True
    except Exception:
        pass
    try:
        res = drv.execute_script(
            "var spans=document.querySelectorAll('span.picker-primary-text,span.gds-body-m');"
            "for(var i=0;i<spans.length;i++){"
            "  var s=spans[i]; if(!s.offsetParent) continue;"
            "  var b=s.closest('button');"
            "  if(b&&!b.disabled){ b.click(); return 'OK'; }"
            "} return 'NO';"
        )
        if res == "OK":
            time.sleep(0.45)
            return True
    except Exception:
        pass
    return False

def _click_flash_in_picker(drv):
    def _is_valid_flash_option(el):
        try:
            txt = (el.text or "").strip().lower()
            return "flash" in txt and "lite" not in txt
        except Exception:
            return False

    for tid in ["bard-mode-option-flash", "mode-option-flash", "flash-option", "model-flash"]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, f"[data-test-id='{tid}']"):
                if el.is_displayed():
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue

    for sel in ["mat-option", "[role='option']", "[role='menuitem']", "[role='menuitemradio']", "button[class*='mode-option']", "button[class*='picker']"]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed() and _is_valid_flash_option(el):
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue

    xpaths = [
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]/ancestor-or-self::button[1]",
        "//mat-option[.//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]]",
        "//button[.//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]]",
        "//*[@role='option' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]",
        "//*[@role='menuitem' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]",
    ]
    for xp in xpaths:
        try:
            for el in drv.find_elements(By.XPATH, xp):
                if el.is_displayed():
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue

    try:
        res = drv.execute_script("""
            var candidates = document.querySelectorAll('mat-option, [role="option"], [role="menuitem"], [role="menuitemradio"], button');
            for (var i = 0; i < candidates.length; i++) {
                var el = candidates[i];
                if (!el.offsetParent) continue;
                var txt = (el.textContent || '').trim().toLowerCase();
                if (txt.indexOf('flash') === -1) continue;
                if (txt.indexOf('lite') !== -1) continue;
                if (txt.length > 60) continue;
                var dis = el.getAttribute('disabled') || el.getAttribute('aria-disabled') === 'true';
                if (dis) return 'DISABLED';
                el.click(); return 'OK:' + txt;
            } return 'NO';
        """)
        if res and res.startswith("OK"):
            time.sleep(0.4)
            return True
        if res == "DISABLED":
            raise ModelLimitReached("Flash disabled in picker")
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
            if txt and "flash" in txt.lower() and "lite" not in txt.lower():
                return True
        except Exception:
            pass
        time.sleep(0.15)
    return False

def ensure_flash_mode(drv):
    current = _get_current_model_text(drv)
    if current and "flash" in current.lower() and "lite" not in current.lower():
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
                drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception:
                pass
            raise
        if clicked and _verify_flash_selected(drv, timeout=2.5):
            return True
        try:
            drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError("Flash mode could not be verified in model picker")

# ----------------------------------------------------------------------------
# CREATE IMAGE SEPARATE ROUTINES
# ----------------------------------------------------------------------------

def click_plus_button(drv):
    try:
        res = drv.execute_script("""
            var btns = document.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                var b = btns[i];
                if (b.offsetParent === null) continue;
                var lbl = (b.getAttribute('aria-label') || '').toLowerCase();
                if (lbl.indexOf('upload') !== -1 || lbl.indexOf('tools') !== -1 || lbl.indexOf('plus') !== -1) {
                    b.click(); return 'OK';
                }
                var icon = b.querySelector('mat-icon[fonticon="plus"], mat-icon[data-mat-icon-name="plus"]');
                if (icon) { b.click(); return 'OK'; }
            } return 'NO';
        """)
        if res == 'OK':
            time.sleep(0.3)
            return True
    except Exception:
        pass
    for sel in ['button[aria-label="Upload and tools"]', 'button[jslog*="300142"]', 'button[aria-haspopup="menu"][aria-label*="Upload"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    return False

def click_upload_files_in_drawer(drv):
    for sel in [
        "button[data-test-id='local-images-files-uploader-button']",
        "//span[contains(text(),'Upload files')]/ancestor::button",
        "//div[contains(text(),'Upload files')]/ancestor::button",
    ]:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            for btn in drv.find_elements(by, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.2)
                    return True
        except Exception:
            continue
    try:
        res = drv.execute_script("""
            var btns = document.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].offsetParent !== null && btns[i].textContent.toLowerCase().indexOf('upload files') !== -1) {
                    btns[i].click(); return 'OK';
                }
            } return 'NO';
        """)
        if res == 'OK':
            time.sleep(0.2)
            return True
    except Exception:
        pass
    return False

def find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs:
        return inputs[0]
    try:
        drv.execute_script("""
            document.querySelectorAll('input[type=\"file\"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                el.removeAttribute('hidden'); el.removeAttribute('disabled');
            });
        """)
    except Exception:
        pass
    time.sleep(0.1)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def is_create_image_mode(drv):
    try:
        editors = drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder='Describe your image']")
        if not any(e.is_displayed() for e in editors):
            return False
        
        signals = [
            "mat-icon[data-mat-icon-name='image_create']",
            "mat-icon[fonticon='image_create']",
            "button[aria-label*='Aspect ratio']",
            "//span[contains(text(), 'Aspect ratio')]",
            "//button[contains(., 'Images')]",
            "//div[contains(., 'Images') and contains(@class, 'chip')]"
        ]
        for sig in signals:
            by = By.XPATH if sig.startswith("//") else By.CSS_SELECTOR
            for el in drv.find_elements(by, sig):
                if el.is_displayed():
                    return True
        return len(editors) > 0
    except Exception:
        return False

def ensure_create_image_mode(drv, tid=0):
    if is_create_image_mode(drv):
        log(f"[T{tid}] CREATE IMAGE VERIFIED")
        return True

    for attempt in range(1, 3):
        if click_plus_button(drv):
            time.sleep(0.3)
            try:
                btns = drv.find_elements(By.CSS_SELECTOR, "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button")
                for btn in btns:
                    if btn.is_displayed() and "create image" in btn.text.lower():
                        drv.execute_script("arguments[0].click();", btn)
                        time.sleep(0.4)
                        break
                else:
                    for icon in drv.find_elements(By.CSS_SELECTOR, "mat-icon[data-mat-icon-name='image_create'], mat-icon[fonticon='image_create']"):
                        if icon.is_displayed():
                            btn = drv.execute_script("var e=arguments[0];while(e&&e.tagName!=='BUTTON')e=e.parentElement;return e;", icon)
                            if btn and btn.is_displayed():
                                drv.execute_script("arguments[0].click();", btn)
                                time.sleep(0.4)
                                break
            except Exception:
                pass

        time.sleep(0.5)
        if is_create_image_mode(drv):
            log(f"[T{tid}] CREATE IMAGE VERIFIED")
            return True

    raise RuntimeError(f"Tab T{tid}: Failed to activate Create image mode.")

def upload_reference_images(drv, abs_paths, tid=0):
    valid_paths = [p for p in abs_paths if p and os.path.exists(p)]
    expected_count = len(valid_paths)
    if expected_count == 0:
        log(f"[T{tid}] No reference images to upload.")
        return True

    if not click_plus_button(drv):
        log(f"[T{tid}] Failed to click plus button for upload.", file=sys.stderr)
        return False
    time.sleep(0.25)

    if not click_upload_files_in_drawer(drv):
        try:
            drv.execute_script("var b=document.querySelector('button.hidden-local-file-image-selector-button, button[xapfileselectortrigger]'); if(b) b.click();")
            time.sleep(0.15)
        except Exception:
            pass

    fi = find_file_input(drv)
    if not fi:
        log(f"[T{tid}] File input not found.", file=sys.stderr)
        return False

    try:
        fi.send_keys("\n".join(valid_paths))
    except Exception as e:
        log(f"[T{tid}] File input send_keys failed: {e}", file=sys.stderr)
        return False

    # Verify attachment chips count (Part P)
    t0 = time.time()
    verified = False
    chip_count = 0
    while time.time() - t0 < 12.0:
        chips = []
        for sel in [
            "button[aria-label='close attachment']",
            "gem-media-attachment",
            "uploader-file-preview",
            ".attachment-preview-wrapper",
            "div[data-test-id='uploaded-img']",
            "mat-icon[fonticon='close']"
        ]:
            try:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        chips.append(el)
            except Exception:
                pass
        chip_count = len(set(chips))
        if chip_count >= expected_count:
            verified = True
            log(f"[T{tid}] ✅ ATTACHED {expected_count}/{expected_count}")
            break
        time.sleep(0.3)

    if not verified:
        log(f"[T{tid}] ATTACHMENT_FAILED: Expected {expected_count} attachments, verified {chip_count}/{expected_count}", file=sys.stderr)
        return False
    return True

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

def _verify_editor_prompt(drv, editor, expected_text, tid=0):
    try:
        actual_raw = editor.text or ""
        if not actual_raw:
            actual_raw = drv.execute_script("return (arguments[0].textContent || '');", editor) or ""

        expected_norm = normalize_prompt_text(expected_text)
        actual_norm = normalize_prompt_text(actual_raw)

        exp_len = len(expected_norm)
        act_len = len(actual_norm)

        log(f"[T{tid}] PROMPT LENGTH expected={exp_len} actual={act_len}")

        if exp_len == 0:
            return act_len == 0

        coverage = act_len / exp_len
        if coverage < 0.98 or coverage > 1.05:
            log(f"[T{tid}] PROMPT LENGTH MISMATCH: coverage={coverage:.2%}")
            return False

        prefix_len = min(80, exp_len)
        if actual_norm[:prefix_len] != expected_norm[:prefix_len]:
            log(f"[T{tid}] PROMPT START MISMATCH: '{actual_norm[:30]}' != '{expected_norm[:30]}'")
            return False
        log(f"[T{tid}] PROMPT START VERIFIED")

        suffix_len = min(80, exp_len)
        if actual_norm[-suffix_len:] != expected_norm[-suffix_len:]:
            log(f"[T{tid}] PROMPT END MISMATCH: '{actual_norm[-30:]}' != '{expected_norm[-30:]}'")
            return False
        log(f"[T{tid}] PROMPT END VERIFIED")

        log(f"[T{tid}] PROMPT COMPLETE VERIFIED")
        return True
    except Exception as e:
        log(f"[T{tid}] Prompt verification error: {e}")
        return False

PROMPT_EMPTY = "PROMPT_EMPTY"
PROMPT_INJECTING = "PROMPT_INJECTING"
PROMPT_VERIFYING = "PROMPT_VERIFYING"
PROMPT_READY = "PROMPT_READY"
PROMPT_FAILED = "PROMPT_FAILED"

def _inject_prompt_atomic(drv, text, tid=0):
    editor = get_quill_editor(drv)
    if not editor:
        log(f"[T{tid}] PROMPT_FAILED: Quill editor element not found in DOM.")
        return False

    for attempt in range(1, 3):
        try:
            drv.execute_script("arguments[0].focus();", editor)
            time.sleep(0.1)

            # Select all and delete in one operation
            ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            time.sleep(0.05)
            ActionChains(drv).send_keys(Keys.DELETE).perform()
            drv.execute_script("document.execCommand('selectAll',false,null); document.execCommand('delete',false,null);")
            time.sleep(0.1)

            # Primary: Chrome CDP Input.insertText in ONE atomic browser operation
            cdp_ok = False
            try:
                drv.execute_cdp_cmd("Input.insertText", {"text": text})
                cdp_ok = True
            except Exception as cdp_err:
                log(f"[T{tid}] CDP Input.insertText notice ({cdp_err}), trying single xclip Ctrl+V...")

            # Fallback: xclip clipboard ONE TIME only
            if not cdp_ok:
                if _set_clipboard_xclip(text):
                    drv.execute_script("arguments[0].focus();", editor)
                    ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
                else:
                    log(f"[T{tid}] xclip clipboard setting failed.", file=sys.stderr)

            time.sleep(0.3)

            # Verify complete prompt
            if _verify_editor_prompt(drv, editor, text, tid=tid):
                return True
            else:
                log(f"[T{tid}] Prompt verification failed on attempt {attempt}. Clearing editor...")
                drv.execute_script("arguments[0].focus(); document.execCommand('selectAll',false,null); document.execCommand('delete',false,null);", editor)
                time.sleep(0.3)
        except Exception as e:
            log(f"[T{tid}] Exception during prompt injection (attempt {attempt}): {e}")
            try:
                drv.execute_script("arguments[0].focus(); document.execCommand('selectAll',false,null); document.execCommand('delete',false,null);", editor)
            except Exception:
                pass
            time.sleep(0.3)

    log(f"[T{tid}] PROMPT_FAILED: Failed to inject and verify prompt after 2 atomic attempts.")
    return False

# ----------------------------------------------------------------------------
# SEND & GENERATION VERIFICATION
# ----------------------------------------------------------------------------

def _click_send_button(drv):
    try:
        res = drv.execute_script("""
            var sels = ['mat-icon[fonticon="arrow_upward"]', 'mat-icon[data-mat-icon-name="arrow_upward"]', 'mat-icon[fonticon="send"]', 'button[aria-label="Send message"]'];
            for (var s = 0; s < sels.length; s++) {
                var els = document.querySelectorAll(sels[s]);
                for (var i = 0; i < els.length; i++) {
                    var b = els[i].tagName === 'BUTTON' ? els[i] : els[i].closest('button');
                    if (b && !b.disabled && b.offsetParent !== null) { b.click(); return 'OK'; }
                }
            } return 'NO';
        """)
        if res == 'OK':
            return True
    except Exception:
        pass
    for xp in [
        "//mat-icon[@data-mat-icon-name='arrow_upward']/ancestor::button",
        "//mat-icon[@fonticon='arrow_upward']/ancestor::button",
        "//button[@aria-label='Send message']",
    ]:
        try:
            for btn in drv.find_elements(By.XPATH, xp):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].click();", btn)
                    return True
        except Exception:
            continue
    return False

def verify_generation_started(drv, timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            stop = drv.execute_script("""
                var sels = ['button[aria-label="Stop generating"]', 'button[aria-label="Cancel"]', 'mat-icon[fonticon="stop"]', 'mat-icon[data-mat-icon-name="stop"]'];
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
# IMAGE DETECTION & INSTANT MEMORY CAPTURE ROUTINES
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
            var sels = ['mat-icon[fonticon="arrow_upward"]', 'mat-icon[data-mat-icon-name="arrow_upward"]', 'mat-icon[fonticon="send"]', 'button[aria-label="Send message"]'];
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
            var sels = ['button[aria-label="Stop generating"]', 'button[aria-label="Cancel"]', 'mat-icon[fonticon="stop"]', 'mat-icon[data-mat-icon-name="stop"]'];
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

    for sel in ["generated-image img", "single-image img", "img[src*='googleusercontent']", "model-response img"]:
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

def _direct_fetch_cdp(drv, save_path, urls_before):
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
            if len(data) > 5000:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                Path(save_path).write_bytes(data)
                return True
    except Exception:
        pass
    return False

def _hover_and_dl_single_click(drv, urls_before, chat_urls):
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
    for sel in ["single-image img", "generated-image img", "img[src^='blob:https://gemini.google.com']", "img[src*='googleusercontent']"]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                src = img.get_attribute("src") or ""
                tid = img.get_attribute("data-test-id") or ""
                if ("uploaded-img" in tid or tid == "image-preview" or src in urls_before or src in chat_urls or src in seen or len(src) < 10):
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
            (QUEUE_NAME, 'process-generation', gen['id'], summary, failed_reason[:4000], attempts_made, WORKER_ID, (error_stack or '')[:8000])
        )
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

def find_first_idle_tab():
    # Strict lowest-ID priority (T0 -> T1 -> T2 -> T3)
    for tid in range(MAX_CONCURRENT_TABS):
        if tab_states[tid]["state"] == S_IDLE:
            return tid
    return None

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
    info["future"] = None
    log(f"[T{tid}][{job_id}] TAB FREED! Immediately available for next queued job.")

async def poll_active_downloads():
    now = time.time()
    for job_id, dinfo in list(active_downloads.items()):
        if dinfo["state"] != "WAITING":
            continue

        raw_path = dinfo["raw_path"]
        job_dir = dinfo["download_dir"]
        files_before = dinfo.get("files_before", set())

        # Direct file check (written via direct memory fetch)
        if raw_path.exists() and raw_path.stat().st_size > 5000:
            dinfo["state"] = "COMPLETE"
            log(f"[{job_id}] DOWNLOAD CONFIRMED ({raw_path.stat().st_size // 1024} KB) -> Immediate handoff to Edge WMR.")
            asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
            continue

        # Check isolated job directory
        found_file = None
        if job_dir.exists():
            for fn in os.listdir(job_dir):
                if fn.endswith(('.crdownload', '.tmp', '.part', '.download')):
                    continue
                if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    continue
                fp = job_dir / fn
                try:
                    if str(fp) in files_before:
                        continue
                    if fp.stat().st_size >= 5000:
                        found_file = fp
                        break
                except Exception:
                    pass

        # Fallback candidate check if not in isolated job_dir (e.g. root Colab downloads)
        if not found_file:
            for cd in [Path('/content/downloads'), Path('/root/Downloads')]:
                if not cd.exists():
                    continue
                for fn in os.listdir(cd):
                    if fn.endswith(('.crdownload', '.tmp', '.part', '.download')):
                        continue
                    if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        continue
                    fp = cd / fn
                    try:
                        if str(fp) in files_before:
                            continue
                        if fp.stat().st_size >= 5000 and (now - fp.stat().st_mtime) < 180:
                            found_file = fp
                            break
                    except Exception:
                        pass
                if found_file:
                    break

        if found_file:
            cur_sz = found_file.stat().st_size
            if cur_sz == dinfo.get("last_size", -1):
                dinfo["stable_checks"] = dinfo.get("stable_checks", 0) + 1
                if dinfo["stable_checks"] >= 2:  # Stable across 2 consecutive polls
                    img_ok = False
                    try:
                        with Image.open(found_file) as im:
                            im.verify()
                        img_ok = True
                    except Exception:
                        img_ok = False

                    if img_ok:
                        raw_path.parent.mkdir(parents=True, exist_ok=True)
                        if str(found_file) != str(raw_path):
                            try:
                                shutil.move(str(found_file), str(raw_path))
                            except Exception:
                                shutil.copy2(str(found_file), str(raw_path))
                                try:
                                    os.remove(str(found_file))
                                except Exception:
                                    pass
                        dinfo["state"] = "COMPLETE"
                        log(f"[{job_id}] DOWNLOAD COMPLETE & STABLE ({raw_path.stat().st_size // 1024} KB) -> Enqueuing for Edge WMR.")
                        asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
            else:
                dinfo["last_size"] = cur_sz
                dinfo["stable_checks"] = 0

        elif now - dinfo["started_at"] > 90.0:
            dinfo["state"] = "FAILED"
            log(f"[{job_id}] ⚠️ Filesystem download timed out after 90s!", file=sys.stderr)
            asyncio.create_task(_handle_job_failure(job_id, dinfo, "Download timed out waiting for file on disk"))

async def _finalize_and_clean_job(job_id, dinfo):
    raw_path = dinfo["raw_path"]
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
        except Exception:
            pass
        if dinfo.get("future") and not dinfo["future"].done():
            dinfo["future"].set_exception(e)
    finally:
        active_downloads.pop(job_id, None)

async def _handle_job_failure(job_id, dinfo, reason):
    counters["failed"] += 1
    gen = dinfo["gen"]
    job_id = dinfo["job_id"] if "job_id" in dinfo else job_id
    try:
        record_dead_letter(gen, reason, 1, 1, traceback.format_exc())
        sys.modules['credits'].refund_look(job_id, reason[:500])
    except Exception:
        pass
    if dinfo.get("future") and not dinfo["future"].done():
        dinfo["future"].set_exception(RuntimeError(reason))
    active_downloads.pop(job_id, None)

async def assign_jobs_to_idle_tabs():
    while not job_queue.empty():
        tid = find_first_idle_tab()
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
            # Healthy tab reuse: do NOT reload Gemini whole page
            start_new_chat(chrome_driver)

            # 1. Switch & verify Flash mode
            try:
                ensure_flash_mode(chrome_driver)
            except ModelLimitReached:
                _recover_stuck_tab(tid, "ModelLimitReached: Flash limit")
                return
            except Exception as e:
                _recover_stuck_tab(tid, f"Flash verification failed: {e}")
                return

            # 2. Activate & verify Create Image mode separately
            try:
                ensure_create_image_mode(chrome_driver, tid=tid)
            except Exception as e:
                _recover_stuck_tab(tid, f"Create Image activation failed: {e}")
                return

            # 3. Upload reference images and verify exact count
            ref_paths = [str(Path(p).resolve()) for p in info["refs"] if p and os.path.exists(p)]
            if not upload_reference_images(chrome_driver, ref_paths, tid=tid):
                _recover_stuck_tab(tid, f"Attachment count mismatch ({len(ref_paths)} references)")
                return

            # 4. Atomic prompt injection (CDP Input.insertText + normalized fingerprint verification)
            if not _inject_prompt_atomic(chrome_driver, info["prompt"], tid=tid):
                _recover_stuck_tab(tid, "Prompt atomic insertion verification failed")
                return

            info["urls_before"] = snapshot_urls(chrome_driver)
            info["chat_urls"] = set()

            # 5. Click Send button
            if not _click_send_button(chrome_driver):
                _recover_stuck_tab(tid, "Failed to click send button")
                return

            # 6. Verify generation started
            if not verify_generation_started(chrome_driver):
                _recover_stuck_tab(tid, "Generation started signal not detected after Send")
                return

            info["state"] = S_GEN_WAITING
            info["next_poll"] = time.time() + 1.2
            log(f"[T{tid}][{job_id}] PROMPT SENT & GENERATION STARTED! Tab T{tid} generating in background.")
    except Exception as e:
        log(f"[T{tid}][{job_id}] Submission error: {e}", file=sys.stderr)
        _recover_stuck_tab(tid, f"Submission error: {e}")

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

            # Independent per-tab timeout
            if now - info["start_time"] > GENERATION_TIMEOUT_S:
                log(f"[T{tid}][{info['job_id']}] HARD TIMEOUT after {GENERATION_TIMEOUT_S}s! Resetting tab T{tid} only.")
                _recover_stuck_tab(tid, "Generation timed out")
                continue

            status, new_src = nb_check_image(chrome_driver, info["urls_before"], info["chat_urls"])

            # Part J: Download click EXACTLY ONCE
            if status == 'SUCCESS' and not info["download_started"]:
                job_id = info["job_id"]
                info["download_started"] = True
                log(f"[T{tid}][{job_id}] IMAGE DETECTED! Initiating immediate capture...")

                job_dir = JOBS_DOWNLOAD_BASE / job_id
                job_dir.mkdir(parents=True, exist_ok=True)
                raw_path = job_dir / f"{job_id}_raw.png"
                files_before = set(os.listdir(job_dir)) if job_dir.exists() else set()

                # A: Instant direct memory / canvas capture (<150ms)
                direct_ok = _direct_fetch_cdp(chrome_driver, str(raw_path), info["urls_before"])
                if direct_ok:
                    info["urls_before"].add(new_src)
                    log(f"[T{tid}][{job_id}] INSTANT DIRECT CAPTURE ({raw_path.stat().st_size // 1024} KB) -> Immediate handoff to Edge WMR.")
                    dinfo = {
                        "job_id": job_id, "tab_id": tid, "job": info["job"], "gen": info["gen"],
                        "prompt": info["prompt"], "download_dir": job_dir, "raw_path": raw_path,
                        "files_before": files_before, "started_at": time.time(), "last_size": raw_path.stat().st_size,
                        "stable_checks": 3, "state": "COMPLETE", "future": info.get("future")
                    }
                    active_downloads[job_id] = dinfo
                    # Tab freed immediately!
                    _free_tab(tid, job_id)
                    asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
                else:
                    # B: Single-click hover download into isolated job directory
                    set_tab_download_dir(chrome_driver, job_dir)
                    hover_ok = _hover_and_dl_single_click(chrome_driver, info["urls_before"], info["chat_urls"])
                    info["urls_before"].add(new_src)
                    log(f"[T{tid}][{job_id}] DOWNLOAD CLICKED (success={hover_ok}) -> Handing off to disk watcher.")
                    active_downloads[job_id] = {
                        "job_id": job_id, "tab_id": tid, "job": info["job"], "gen": info["gen"],
                        "prompt": info["prompt"], "download_dir": job_dir, "raw_path": raw_path,
                        "files_before": files_before, "started_at": time.time(), "last_size": -1,
                        "stable_checks": 0, "state": "WAITING", "future": info.get("future")
                    }
                    # Tab freed immediately!
                    _free_tab(tid, job_id)

                # Immediately assign next queued job to this newly freed tab!
                if not job_queue.empty():
                    asyncio.create_task(assign_jobs_to_idle_tabs())
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

            else:  # WAITING
                if _send_btn_enabled(chrome_driver) and not _is_gemini_processing(chrome_driver):
                    info["stuck_polls"] += 1
                    if info["stuck_polls"] >= 8:
                        log(f"[T{tid}][{info['job_id']}] SOFT STUCK detected on tab T{tid}! Resetting tab T{tid} only.")
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

    # Full reload ONLY on recovery
    try:
        chrome_driver.switch_to.window(info["handle"])
        chrome_driver.get(GEMINI_APP_URL)
        time.sleep(1.0)
    except Exception:
        pass

    info["state"] = S_IDLE
    info["job"] = None
    info["job_id"] = None
    info["gen"] = None
    info["prompt"] = None
    info["download_started"] = False
    info["stuck_polls"] = 0
    info["start_time"] = 0.0
    info["future"] = None

    counters["failed"] += 1
    if gen:
        try:
            record_dead_letter(gen, reason, 1, 1, traceback.format_exc())
            sys.modules['credits'].refund_look(job_id, reason[:500])
        except Exception:
            pass
    if future and not future.done():
        future.set_exception(RuntimeError(reason))

    log(f"[T{tid}] TAB T{tid} RECOVERED & FREED. Ready for next job.")
    if not job_queue.empty():
        asyncio.create_task(assign_jobs_to_idle_tabs())

def print_pipeline_status():
    global last_status_print
    now = time.time()
    if now - last_status_print < 15.0:
        return
    last_status_print = now

    gen_count = sum(1 for st in tab_states if st["state"] == S_GEN_WAITING)
    dl_waiting_count = sum(1 for d in active_downloads.values() if d.get("state") == "WAITING")
    wmr_count = edge_wmr_worker.work_queue.qsize() if hasattr(edge_wmr_worker, "work_queue") else 0
    fin_count = sum(1 for d in active_downloads.values() if d.get("state") in ("COMPLETE", "FINALIZING"))

    print("\n" + "=" * 70)
    print(f"📊 PIPELINE STATUS [{time.strftime('%H:%M:%S')}]")
    print(f"  QUEUE: {job_queue.qsize()} | GENERATING: {gen_count} | DOWNLOAD_WAITING: {dl_waiting_count} | WMR: {wmr_count} | FINALIZING: {fin_count} | COMPLETED: {counters['completed']} | FAILED: {counters['failed']}")

    print("  TABS:")
    for tid in range(MAX_CONCURRENT_TABS):
        st = tab_states[tid]
        state = st["state"]
        jid = st["job_id"][:8] if st["job_id"] else "---"
        elapsed = f"{int(now - st['start_time'])}s" if st["start_time"] > 0 else "0s"
        print(f"    T{tid} = {state:<13} Job={jid} ({elapsed})")

    if active_downloads:
        print("  DOWNLOADS:")
        for jid, dinfo in list(active_downloads.items()):
            dst = dinfo.get("state", "UNKNOWN")
            el = f"{now - dinfo['started_at']:.1f}s"
            print(f"    Job {jid[:8]} = {dst} ({el})")
    print("=" * 70 + "\n")

async def central_scheduler_loop():
    while True:
        try:
            # STEP 1 — POLL ACTIVE FILE DOWNLOADS
            await poll_active_downloads()

            # STEP 2 — ASSIGN IDLE TABS (lowest-ID priority)
            await assign_jobs_to_idle_tabs()

            # STEP 3 — POLL ALL GENERATING TABS
            await poll_active_tabs()

            # STEP 4 — STATUS DISPLAY
            print_pipeline_status()
        except Exception as e:
            log(f"Scheduler loop error: {e}", file=sys.stderr)
        # STEP 5 — SHORT SCHEDULER SLEEP
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

    scheduler_task = asyncio.create_task(central_scheduler_loop())
    log(f"[{WORKER_ID}] waiting for jobs (Ctrl+C to stop)...")

    try:
        await scheduler_task
    except (KeyboardInterrupt, asyncio.CancelledError):
        log(f"\n[{WORKER_ID}] Stopping worker gracefully...")
    finally:
        await worker.close()
        try:
            chrome_driver.quit()
        except Exception:
            pass
        if edge_wmr_worker.driver:
            try:
                edge_wmr_worker.driver.quit()
            except Exception:
                pass

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())


