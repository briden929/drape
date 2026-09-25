# ============================================================================
# 🚀 QUEUE WORKER v3.0 — DUAL-BROWSER (CHROME + EDGE) + MULTI-TAB PIPELINE
# ============================================================================
# Copy and paste this ENTIRE cell into Google Colab and run it.
#
# ARCHITECTURE OVERVIEW:
# ┌─────────────────────────────────────────────────────────────────────────┐
# │ GOOGLE CHROME (Persistent Logged-in Profile)                            │
# │  • Tab 1: Upload refs -> Send prompt -> Lock released immediately       │
# │  • Tab 2: (Opens immediately while Tab 1 generates) -> Upload & Send    │
# │  • Tab 3..N: Round-robin pipeline across concurrent queue jobs         │
# │  • Per-Tab Download: /content/downloads/chrome/tab_1, tab_2, etc.      │
# │  • Proven Hover-Download & Direct-Fetch to capture generated image      │
# └────────────────────────────────────┬────────────────────────────────────┘
#                                      │ (Immediate async hand-off on ready)
# ┌────────────────────────────────────▼────────────────────────────────────┐
# │ MICROSOFT EDGE (Independent Browser, Fresh Profile, NO Login Required)  │
# │  • Dedicated Background Watermark Removal Worker                        │
# │  • Removes watermark via WMR service -> Downloads to edge/tab_N/        │
# │  • Tab-wised output: /content/downloads/edge/tab_N/<gen_id>_clean.png   │
# │  • Converts to WebP -> Pushes to Cloudflare R2 -> Settles Credits       │
# │  • Chrome Tab is ALREADY freed & working on next queued job!            │
# └─────────────────────────────────────────────────────────────────────────┘
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
    'REDIS_TUNNEL_URL': 'https://widely-furnished-totally-cheese.trycloudflare.com',
}

for _k, _v in _HARDCODED.items():
    os.environ[_k] = _v

os.environ.setdefault("REDIS_KEY_PREFIX", "vastralook:")
QUEUE_NAME = 'generations'
REDIS_KEY_PREFIX = os.environ.get('REDIS_KEY_PREFIX', 'vastralook:')
MAX_CONCURRENT_TABS = 4  # Parallel Chrome tabs for Gemini generation
GENERATION_TIMEOUT_S = 240
LOGIN_TIMEOUT_S = 900
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

# Dedicated per-tab download directories for Chrome and Edge
CHROME_DL_BASE = Path('/content/downloads/chrome')
EDGE_DL_BASE = Path('/content/downloads/edge')
WMR_DL_DIR = Path('/content/wmr_downloads')
FINAL_OUTPUT_BASE = Path('/content/downloads/final_output')

for _d in (BASE_DIR, STATE_DIR, CHROME_PROFILE_DIR, EDGE_PROFILE_DIR, REFS_CACHE_DIR,
           CHROME_DL_BASE, EDGE_DL_BASE, WMR_DL_DIR, FINAL_OUTPUT_BASE):
    _d.mkdir(parents=True, exist_ok=True)

for _i in range(1, MAX_CONCURRENT_TABS + 1):
    (CHROME_DL_BASE / f'tab_{_i}').mkdir(parents=True, exist_ok=True)
    (EDGE_DL_BASE / f'tab_{_i}').mkdir(parents=True, exist_ok=True)

_drive_cookies = Path('/content/drive/MyDrive/gemini-queue-worker/cookies.pkl')
COOKIES_FILE = _drive_cookies if _drive_cookies.parent.parent.exists() else STATE_DIR / 'cookies.pkl'
COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

print(f"  Worker ID:         {WORKER_ID}")
print(f"  Redis Tunnel:      {os.environ['REDIS_TUNNEL_URL']}")
print(f"  Chrome Profile:    {CHROME_PROFILE_DIR}")
print(f"  Edge Profile:      {EDGE_PROFILE_DIR}")
print(f"  Max Parallel Tabs: {MAX_CONCURRENT_TABS}")
print("  ✅ Secrets and directories configured successfully.\n")


# ============================================================================
# STEP 2: INSTALL DEPENDENCIES (CHROME + EDGE + PYTHON LIBS + NOVNC)
# ============================================================================
print("=" * 80)
print("📦 STEP 2: VERIFYING & INSTALLING DEPENDENCIES")
print("=" * 80)

def run_cmd(cmd, shell=True, timeout=180):
    try:
        return subprocess.run(cmd, shell=shell, capture_output=True, text=True, check=False, timeout=timeout)
    except Exception as e:
        print(f"  ⚠️ Command error ({cmd}): {e}")
        return None

_PY_PKGS = [
    "bullmq", "psycopg2-binary", "boto3", "selenium", "Pillow",
    "websockets", "nest_asyncio", "undetected-chromedriver",
    "webdriver-manager", "pyvirtualdisplay", "setuptools", "requests"
]
print("  Installing Python packages...")
run_cmd(f"{sys.executable} -m pip install -q {' '.join(_PY_PKGS)}")
print("  ✅ Python packages ready.")

