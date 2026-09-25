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