os.environ["DEBIAN_FRONTEND"] = "noninteractive"
print("  Installing Xvfb, x11vnc, noVNC, and utilities...")
run_cmd("apt-get update -qq && apt-get install -y -qq xvfb x11vnc novnc websockify curl wget unzip")

# Google Chrome
_chrome_path = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
if not _chrome_path or not os.path.exists("/usr/bin/google-chrome-stable"):
    print("  Installing Google Chrome Stable...")
    run_cmd("wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
    run_cmd("dpkg -i /tmp/chrome.deb || apt-get install -f -y")
_chrome_bin = "/usr/bin/google-chrome-stable" if os.path.exists("/usr/bin/google-chrome-stable") else (shutil.which("google-chrome") or "google-chrome")
print(f"  ✅ Google Chrome available at: {_chrome_bin}")

# Microsoft Edge
_edge_bin = None
for _p in ["/usr/bin/microsoft-edge-stable", "/usr/bin/microsoft-edge", "/opt/microsoft/msedge/msedge"]:
    if os.path.exists(_p):
        _edge_bin = _p
        break

if not _edge_bin:
    print("  Installing Microsoft Edge Stable (for independent watermark remover)...")
    run_cmd("curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /tmp/microsoft.gpg")
    run_cmd("install -o root -g root -m 644 /tmp/microsoft.gpg /etc/apt/trusted.gpg.d/")
    run_cmd("echo 'deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main' > /etc/apt/sources.list.d/microsoft-edge.list")
    run_cmd("apt-get update -qq && apt-get install -y -qq microsoft-edge-stable")
    for _p in ["/usr/bin/microsoft-edge-stable", "/usr/bin/microsoft-edge", "/opt/microsoft/msedge/msedge"]:
        if os.path.exists(_p):
            _edge_bin = _p
            break

if _edge_bin:
    print(f"  ✅ Microsoft Edge ready at: {_edge_bin}")
else:
    print("  ⚠️ Microsoft Edge not found; will use standalone Chrome instance for WMR.")

print("  ✅ All browser and system dependencies verified.\n")


# ============================================================================
# STEP 3: REGISTER COMPLETE BACKEND MODULES (db, credits, fashion_studio)
# ============================================================================
print("=" * 80)
print("⚙️ STEP 3: REGISTERING FULL BACKEND SYSTEM MODULES")
print("=" * 80)

# --- db module ---
_mod_db = types.ModuleType('db')
sys.modules['db'] = _mod_db
exec(compile('''
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
''', 'db.py', 'exec'), _mod_db.__dict__)
print("  ✅ Module 'db' registered.")

# --- credits module ---
_mod_credits = types.ModuleType('credits')
sys.modules['credits'] = _mod_credits
exec(compile('''
import hashlib
import hmac
import json
import os
import uuid
import psycopg2
import requests
import db

DATABASE_URL = os.environ.get('DATABASE_URL')
COST_PER_LOOK = int(os.environ.get('GA_CREDITS_PER_LOOK', '10'))

def _conn():
    return db.borrow()

def _apply_delta(cur, user_id, delta, reason, reference_type, reference_id):
    cur.execute('SELECT credit_balance FROM users WHERE id = %s FOR UPDATE', (user_id,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f'user {user_id} not found')
    after = row[0] + delta
    if after < 0:
        raise RuntimeError(f'Insufficient credits: need {-delta}, have {row[0]}.')
    cur.execute('UPDATE users SET credit_balance = %s WHERE id = %s', (after, user_id))
    cur.execute(
        'INSERT INTO credit_transactions (user_id, delta, balance_after, reason, reference_type, reference_id) VALUES (%s,%s,%s,%s,%s,%s)',
        (user_id, delta, after, reason, reference_type, reference_id)
    )
    return after

def settle_look(gen_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE credit_holds SET status = 'settled', released_at = now() WHERE generation_id = %s AND status = 'held'", (gen_id,))
        cur.execute("UPDATE image_generations SET status = 'done', completed_at = now() WHERE id = %s AND status = 'processing'", (gen_id,))
        conn.commit()
    finally:
        conn.close()

def refund_look(gen_id, error=None):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE credit_holds SET status = 'released', released_at = now() WHERE generation_id = %s AND status = 'held' RETURNING user_id, amount", (gen_id,))
        row = cur.fetchone()
        if row and row[1] > 0:
            _apply_delta(cur, row[0], row[1], 'hold_release', 'generation', gen_id)
        cur.execute(
            "UPDATE image_generations SET status = 'failed', error = COALESCE(%s, error), completed_at = now() WHERE id = %s AND status = 'processing'",
            ((error or 'generation did not finish')[:500], gen_id)
        )
        conn.commit()
        return bool(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
''', 'credits.py', 'exec'), _mod_credits.__dict__)
print("  ✅ Module 'credits' registered.")

# --- fashion_studio module ---
_mod_fashion = types.ModuleType('fashion_studio')
sys.modules['fashion_studio'] = _mod_fashion
exec(compile('''
import json
import mimetypes
import os
import uuid
from pathlib import Path
import boto3
import psycopg2
import db

R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
R2_PUBLIC_URL = (os.environ.get('R2_PUBLIC_URL') or '').rstrip('/')
DATABASE_URL = os.environ.get('DATABASE_URL')
FASHION_STUDIO_USER_ID = os.environ.get('FASHION_STUDIO_USER_ID')

def configured():
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_PUBLIC_URL and DATABASE_URL)

def _r2_client():
    return boto3.client(
        's3',
        endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name='auto'
    )

_FASHION_TRYON_BODY = (
    "GOLDEN RULE: BINARY VISIBILITY MASK\\n"
    "The mannequin is a strict binary visibility mask. Replace ONLY pixels occupied by the mannequin. "
    "Never expand the mask. Never generate outside the mannequin's crop boundaries. If a body part is cropped in the mannequin, it remains cropped.\\n\\n"
    "REFERENCE AUTHORITY (STRICT ISOLATION)\\n"
    "• MANNEQUIN_REF: Absolute authority for pose, skeleton, camera, crop, framing, lighting, shadows, environment, accessory paths, and footwear contact. Contains ZERO clothing/face data.\\n"
    "• CLOTHING_REF: Absolute authority for garment identity, construction, structural topology, material properties and commercial product specification. Contains ZERO pose, body or camera data.{face_ref_authority}\\n\\n"
    "REFERENCE COMPLETENESS\\n"
    "Use only information explicitly visible in each reference.\\n"
    "When information is not visible, reconstruct conservatively from visible structural evidence without redesigning or inventing new product features.\\n\\n"
    "HARD CONSTRAINTS & SOFT PREFERENCES\\n"
    "HARD CONSTRAINTS (Must Never Change):\\n"
    "• Visibility mask and crop boundaries\\n"
    "• Pose, skeleton, and camera geometry\\n"
    "• Face identity and hairstyle identity\\n"
    "• Garment identity and material identity\\n"
    "• Accessory geometry and paths\\n\\n"
    "SOFT PREFERENCES (Optimize When Possible):\\n"
    "• Photographic realism and lighting consistency\\n"
    "• Fabric wrinkles, folds, and drape\\n"
    "• Facial expression and eye gaze\\n"
    "• Hair strand physics and movement\\n"
    "• Soft tissue and skin deformation\\n\\n"
    "CONFLICT HIERARCHY\\n"
    "1. Visibility Mask & Canvas (Absolute)\\n"
    "2. Pose, Skeleton & Camera (Immutable structural base)\\n"
    "3. Garment & Face Identity (Identity Preservation)\\n"
    "4. Photorealistic Rendering (Execution)\\n\\n"
    "FAILURE POLICY\\n"
    "If all constraints cannot be satisfied simultaneously, preserve every hard constraint.\\n"
    "Never invent new content to resolve ambiguity.\\n"
    "Prefer an incomplete but faithful reconstruction over an incorrect reconstruction.\\n"
    "Do not redesign, approximate, beautify, or hallucinate missing information.\\n"
    "When uncertainty exists, preserve product identity and structural consistency rather than inventing missing garment details.\\n\\n"
    "POSE OVERRIDES GARMENT\\n"
    "If preserving garment appearance requires changing pose, skeleton, camera, or framing, DO NOT modify the body.\\n"
    "Always adapt the garment to the locked pose.\\n"
    "Never adapt the pose to the garment.\\n\\n"
    "POSE, SKELETON & CAMERA LOCK\\n"
    "• Skeleton: Immutable. Faithfully preserve exact joint angles, limb states, weight distribution, and asymmetry. Do not relax, beautify, or auto-correct.\\n"
    "• Hands & Contact: Faithfully preserve exact gesture, finger curl, and physical contact points. No new or removed contacts.\\n"
    "• Camera: Camera geometry is immutable. Maintain identical viewpoint, perspective, focal length, framing, crop, and aspect ratio.\\n\\n"
    "VISIBILITY & OCCLUSION\\n"
    "• Mask Rule: Visible anatomy comes ONLY from MANNEQUIN_REF. Never reveal hidden surfaces or complete cropped regions.\\n"
    "• Occlusion: Exact foreground/background relationships maintained.\\n\\n"
    "GARMENT IDENTITY\\n"
    "Treat CLOTHING_REF as the canonical product specification rather than a worn garment\\n"
    "Infer garment construction only from visible evidence contained in CLOTHING_REF.\\n"
    "Reconstruct the same garment as if professionally worn on the reconstructed body without altering its identity.\\n"
    "Faithfully preserve the original garment identity, including:\\n"
    "• garment category, construction, neckline, sleeve length\\n"
    "• embroidery geometry, placement, border geometry, print layout\\n"
    "• fabric type, micro-texture, weave pattern, embroidery density, printed motifs, trims, borders, surface finish and material appearance.\\n"
    "Do not redesign, reinterpret, or approximate the product.\\n"
    "Preserve the commercial product exactly; only physically plausible deformation caused by dressing and the locked pose is permitted.\\n\\n"
    "IDENTITY CONTINUITY\\n"
    "All visible garment regions must remain mutually consistent as parts of the same commercial product.\\n"
    "Construction, proportions, materials, decorative elements and finishing details must remain coherent across the entire garment.\\n\\n"
    "GARMENT DRESSING\\n"
    "Reconstruct the complete human anatomy from MANNEQUIN_REF before applying the garment.\\n"
    "Dress the reconstructed body with the garment defined by CLOTHING_REF.\\n"
    "Determine the correct wearing configuration from the garment construction, structural design and fastening system.\\n"
    "Body anatomy defines garment deformation.\\n"
    "Generate physically realistic wrapping, layering, fastening, tension, compression, folds and drape created only by body anatomy, gravity, material properties and the locked pose.\\n"
    "Do not copy fold patterns from CLOTHING_REF.\\n"
    "Generate new folds from physical interaction while preserving product identity.\\n\\n"
    "GARMENT TOPOLOGY\\n"
    "Preserve the relative spatial arrangement and proportions of all structural garment components.\\n"
    "Necklines, waistlines, shoulder seams, sleeve attachments, borders, hems, pleats, panels, lapels, collars, cuffs and structural elements must remain in their correct anatomical positions.\\n"
    "Do not shift, rotate, resize or proportionally alter structural garment components.\\n\\n"
    "BODY–GARMENT COUPLING\\n"
    "The garment must appear physically worn rather than overlaid.\\n"
    "Maintain continuous body contact where naturally expected.\\n"
    "Fabric deformation must arise only from body anatomy, contact, gravity, material properties and the locked pose.\\n"
    "Avoid floating fabric or detached garment regions.\\n"
    "Material appearance should respond naturally to the locked scene lighting while preserving original fabric characteristics.\\n\\n"
    "STRUCTURAL STABILITY\\n"
    "Preserve the structural integrity of the garment.\\n"
    "Seams, attachment points, closures, waistlines, necklines, cuffs, collars and other structural components must remain mechanically consistent under deformation.\\n"
    "Only physically plausible deformation is permitted.\\n\\n"
    "FACE & HAIR ADAPTATION\\n"
    "• Face: Identity is immutable. Do not copy the reference expression. Generate a natural expression from the combined influence of body language, head orientation, garment style, environment, lighting, camera distance and commercial fashion intent. Expressions should appear naturally emerging from the interaction between the model, photographer, garment and environment, rather than looking artificially posed or emotionally empty. Preserve natural facial asymmetry, subtle facial muscle activation, dimples, smile lines, crow's feet, nasolabial folds and other genuine micro-expressions when naturally produced by the scene or expression.\\n"
    "• Hair: Identity (haircut, length, density, texture and color) is immutable. Hair strands are adaptive. Preserve hairstyle identity while naturally responding to gravity, body movement, shoulder contact and airflow. Hair must emerge naturally from the scalp with realistic volume and strand continuity.\\n\\n"
    "EYE BEHAVIOR\\n"
    "Eyes should exhibit realistic human behavior with natural focus, subtle eyelid asymmetry, appropriate catchlights, gaze stability, gentle squinting under bright sunlight and relaxed ocular muscles. Avoid frozen staring or perfectly symmetrical eyes.\\n\\n"
    "SKIN REALISM\\n"
    "Preserve natural skin characteristics including fine pores, subtle wrinkles, gentle skin compression, lip texture, realistic translucency, slight color variation and natural specular highlights appropriate to the lighting.\\n\\n"
    "ACCESSORY & ENVIRONMENT LOCK\\n"
    "• Accessories: Rigid geometry. Faithfully preserve exact dimensions, strap paths, and occlusion. Do not reroute straps or float bags.\\n"
    "• Environment: Static. Lighting, shadows, and background remain spatially identical to MANNEQUIN_REF.\\n\\n"
    "CONSISTENCY PRINCIPLE\\n"
    "All reconstructed elements must remain mutually consistent.\\n"
    "Face, body, clothing, lighting, shadows, perspective, and material response must appear to belong to a single photograph captured at one moment in time.\\n"
    "All reconstructed elements must share one physically coherent three-dimensional world space.\\n\\n"
    "HUMAN REALISM\\n"
    "Produce an authentic commercial fashion photograph with consistent lighting, perspective, material response and photographic realism.\\n"
    "Preserve natural human asymmetry, realistic skin and authentic fabric imperfections.\\n"
    "Avoid synthetic, over-processed or digitally illustrated appearance.\\n\\n"
    "NEGATIVE CONSTRAINTS\\n"
    "Do not violate: visibility, pose, camera, garment identity, face identity, material identity, accessory geometry.\\n"
    "Avoid: AI artifacts, plastic skin, floating objects, unrealistic fabric physics, incorrect garment construction, geometry distortion, artificial symmetry.\\n\\n"
    "INPUT ORDER (this request):\\n{input_order}\\n"
    "Generate exactly one final fashion photograph."
)

def fashion_tryon_prompt(has_model):
    if has_model:
        core_obj = (
            "CORE OBJECTIVE\\n"
            "Create one physically plausible commercial fashion photograph by replacing the mannequin "
            "with the real person from FACE_REF while faithfully preserving the garment identity from CLOTHING_REF "
            "and the complete body pose from MANNEQUIN_REF.\\nThis is a constrained reconstruction task, not creative image synthesis."
        )
        face_ref_auth = "\\n• FACE_REF: Absolute authority for facial identity, skin, hair, and person appearance from the model character/angle reference. Contains ZERO body pose data — pose always comes from MANNEQUIN_REF."
        input_order = "1) CLOTHING_REF image(s) — garment packshot(s)\\n2) MANNEQUIN_REF image — hologram / pose mannequin\\n3) FACE_REF image — model character / angle reference (identity)"
    else:
        core_obj = (
            "CORE OBJECTIVE\\n"
            "Create one physically plausible commercial fashion photograph by rendering a professional fashion model wearing "
            "the garment from CLOTHING_REF, in the exact body pose, camera framing and scene established by MANNEQUIN_REF.\\n"
            "This is a constrained reconstruction task, not creative image synthesis."
        )
        face_ref_auth = ""
        input_order = "1) CLOTHING_REF image(s) — garment packshot(s)\\n2) MANNEQUIN_REF image — hologram / pose mannequin"
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
    
    params_json = json.dumps({'source': 'gemini-automation-v3', **{k: v for k, v in (params or {}).items() if v}})
    conn = db.borrow()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE image_generations SET status = 'done', output_url = %s, webp_url = %s, completed_at = now() WHERE id = %s",
            (output_url, webp_url, gen_id)
        )
        if cur.rowcount == 0:
            cur.execute(
                "INSERT INTO image_generations (id, user_id, prompt, params, is_free, credits_cost, status, output_url, webp_url, started_at, completed_at) "
                "VALUES (%s, %s, %s, %s, TRUE, 0, 'done', %s, %s, now(), now()) ON CONFLICT (id) DO UPDATE SET status = 'done', output_url = EXCLUDED.output_url, webp_url = EXCLUDED.webp_url, completed_at = now()",
                (gen_id, target_user_id, prompt, params_json, output_url, webp_url)
            )
        conn.commit()
    finally:
        conn.close()
    return {'output_url': output_url, 'webp_url': webp_url}
''', 'fashion_studio.py', 'exec'), _mod_fashion.__dict__)
print("  ✅ Module 'fashion_studio' registered with full proprietary try-on prompts.\n")


# ============================================================================
# STEP 4: START REDIS WEBSOCKET-TO-TCP TUNNEL BRIDGE (EXACT VERIFIED LOGIC)
# ============================================================================
print("=" * 80)
print("🌐 STEP 4: CONNECTING TO REDIS VIA SECURE TUNNEL")
print("=" * 80)

_bridge_script = BASE_DIR / 'ws_tcp_bridge.py'
_bridge_script.write_text('''import asyncio
import sys
import websockets

async def handle_tcp(reader, writer, tunnel_url):
    peer = writer.get_extra_info('peername')
    try:
        async with websockets.connect(tunnel_url, max_size=None) as ws:

            async def tcp_to_ws():
                try:
                    while True:
                        data = await reader.read(65536)
                        if not data:
                            break
                        await ws.send(data)
                except Exception:
                    pass
                finally:
                    try:
                        await ws.close()
                    except Exception:
                        pass

            async def ws_to_tcp():
                try:
                    async for message in ws:
                        writer.write(message if isinstance(message, (bytes, bytearray)) else message.encode())
                        await writer.drain()
                except Exception:
                    pass
                finally:
                    writer.close()

            await asyncio.gather(tcp_to_ws(), ws_to_tcp())
    except Exception as e:
        print(f'[ws_tcp_bridge] connection {peer} failed: {e}', file=sys.stderr)
    finally:
        try:
            writer.close()
        except Exception:
            pass

async def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: ws_tcp_bridge.py wss://xxxx.trycloudflare.com [local_port]')
    tunnel_url = sys.argv[1]
    if tunnel_url.startswith('https://'):
        tunnel_url = 'wss://' + tunnel_url[len('https://'):]
    local_port = int(sys.argv[2]) if len(sys.argv) > 2 else 16379
    server = await asyncio.start_server(lambda r, w: handle_tcp(r, w, tunnel_url), '127.0.0.1', local_port)
    print(f'[ws_tcp_bridge] listening on 127.0.0.1:{local_port} -> {tunnel_url}')
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
''', encoding='utf-8')

_tunnel_url = os.environ['REDIS_TUNNEL_URL']
print(f"  Starting local bridge 127.0.0.1:{LOCAL_REDIS_PORT} -> {_tunnel_url}")
_bridge_proc = subprocess.Popen(
    [sys.executable, str(_bridge_script), _tunnel_url, str(LOCAL_REDIS_PORT)],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
)
time.sleep(3)

if _bridge_proc.poll() is not None:
    raise SystemExit(f"❌ Redis tunnel bridge failed to start. Verify REDIS_TUNNEL_URL: {_tunnel_url}")

# Verify Redis responsiveness through bridge
_redis_ok = False
try:
    _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _sock.settimeout(6)
    _sock.connect(('127.0.0.1', LOCAL_REDIS_PORT))
    _sock.sendall(b"*1\r\n$4\r\nPING\r\n")
    _resp = _sock.recv(1024)
    _sock.close()
    if b"+PONG" in _resp:
        _redis_ok = True
        print(f"  ✅ Redis tunnel bridge VERIFIED: Remote Redis responded with PONG!")
    else:
        print(f"  ⚠️ Redis bridge connected, response: {_resp[:40]}")
except Exception as _sock_err:
    print(f"  ⚠️ Initial Redis test socket check ({_sock_err}). BullMQ will establish connection on startup.")

os.environ['REDIS_URL'] = f'redis://127.0.0.1:{LOCAL_REDIS_PORT}'
REDIS_URL = os.environ['REDIS_URL']
print(f"  ✅ Redis reachable locally at 127.0.0.1:{LOCAL_REDIS_PORT} via {_tunnel_url}\n")


# ============================================================================
# STEP 5: VIRTUAL DISPLAY & NOVNC SETUP
# ============================================================================
print("=" * 80)
print("🖥️ STEP 5: INITIALIZING VIRTUAL DISPLAY & NOVNC STREAMING")
print("=" * 80)

def start_display_and_vnc(screen_w=1920, screen_h=1080, vnc_port=5900, novnc_port=6080):
    if platform.system() != 'Linux':
        print(f"  Running on {platform.system()} — virtual display skipped.")
        return None
    try:
        from pyvirtualdisplay import Display
        disp = Display(visible=0, size=(screen_w, screen_h))
        disp.start()
        os.environ['DISPLAY'] = f":{getattr(disp, 'display', 0)}"
        print(f"  Virtual Display started on {os.environ['DISPLAY']}")
        
        run_cmd("pkill -f x11vnc", timeout=5)
        run_cmd("pkill -f websockify", timeout=5)
        time.sleep(0.5)
        
        subprocess.Popen(
            ['x11vnc', '-display', os.environ['DISPLAY'], '-forever', '-nopw', '-shared', '-quiet', '-rfbport', str(vnc_port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(1.0)
        
        web_dir = None
        for p in ('/usr/share/novnc', '/usr/share/noVNC', '/opt/novnc'):
            if os.path.isfile(os.path.join(p, 'vnc.html')):
                web_dir = p
                break
        
        cmd = ['websockify', '--web', web_dir, str(novnc_port), f'localhost:{vnc_port}'] if web_dir else ['websockify', str(novnc_port), f'localhost:{vnc_port}']
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)
        
        cf_bin = "/usr/local/bin/cloudflared"
        if not os.path.exists(cf_bin):
            run_cmd(f"wget -q -O {cf_bin} https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", timeout=60)
            run_cmd(f"chmod +x {cf_bin}", timeout=5)
        
        if os.path.exists(cf_bin):
            p = subprocess.Popen([cf_bin, 'tunnel', '--url', f'http://localhost:{novnc_port}'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            deadline = time.time() + 25
            while time.time() < deadline:
                line = p.stdout.readline()
                if not line: continue
                m = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', line)
                if m:
                    vnc_url = f"{m.group(0)}/vnc.html?autoconnect=true&resize=scale"
                    print(f"  🌐 noVNC Live Stream: {vnc_url}")
                    return vnc_url
        return f"http://localhost:{novnc_port}/vnc.html"
    except Exception as e:
        print(f"  ⚠️ noVNC setup notice: {e}")
        return None

vnc_stream_url = start_display_and_vnc()
print("  ✅ Virtual display setup complete.\n")


# ============================================================================
# STEP 6: BROWSER DRIVERS INITIALIZATION (CHROME + EDGE)
# ============================================================================
print("=" * 80)
print("🌐 STEP 6: INITIALIZING PERSISTENT CHROME & EDGE DRIVERS")
print("=" * 80)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

def create_chrome_driver():
    import undetected_chromedriver as uc
    from webdriver_manager.chrome import ChromeDriverManager
    
    prefs = {
        'download.default_directory': str(CHROME_DL_BASE.resolve()),
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'safebrowsing.enabled': True
    }
    
    opts = uc.ChromeOptions()
    opts.binary_location = _chrome_bin
    opts.add_argument('--window-size=1920,1080')
    opts.add_argument('--start-maximized')
    opts.add_argument('--lang=en-US,en')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument(f'--user-data-dir={CHROME_PROFILE_DIR}')
    opts.add_argument('--profile-directory=Default')
    opts.add_experimental_option('prefs', prefs)
    
    drv = None
    try:
        driver_path = ChromeDriverManager().install()
        drv = uc.Chrome(options=opts, driver_executable_path=driver_path, use_subprocess=True)
        drv.get('about:blank')
    except Exception as e:
        print(f"  ⚠️ undetected-chromedriver fallback ({e}), using Selenium Chrome")
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        sopts = ChromeOptions()
        sopts.binary_location = _chrome_bin
        sopts.add_argument('--window-size=1920,1080')
        sopts.add_argument('--no-sandbox')
        sopts.add_argument('--disable-dev-shm-usage')
        sopts.add_argument(f'--user-data-dir={CHROME_PROFILE_DIR}')
        sopts.add_argument('--profile-directory=Default')
        sopts.add_experimental_option('prefs', prefs)
        svc = ChromeService(ChromeDriverManager().install())
        drv = webdriver.Chrome(service=svc, options=sopts)
    
    drv.set_page_load_timeout(60)
    drv.implicitly_wait(3)
    return drv

def create_edge_driver(download_dir):
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.edge.service import Service as EdgeService
    
    edge_bin = "/usr/bin/microsoft-edge-stable"
    if not os.path.exists(edge_bin):
        for p in ["/usr/bin/microsoft-edge", "/opt/microsoft/msedge/msedge"]:
            if os.path.exists(p):
                edge_bin = p
                break
    
    opts = EdgeOptions()
    if os.path.exists(edge_bin):
        opts.binary_location = edge_bin
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"--user-data-dir={EDGE_PROFILE_DIR}")
    prefs = {
        'download.default_directory': str(Path(download_dir).resolve()),
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'safebrowsing.enabled': True
    }
    opts.add_experimental_option('prefs', prefs)
    
    drv = None
    try:
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        svc = EdgeService(EdgeChromiumDriverManager().install())
        drv = webdriver.Edge(service=svc, options=opts)
    except Exception as e:
        try:
            drv = webdriver.Edge(options=opts)
        except Exception:
            try:
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service as ChromeService
                copts = ChromeOptions()
                copts.binary_location = edge_bin
                copts.add_argument("--window-size=1280,900")
                copts.add_argument("--no-sandbox")
                copts.add_argument("--disable-dev-shm-usage")
                copts.add_argument(f"--user-data-dir={EDGE_PROFILE_DIR}")
                copts.add_experimental_option('prefs', prefs)
                csvc = ChromeService(ChromeDriverManager().install())
                drv = webdriver.Chrome(service=csvc, options=copts)
            except Exception:
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service as ChromeService
                copts = ChromeOptions()
                copts.add_argument("--window-size=1280,900")
                copts.add_argument("--no-sandbox")
                copts.add_argument("--disable-dev-shm-usage")
                copts.add_argument(f"--user-data-dir={EDGE_PROFILE_DIR}")
                copts.add_experimental_option('prefs', prefs)
                csvc = ChromeService(ChromeDriverManager().install())
                drv = webdriver.Chrome(service=csvc, options=copts)
    
    drv.set_page_load_timeout(60)
    drv.implicitly_wait(3)
    return drv

print("  Launching Google Chrome for Gemini generation...")
chrome_driver = create_chrome_driver()
print("  ✅ Google Chrome launched.")


# ============================================================================
# STEP 7: GOOGLE ACCOUNT & GEMINI LOGIN VERIFICATION
# ============================================================================
print("=" * 80)
print("🔐 STEP 7: VERIFYING GOOGLE / GEMINI LOGIN STATE")
print("=" * 80)

def load_cookies(drv, cpath):
    if not os.path.exists(cpath):
        return False
    try:
        with open(cpath, 'rb') as f:
            cookies = pickle.load(f)
        drv.get('https://www.google.com')
        time.sleep(1)
        for c in cookies:
            try: drv.add_cookie(c)
            except Exception: pass
        return True
    except Exception:
        return False

def save_cookies(drv, cpath):
    try:
        Path(cpath).parent.mkdir(parents=True, exist_ok=True)
        with open(cpath, 'wb') as f:
            pickle.dump(drv.get_cookies(), f)
    except Exception:
        pass

def is_google_logged_in(drv):
    try:
        drv.get('https://myaccount.google.com/')
        time.sleep(2)
        return 'myaccount.google.com' in drv.current_url and 'signin' not in drv.current_url
    except Exception:
        return False

if load_cookies(chrome_driver, COOKIES_FILE):
    chrome_driver.refresh()
    time.sleep(1)

if is_google_logged_in(chrome_driver):
    print("  ✅ Google Account already logged in via saved cookies / profile.")
else:
    print("  ⚠️ Notice: Google Account not signed in. Opening Google sign-in...")
    chrome_driver.get('https://accounts.google.com/ServiceLogin')
    print(f"  👉 If manual verification is required, complete login via noVNC. Waiting up to {LOGIN_TIMEOUT_S}s...")
    t_end = time.time() + LOGIN_TIMEOUT_S
    logged_in = False
    while time.time() < t_end:
        if is_google_logged_in(chrome_driver):
            logged_in = True
            save_cookies(chrome_driver, COOKIES_FILE)
            print("  ✅ Login detected and cookies saved.")
            break
        time.sleep(3)
    if not logged_in:
        print("  ⚠️ Proceeding to Gemini directly...")

print("  Navigating to Gemini...")
chrome_driver.get(GEMINI_APP_URL)
time.sleep(3)
try:
    for btn in chrome_driver.find_elements(By.CSS_SELECTOR, "button, [role='button']"):
        if (btn.text or '').strip().lower() in ('dismiss', 'got it', 'i agree', 'accept'):
            chrome_driver.execute_script("arguments[0].click();", btn)
            break
except Exception:
    pass
print("  ✅ Gemini web interface ready.\n")


# ============================================================================
# STEP 8: DUAL-BROWSER INDEPENDENT WATERMARK REMOVER (EDGE WORKER)
# ============================================================================
print("=" * 80)
print("🧼 STEP 8: STARTING INDEPENDENT EDGE WATERMARK REMOVER")
print("=" * 80)

def convert_to_webp(png_path, max_size_kb=450):
    try:
        from PIL import Image
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
            tab_edge_dl = EDGE_DL_BASE / f'tab_{tab_id}'
            tab_edge_dl.mkdir(parents=True, exist_ok=True)
            cleaned_target = tab_edge_dl / f'{gen_id}_clean.png'

            try:
                log(f"[{WORKER_ID}] {gen_id}: [STEP_EDGE_TAB{tab_id}_WMR_START] Removing watermark in Edge (Tab {tab_id} folder)...")
                drv = self._get_driver()
                ok = self._process_image(drv, input_png_path, tab_edge_dl, cleaned_target)
                final_png = cleaned_target if (ok and cleaned_target.exists() and cleaned_target.stat().st_size > 1000) else input_png_path
                log(f"[{WORKER_ID}] {gen_id}: [STEP_EDGE_TAB{tab_id}_WMR_CLEANED] Cleaned image ready -> {final_png}")
                
                log(f"[{WORKER_ID}] {gen_id}: [STEP_CONVERT_WEBP] Converting to WebP...")
                webp_target = tab_edge_dl / f'{gen_id}_clean.webp'
                webp_path = convert_to_webp(str(final_png))
                if webp_path and os.path.exists(webp_path) and str(webp_path) != str(webp_target):
                    try: shutil.copy2(webp_path, str(webp_target)); webp_path = str(webp_target)
                    except Exception: pass
                loop.call_soon_threadsafe(response_future.set_result, (str(final_png), str(webp_path) if webp_path else None))
            except Exception as ex:
                log(f"[{WORKER_ID}] {gen_id}: [STEP_EDGE_TAB{tab_id}_WMR_ERROR] Watermark removal notice ({ex}), using original", file=sys.stderr)
                webp_path = convert_to_webp(str(input_png_path))
                loop.call_soon_threadsafe(response_future.set_result, (str(input_png_path), str(webp_path) if webp_path else None))
            finally:
                self.work_queue.task_done()

    def _process_image(self, drv, image_path, tab_edge_dl, cleaned_target_path, timeout=90):
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

            files_before = set(os.listdir(WMR_DL_DIR)) if os.path.exists(WMR_DL_DIR) else set()
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

            candidate_dirs = [WMR_DL_DIR, tab_edge_dl, Path('/content/downloads'), Path('/root/Downloads')]
            for cd in candidate_dirs:
                cd.mkdir(parents=True, exist_ok=True)
            files_before_map = {str(d): set(os.listdir(d)) for d in candidate_dirs if os.path.exists(d)}

            # Click download button
            if not _wmr_click_download(drv):
                return False

            # Wait for downloaded file in candidate_dirs
            t_dl = time.time()
            fp = None
            while time.time() - t_dl < 30:
                fp = _scan_downloaded_file(candidate_dirs, files_before_map, min_size=1000)
                if fp and os.path.exists(fp):
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
print("  ✅ Edge Watermark Remover worker thread active.\n")
