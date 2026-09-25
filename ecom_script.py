# @title 🚀 ECOM 2 ITERATION
# ============================================================================
# ✅ Xvfb + visible Chrome (NOT headless)
# ✅ noVNC remote desktop
# ✅ 6 Tabs — TRUE MULTI-TAB POLLING
# ✅ PACK-WISE processing: model + cloth matched ONCE per pack (from FULL json),
#    reused for every image inside that pack's WR folder.
# ✅ Filename format: WR renders are named
#    {PackID}.{n}.{studio}.WR.{desc}.ext   e.g.  131.6.f360.WR.png
#    (desc is optional — parser handles both cases)
# ✅ MODEL SOURCE: model_index.json is a FIXED CATALOG of named
#    models — {"models":[{"no":"M001","name":"Sophia","ethnicity":...,
#    "skin_tone":...,"body_type":...,"age_approx":...}, ...]} — resolved
#    against actual image files in Female Model/R WEBP/{name}.webp.
#    Matching scores ethnicity + skin_tone as primary signal, body_type +
#    age as secondary, then — among equally-good candidates — picks the
#    LEAST-USED model so the same face isn't reused pack after pack.
# 🆕 v2: Model "usage" is NO LONGER stored in metadata/model_usage.json.
#    It is simply recomputed every run by scanning every already-generated
#    output filename on disk and counting the Mxxx token. Zero persistent
#    usage state — always self-consistent with what's actually on disk.
# ✅ Persistent metadata/cloth_index.json (created once, only appended to
#    when a NEW cloth image is used — existing entries are NEVER
#    renumbered or overwritten)
# ✅ BULK PRE-ASSIGNMENT PASS (cloths only) — runs FIRST, before anything
#    else. Scans EVERY cloth image on disk, assigns an ID to anything not
#    already indexed, verifies/keeps existing IDs untouched, saves
#    immediately. Only after this completes does the script move on.
# 🆕 v2: FIXED "already processed but reprocessed anyway" bug.
#    Previously, the "already done?" check rebuilt the output filename
#    using the model/cloth chosen THIS run, so if a prior run had picked a
#    different model or cloth for the same pack, the file "looked missing"
#    even though it already existed on disk. Now every pack's existing
#    output folder is scanned FIRST: if files are already there, their
#    Mxxx/Cxxx tokens are parsed straight out of the filename and REUSED
#    (no re-matching, no wasted usage-count), and any image number already
#    present is skipped individually. If the WHOLE pack is already done,
#    the pack is skipped entirely with zero JSON reads / matching at all.
# ✅ Output = Original only. Naming:
#    {PackID}.{ImgNum}.M{ModelID}.C{ClothID}.{Studio}.Original.png
# ✅ Per-pack manifest.json written alongside the images
# 🆕 v2: Faster "stuck tab" recovery — if Gemini's send button re-enables
#    (meaning it finished responding) but no image / thumb-up / refusal /
#    error is detected after a few quick polls, the tab is refreshed and
#    the job requeued instead of waiting the full timeout. Same explicit
#    refresh happens on a hard MAX_STATE_TIMEOUT. This keeps all 6 tabs
#    cycling continuously instead of one tab blocking the pipeline.
# ❌ REMOVED: watermark-removal section (geminiwatermarkremover.io) — Original only
# ============================================================================

import os, re, json, time, shutil, base64, subprocess, pickle, socket, math
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from PIL import Image
import numpy as np
from IPython.display import display as ipy_display, HTML, Image as IPImage

# ============================================================================
# SECTION 1 — INSTALL DEPENDENCIES
# ============================================================================
print("=" * 70)
print("🔧 INSTALLING DEPENDENCIES (Xvfb + Chrome + noVNC)")
print("=" * 70)
import subprocess as _sp

os.environ["DEBIAN_FRONTEND"] = "noninteractive"

def run_cmd(cmd, shell=True, timeout=120):
    try:
        return _sp.run(cmd, shell=shell, capture_output=True, text=True,
                       check=False, timeout=timeout)
    except _sp.TimeoutExpired:
        print(f"⚠️ Command timed out after {timeout}s")
        return None
    except:
        return None

def _bin_exists(name):
    r = run_cmd(f"which {name}", timeout=5)
    return r is not None and r.returncode == 0 and r.stdout.strip() != ""

print("📦 Updating package lists...")
run_cmd("apt-get update -y", timeout=60)

print("📦 Installing system packages...")
run_cmd("apt-get install -y wget xvfb x11vnc novnc websockify "
        "unzip zip xclip xsel curl dbus-x11 python3-numpy", timeout=120)

for binary in ["Xvfb", "x11vnc", "websockify"]:
    if not _bin_exists(binary):
        if binary == "x11vnc":
            run_cmd("apt-get install -y x11vnc", timeout=60)
        elif binary == "websockify":
            run_cmd("apt-get install -y websockify python3-websockify", timeout=60)
            if not _bin_exists("websockify"):
                run_cmd("pip install -q websockify", timeout=60)
        elif binary == "Xvfb":
            run_cmd("apt-get install -y xvfb", timeout=60)

novnc_web_dir = None
NOVNC_SEARCH_PATHS = ["/usr/share/novnc", "/usr/share/noVNC", "/opt/novnc",
                      "/opt/noVNC", "/usr/local/share/novnc"]
for p in NOVNC_SEARCH_PATHS:
    if os.path.isfile(os.path.join(p, "vnc.html")) or \
       os.path.isfile(os.path.join(p, "vnc_lite.html")):
        novnc_web_dir = p
        break

if novnc_web_dir:
    vnc_html = os.path.join(novnc_web_dir, "vnc.html")
    vnc_lite = os.path.join(novnc_web_dir, "vnc_lite.html")
    if not os.path.isfile(vnc_html) and os.path.isfile(vnc_lite):
        shutil.copy(vnc_lite, vnc_html)

chrome_bin = None
for path in ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome"]:
    if os.path.exists(path):
        chrome_bin = path
        break

if not chrome_bin:
    run_cmd("wget -q -O /tmp/chrome.deb "
            "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb",
            timeout=60)
    run_cmd("dpkg -i /tmp/chrome.deb", timeout=60)
    run_cmd("apt-get install -f -y", timeout=60)
    run_cmd("rm -f /tmp/chrome.deb", timeout=5)
    for path in ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome"]:
        if os.path.exists(path):
            chrome_bin = path
            break

if not chrome_bin:
    result = run_cmd("which google-chrome", timeout=5)
    chrome_bin = result.stdout.strip() if result and result.stdout.strip() else "google-chrome"

import platform
cf_path = "/usr/local/bin/cloudflared"
cf_ok = False
if os.path.exists(cf_path):
    r = run_cmd(f"{cf_path} --version", timeout=5)
    cf_ok = r is not None and r.returncode == 0

if not cf_ok:
    arch = "arm64" if platform.machine().lower() in ["aarch64", "arm64"] else "amd64"
    run_cmd(f"curl -sL -o {cf_path} "
            f"https://github.com/cloudflare/cloudflared/releases/latest/download/"
            f"cloudflared-linux-{arch}", timeout=60)
    if os.path.exists(cf_path) and os.path.getsize(cf_path) > 100_000:
        run_cmd(f"chmod +x {cf_path}", timeout=5)
        r = run_cmd(f"{cf_path} --version", timeout=5)
        cf_ok = r is not None and r.returncode == 0
        if not cf_ok:
            cf_path = None

run_cmd("pip install -q selenium webdriver-manager pyvirtualdisplay pillow requests numpy",
        timeout=120)
print("✅ Python packages ready")

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from google.colab import drive
from pyvirtualdisplay import Display

print("📁 Mounting Drive...")
try:
    drive.mount("/content/drive")
except:
    print("⚠️ Drive already mounted or failed")

print("\n✅ ALL DEPENDENCIES READY\n")

# ============================================================================
# SECTION 2 — VIRTUAL DISPLAY + noVNC
# ============================================================================
SCREEN_W, SCREEN_H = 1920, 1080
VNC_PORT, NOVNC_PORT = 5900, 6080
_display_obj = _x11vnc_proc = _novnc_proc = _cf_proc = None

def _port_open(port, host="127.0.0.1", timeout=1.0):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except:
        return False

def _wait_for_port(port, label="service", max_wait=15):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        if _port_open(port):
            print(f"✅ {label} on :{port}")
            return True
        time.sleep(0.5)
    print(f"⚠️ {label} not ready on :{port}")
    return False

def _kill_port(port):
    try:
        run_cmd(f"fuser -k {port}/tcp", timeout=5)
    except:
        pass
    time.sleep(0.3)

def start_display():
    global _display_obj
    run_cmd("pkill -f Xvfb", timeout=5)
    time.sleep(0.3)
    try:
        _display_obj = Display(visible=0, size=(SCREEN_W, SCREEN_H))
        _display_obj.start()
        os.environ["DISPLAY"] = f":{_display_obj.display}"
        print(f"✅ Display :{_display_obj.display}")
    except Exception as e:
        print(f"⚠️ pyvirtualdisplay failed: {e}")
        if _bin_exists("Xvfb"):
            subprocess.Popen(["Xvfb", ":99", "-screen", "0",
                              f"{SCREEN_W}x{SCREEN_H}x24", "-ac"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.environ["DISPLAY"] = ":99"
            time.sleep(1.0)
            print("✅ Display :99")

def start_vnc():
    global _x11vnc_proc, _novnc_proc
    disp = os.environ.get("DISPLAY", ":99")
    run_cmd("pkill -f x11vnc", timeout=5)
    run_cmd("pkill -f websockify", timeout=5)
    _kill_port(VNC_PORT)
    _kill_port(NOVNC_PORT)
    time.sleep(0.5)

    if _bin_exists("x11vnc"):
        _x11vnc_proc = subprocess.Popen(
            ["x11vnc", "-display", disp, "-forever", "-nopw",
             "-quiet", "-rfbport", str(VNC_PORT), "-shared"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        _wait_for_port(VNC_PORT, "x11vnc", max_wait=10)

        if not _port_open(VNC_PORT) or not _bin_exists("websockify"):
            return

        cmd = (["websockify", "--web", novnc_web_dir, str(NOVNC_PORT),
                f"localhost:{VNC_PORT}"] if novnc_web_dir
               else ["websockify", str(NOVNC_PORT), f"localhost:{VNC_PORT}"])
        _novnc_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        _wait_for_port(NOVNC_PORT, "noVNC/websockify", max_wait=10)

def start_tunnel():
    global _cf_proc
    local_url = f"http://localhost:{NOVNC_PORT}"
    if not _port_open(NOVNC_PORT):
        time.sleep(5)
        if not _port_open(NOVNC_PORT):
            ipy_display(HTML("<div style='background:#ea4335;color:white;padding:12px;"
                             "border-radius:8px;'>❌ noVNC not listening.</div>"))
            return local_url

    if cf_path and os.path.exists(cf_path):
        try:
            run_cmd("pkill -f cloudflared", timeout=5)
            time.sleep(0.5)
            _cf_proc = subprocess.Popen(
                [cf_path, "tunnel", "--url", local_url],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            deadline = time.time() + 30
            while time.time() < deadline:
                line = _cf_proc.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
                if m:
                    tb = m.group(0)
                    vnc_url_1 = f"{tb}/vnc.html?autoconnect=true&resize=scale"
                    vnc_url_2 = f"{tb}"
                    ipy_display(HTML(f"""
                    <div style='background:linear-gradient(135deg,#34a853,#0d652d);color:white;
                    padding:16px;border-radius:10px;font-size:15px;font-weight:bold;margin:10px 0;'>
                    🌐 noVNC Ready: <a href='{vnc_url_1}' target='_blank' style='color:#a8e6cf;'>{vnc_url_1}</a><br><br>
                    🖥️ VNC URL: <a href='{vnc_url_2}' target='_blank' style='color:#a8e6cf;'>{vnc_url_2}</a>
                    </div>"""))
                    return tb
        except Exception as e:
            print(f"⚠️ Tunnel error: {e}")

    fallback = f"http://localhost:{NOVNC_PORT}/vnc.html"
    ipy_display(HTML(f"<div style='background:#fbbc04;color:#333;padding:12px;"
                     f"border-radius:8px;'>⚠️ Local only: <b>{fallback}</b></div>"))
    return fallback

def setup_novnc_ui():
    start_display()
    start_vnc()
    return start_tunnel()

# ============================================================================
# SECTION 3 — CONFIGURATION + PATHS (NEW PACK-WISE LAYOUT)
# ============================================================================
BASE             = "/content/drive/MyDrive/Gemini/Ecom Photoshoot"
INPUT_BASE       = f"{BASE}/ALL INPUT PACK"
IMG_SRC_BASE     = f"{BASE}/ALL IMAGE PACK"
WOMEN_DIR        = os.path.join(INPUT_BASE, "Women")
WOMEN_IMG_DIR    = os.path.join(WOMEN_DIR, "Women Image")
WOMEN_JSON_DIR   = os.path.join(WOMEN_DIR, "Women Json")

# Input WR renders to be re-generated, laid out pack-wise:
#   ALL PACK 1 ITERATION/Women/{ClothCategory}/WR/{PackID}/{PackID}.{n}.{studio}.WR.{desc}.ext
#   e.g. 131.6.f360.WR.png   (desc is optional)
ITER1_BASE       = f"{BASE}/ALL PACK 1 ITERATION/Women"

# JSON per pack lives at:
#   ALL INPUT PACK/Women/Women Json/{studio}/{pack_id}/FULL/{pack_id}.{studio}.{desc}.json
JSON_SRC         = WOMEN_JSON_DIR   # kept for the validation printout below

def _find_dir(candidates):
    for c in candidates:
        if os.path.isdir(c):
            return c
        parent = os.path.dirname(c)
        target = os.path.basename(c).lower()
        if os.path.isdir(parent):
            for entry in os.listdir(parent):
                if entry.lower() == target and os.path.isdir(os.path.join(parent, entry)):
                    return os.path.join(parent, entry)
    return candidates[0]

# Model images live under "Female Model/R CHARACTER WEBP" and are named after the
# model's NAME from the catalog (e.g. "Valentina.webp").
MODEL_IMG_DIR  = _find_dir([f"{BASE}/Female Model/R CHARACTER WEBP"])
CLOTH_RGB_BASE = _find_dir([
    f"{BASE}/ALL CLOTH/WOMEN/women cloth mobile rgb",
    f"{BASE}/ALL CLOTH/WOMEN/Women cloth mobile rgb",
    f"{BASE}/ALL CLOTH/Women/women cloth mobile rgb",
    f"{BASE}/WOMEN/women cloth mobile rgb",
    f"{BASE}/WOMEN/Women cloth mobile rgb",
])
CLOTH_WR_BASE  = _find_dir([
    f"{BASE}/ALL CLOTH/WOMEN/women cloth mobile",
    f"{BASE}/ALL CLOTH/WOMEN/Women cloth mobile",
    f"{BASE}/ALL CLOTH/Women/women cloth mobile",
    f"{BASE}/WOMEN/women cloth mobile",
    f"{BASE}/WOMEN/Women cloth mobile",
])

# Output: Original ONLY, pack-wise
OUTPUT_BASE      = f"{BASE}/ALL PACK 2 ITERATION/Women"

# Persistent metadata
METADATA_DIR     = f"{BASE}/metadata"
MODEL_INDEX_PATH = f"{METADATA_DIR}/model_index.json"   # fixed catalog (see load_model_catalog)
CLOTH_INDEX_PATH = f"{METADATA_DIR}/cloth_index.json"   # unchanged: append-only auto-assigned IDs
# 🆕 v2: NO model_usage.json anymore — usage is derived from output filenames
# on disk every run (see compute_model_usage_from_filenames in Section 7).

_cloth_rgb_map = {}
_cloth_wr_map  = {}

def _build_cloth_cache():
    global _cloth_rgb_map, _cloth_wr_map
    if os.path.isdir(CLOTH_RGB_BASE):
        for d in os.listdir(CLOTH_RGB_BASE):
            if os.path.isdir(os.path.join(CLOTH_RGB_BASE, d)):
                _cloth_rgb_map[d.lower()] = d
    if os.path.isdir(CLOTH_WR_BASE):
        for d in os.listdir(CLOTH_WR_BASE):
            if os.path.isdir(os.path.join(CLOTH_WR_BASE, d)):
                _cloth_wr_map[d.lower()] = d

_build_cloth_cache()

print("\n" + "=" * 70)
print("🔍 PATH VALIDATION")
print("=" * 70)
for label, path in [("ITER1_BASE", ITER1_BASE), ("WOMEN_JSON_DIR", WOMEN_JSON_DIR),
                    ("MODEL_IMG_DIR", MODEL_IMG_DIR),
                    ("CLOTH_RGB_BASE", CLOTH_RGB_BASE),
                    ("CLOTH_WR_BASE", CLOTH_WR_BASE)]:
    exists = os.path.isdir(path)
    count  = len(os.listdir(path)) if exists else 0
    mark   = "✅" if exists else "❌"
    print(f"  {mark} {label}: {path}  ({count} items)")

if _cloth_rgb_map:
    print(f"  📦 Cloth RGB categories cached: {len(_cloth_rgb_map)}")
if _cloth_wr_map:
    print(f"  📦 Cloth WR categories cached: {len(_cloth_wr_map)}")
print("=" * 70 + "\n")

COOKIES_FILE     = "/content/drive/MyDrive/google_cookies.pkl"
GEMINI_APP_URL   = "https://gemini.google.com/app"
CHROME_DL_BASE   = "/content/downloads"
LOCAL_COPY_BASE  = "/content/image_copies"
LOGIN_SS_DIR     = "/content/login_screenshots"
ERR_SS_DIR       = "/content/error_screenshots"

for d in [CHROME_DL_BASE, LOCAL_COPY_BASE, LOGIN_SS_DIR, ERR_SS_DIR, METADATA_DIR]:
    os.makedirs(d, exist_ok=True)

TIMEOUT           = 15
GEN_TIMEOUT       = 240
DOWNLOAD_TIMEOUT  = 60
MAX_STATE_TIMEOUT = 420          # hard timeout per job (unchanged)
SOFT_STUCK_POLLS  = 5            # 🆕 v2: consecutive "finished but nothing detected" polls before we bail early
IMG_EXTS          = (".jpg", ".jpeg", ".png", ".webp")
TOTAL_TABS        = 6

GEN_SUCCESS   = "SUCCESS"
GEN_REFUSED   = "REFUSED"
GEN_TIMEOUT_S = "TIMEOUT"
GEN_LIMIT     = "LIMIT"
GEN_ERROR     = "ERROR"
S_IDLE        = "IDLE"
S_GEN_WAITING = "GW"

CAPTCHA_SIGNALS = [
    "select all squares", "select all images", "i'm not a robot",
    "verify you are human", "are you a robot", "recaptcha",
    "click verify once", "type the characters"
]
SORRY_URL_SIGNALS   = ["google.com/sorry", "recaptcha", "accounts.google.com/v3/signin"]
GEMINI_ERROR_SIG    = [
    "i encountered an error doing what you asked",
    "encountered an error doing what you asked",
    "something went wrong. try again",
    "an error occurred. please try again",
    "i'm not able to help with that right now",
    "unable to complete your request",
]
PRO_LIMIT_PHRASES   = [
    "you've reached your image-generation limit",
    "reached your image-generation limit",
    "image-generation limit",
    "can't generate more images for you today",
    "come back tomorrow",
    "you've reached your limit",
    "reached your daily limit",
    "rate limit", "too many requests",
]
TEXT_REFUSAL = [
    "can't create images of", "cannot create images of",
    "i'm not able to create that image",
    "i'm unable to create that image",
    "i can't create this image",
]

def tab_dl_dir(tid):
    d = os.path.join(CHROME_DL_BASE, f"tab_{tid}")
    os.makedirs(d, exist_ok=True)
    return d

# ============================================================================
# SECTION 3.5 — PERSISTENT CLOTH INDEX (created once, append-only)
# Model index is a FIXED CATALOG loaded separately in Section 7 — it is
# never auto-assigned or renumbered here.
# ============================================================================
def load_json_file(path, default):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

_cloth_index = load_json_file(CLOTH_INDEX_PATH, {})
_cloth_index_dirty = False

if not os.path.isfile(CLOTH_INDEX_PATH):
    save_json_file(CLOTH_INDEX_PATH, _cloth_index)
    print(f"📝 Created {CLOTH_INDEX_PATH}")

def _next_id(index_dict, letter):
    nums = []
    for k in index_dict:
        if k.startswith(letter) and k[1:].isdigit():
            nums.append(int(k[1:]))
    return (max(nums) + 1) if nums else 1

def get_or_assign_cloth_id(cloth_path, cloth_type):
    """Returns existing Cxxx id if this exact cloth image is already indexed,
    otherwise assigns the next free id. Existing ids are NEVER changed."""
    global _cloth_index, _cloth_index_dirty
    fn = os.path.basename(cloth_path)
    for cid, info in _cloth_index.items():
        if info.get("filename") == fn:
            return cid
    cid = f"C{_next_id(_cloth_index, 'C'):03d}"
    _cloth_index[cid] = {"filename": fn, "cloth_type": cloth_type}
    _cloth_index_dirty = True
    return cid

def flush_indexes():
    global _cloth_index_dirty
    if _cloth_index_dirty:
        save_json_file(CLOTH_INDEX_PATH, _cloth_index)
        _cloth_index_dirty = False

# ============================================================================
# SECTION 3.6 — BULK PRE-ASSIGNMENT PASS (cloths only, runs once, FIRST)
# ----------------------------------------------------------------------------
# Before ANY pack scanning, browser setup, or generation starts, we:
#   1) List every cloth WR image file on disk (every category under CLOTH_WR_BASE).
#   2) If its filename is ALREADY in the index -> verified, skip (ID untouched).
#   3) If it's NOT in the index yet -> assign the next free Cxxx id.
#   4) Save immediately, then print a verification summary.
# Models are NOT pre-assigned here — they come from the fixed catalog in
# model_index.json (see load_model_catalog in Section 7).
# ============================================================================
def pre_assign_all_cloths():
    """Scan every cloth category folder under CLOTH_WR_BASE fully and make sure
    every cloth WR image has a permanent ID."""
    global _cloth_index
    if not os.path.isdir(CLOTH_WR_BASE):
        print(f"   ⚠️ Cloth WR base not found, cannot pre-assign: {CLOTH_WR_BASE}")
        return

    already_filenames = {info.get("filename") for info in _cloth_index.values()}

    total_found   = 0
    already_count = 0
    new_count     = 0

    for category_dir in sorted(os.listdir(CLOTH_WR_BASE)):
        cat_path = os.path.join(CLOTH_WR_BASE, category_dir)
        if not os.path.isdir(cat_path):
            continue
        wr_dir = os.path.join(cat_path, "WR")
        scan_dir = wr_dir if os.path.isdir(wr_dir) else cat_path

        try:
            files = sorted(
                fn for fn in os.listdir(scan_dir)
                if os.path.splitext(fn)[1].lower() in IMG_EXTS
            )
        except:
            continue

        for fn in files:
            total_found += 1
            if fn in already_filenames:
                already_count += 1
                continue
            full_path = os.path.join(scan_dir, fn)
            get_or_assign_cloth_id(full_path, category_dir)  # assigns next free Cxxx
            new_count += 1

    flush_indexes()
    print(f"   👗 Cloths on disk: {total_found}  |  ✅ already assigned: {already_count}  "
          f"|  🆕 newly assigned: {new_count}  |  📇 total in index: {len(_cloth_index)}")

def run_bulk_pre_assignment():
    print("\n" + "=" * 70)
    print("🔧 BULK PRE-ASSIGNMENT — Cloth IDs (runs first, every time)")
    print("=" * 70)
    pre_assign_all_cloths()
    print("=" * 70)
    print(f"✅ Verified: {CLOTH_INDEX_PATH}")
    print("=" * 70 + "\n")



# ============================================================================
# SECTION 4 — ITERATION 2 PROMPT TEMPLATE
# ============================================================================

ITER2_PROMPT_TEMPLATE = """
CORE OBJECTIVE
Create one physically plausible commercial fashion photograph by replacing the mannequin with the real person from FACE_REF while faithfully preserving the garment identity from CLOTHING_REF and the complete body pose from MANNEQUIN_REF.
This is a constrained reconstruction task, not creative image synthesis.

GOLDEN RULE: BINARY VISIBILITY MASK
The mannequin is a strict binary visibility mask. Replace ONLY pixels occupied by the mannequin. Never expand the mask. Never generate outside the mannequin's crop boundaries. If a body part is cropped in the mannequin, it remains cropped.

REFERENCE AUTHORITY (STRICT ISOLATION)
• MANNEQUIN_REF: Absolute authority for pose, skeleton, camera, crop, framing, lighting, shadows, environment, accessory paths, and footwear contact. Contains ZERO clothing/face data.
• CLOTHING_REF: Absolute authority for garment identity, construction, structural topology, material properties and commercial product specification. Contains ZERO pose, body or camera data.
• FACE_REF: Absolute authority for facial identity, skin, and hair geometry. Contains ZERO body pose data.

REFERENCE COMPLETENESS
Use only information explicitly visible in each reference.
When information is not visible, reconstruct conservatively from visible structural evidence without redesigning or inventing new product features.

HARD CONSTRAINTS & SOFT PREFERENCES
HARD CONSTRAINTS (Must Never Change):
• Visibility mask and crop boundaries
• Pose, skeleton, and camera geometry
• Face identity and hairstyle identity
• Garment identity and material identity
• Accessory geometry and paths

SOFT PREFERENCES (Optimize When Possible):
• Photographic realism and lighting consistency
• Fabric wrinkles, folds, and drape
• Facial expression and eye gaze
• Hair strand physics and movement
• Soft tissue and skin deformation

CONFLICT HIERARCHY
1. Visibility Mask & Canvas (Absolute)
2. Pose, Skeleton & Camera (Immutable structural base)
3. Garment & Face Identity (Identity Preservation)
4. Photorealistic Rendering (Execution)

FAILURE POLICY
If all constraints cannot be satisfied simultaneously, preserve every hard constraint.
Never invent new content to resolve ambiguity.
Prefer an incomplete but faithful reconstruction over an incorrect reconstruction.
Do not redesign, approximate, beautify, or hallucinate missing information.
When uncertainty exists, preserve product identity and structural consistency rather than inventing missing garment details.

POSE OVERRIDES GARMENT
If preserving garment appearance requires changing pose, skeleton, camera, or framing, DO NOT modify the body.
Always adapt the garment to the locked pose.
Never adapt the pose to the garment.

POSE, SKELETON & CAMERA LOCK
• Skeleton: Immutable. Faithfully preserve exact joint angles, limb states, weight distribution, and asymmetry. Do not relax, beautify, or auto-correct.
• Hands & Contact: Faithfully preserve exact gesture, finger curl, and physical contact points. No new or removed contacts.
• Camera: Camera geometry is immutable. Maintain identical viewpoint, perspective, focal length, framing, crop, and aspect ratio.

VISIBILITY & OCCLUSION
• Mask Rule: Visible anatomy comes ONLY from MANNEQUIN_REF. Never reveal hidden surfaces or complete cropped regions.
• Occlusion: Exact foreground/background relationships maintained.

GARMENT IDENTITY
Treat CLOTHING_REF as the canonical product specification rather than a worn garment
Infer garment construction only from visible evidence contained in CLOTHING_REF.
Reconstruct the same garment as if professionally worn on the reconstructed body without altering its identity.
Faithfully preserve the original garment identity, including:
• garment category, construction, neckline, sleeve length
• embroidery geometry, placement, border geometry, print layout
• fabric type, micro-texture, weave pattern, embroidery density, printed motifs, trims, borders, surface finish and material appearance.
Do not redesign, reinterpret, or approximate the product.
Preserve the commercial product exactly; only physically plausible deformation caused by dressing and the locked pose is permitted.

IDENTITY CONTINUITY
All visible garment regions must remain mutually consistent as parts of the same commercial product.
Construction, proportions, materials, decorative elements and finishing details must remain coherent across the entire garment.

GARMENT DRESSING
Reconstruct the complete human anatomy from MANNEQUIN_REF before applying the garment.
Dress the reconstructed body with the garment defined by CLOTHING_REF.
Determine the correct wearing configuration from the garment construction, structural design and fastening system.
Body anatomy defines garment deformation.
Generate physically realistic wrapping, layering, fastening, tension, compression, folds and drape created only by body anatomy, gravity, material properties and the locked pose.
Do not copy fold patterns from CLOTHING_REF.
Generate new folds from physical interaction while preserving product identity.

GARMENT TOPOLOGY
Preserve the relative spatial arrangement and proportions of all structural garment components.
Necklines, waistlines, shoulder seams, sleeve attachments, borders, hems, pleats, panels, lapels, collars, cuffs and structural elements must remain in their correct anatomical positions.
Do not shift, rotate, resize or proportionally alter structural garment components.

BODY–GARMENT COUPLING
The garment must appear physically worn rather than overlaid.
Maintain continuous body contact where naturally expected.
Fabric deformation must arise only from body anatomy, contact, gravity, material properties and the locked pose.
Avoid floating fabric or detached garment regions.
Material appearance should respond naturally to the locked scene lighting while preserving original fabric characteristics.

STRUCTURAL STABILITY
Preserve the structural integrity of the garment.
Seams, attachment points, closures, waistlines, necklines, cuffs, collars and other structural components must remain mechanically consistent under deformation.
Only physically plausible deformation is permitted.

FACE & HAIR ADAPTATION
• Face: Identity is immutable. Do not copy the reference expression. Generate a natural expression from the combined influence of body language, head orientation, garment style, environment, lighting, camera distance and commercial fashion intent. Expressions should appear naturally emerging from the interaction between the model, photographer, garment and environment, rather than looking artificially posed or emotionally empty. Preserve natural facial asymmetry, subtle facial muscle activation, dimples, smile lines, crow's feet, nasolabial folds and other genuine micro-expressions when naturally produced by the scene or expression.
• Hair: Identity (haircut, length, density, texture and color) is immutable. Hair strands are adaptive. Preserve hairstyle identity while naturally responding to gravity, body movement, shoulder contact and airflow. Hair must emerge naturally from the scalp with realistic volume and strand continuity.

EYE BEHAVIOR
Eyes should exhibit realistic human behavior with natural focus, subtle eyelid asymmetry, appropriate catchlights, gaze stability, gentle squinting under bright sunlight and relaxed ocular muscles. Avoid frozen staring or perfectly symmetrical eyes.

SKIN REALISM
Preserve natural skin characteristics including fine pores, subtle wrinkles, gentle skin compression, lip texture, realistic translucency, slight color variation and natural specular highlights appropriate to the lighting.

ACCESSORY & ENVIRONMENT LOCK
• Accessories: Rigid geometry. Faithfully preserve exact dimensions, strap paths, and occlusion. Do not reroute straps or float bags.
• Environment: Static. Lighting, shadows, and background remain spatially identical to MANNEQUIN_REF.

CONSISTENCY PRINCIPLE
All reconstructed elements must remain mutually consistent.
Face, body, clothing, lighting, shadows, perspective, and material response must appear to belong to a single photograph captured at one moment in time.
All reconstructed elements must share one physically coherent three-dimensional world space.

HUMAN REALISM
Produce an authentic commercial fashion photograph with consistent lighting, perspective, material response and photographic realism.
Preserve natural human asymmetry, realistic skin and authentic fabric imperfections.
Avoid synthetic, over-processed or digitally illustrated appearance.


NEGATIVE CONSTRAINTS
Do not violate:
• visibility
• pose
• camera
• garment identity
• face identity
• material identity
• accessory geometry

Avoid:
• AI artifacts
• plastic skin
• floating objects
• unrealistic fabric physics
• incorrect garment construction
• geometry distortion
• artificial symmetry
"""




# ============================================================================
# SECTION 5 — FILENAME / PATH UTILITIES + ACCESSORY EXTRACTION
# ============================================================================
def extract_accessories_from_json(json_data):
    DEFAULT_ACCESSORIES = '["earrings", "bangles", "footwear"]'
    try:
        other = json_data.get("other") or {}
        acc_dict = other.get("accessories") or {}
        if not acc_dict:
            acc_dict = json_data.get("accessories") or {}
        if not isinstance(acc_dict, dict) or not acc_dict:
            return DEFAULT_ACCESSORIES
        acc_keys = [key for key, val in acc_dict.items() if val]
        if not acc_keys:
            return DEFAULT_ACCESSORIES
        formatted = "[" + ", ".join(f'"{k}"' for k in acc_keys) + "]"
        return formatted
    except Exception:
        return DEFAULT_ACCESSORIES

def safe_name(s):
    return re.sub(r'[<>:"/\\|?*]', "", str(s)).strip()

def parse_iter1_wr_filename(filename, known_studios):
    """{PackID}.{n}.{studio}.WR.{desc}.ext  e.g. 131.6.f360.WR.png  (desc OPTIONAL)
    Returns (n, studio, desc, ext, pack_id_in_name) or None."""
    base, ext = os.path.splitext(filename)
    parts = base.split(".")

    if len(parts) < 4:
        return None

    try:
        pack_id_in_name = int(parts[0])
    except:
        return None

    try:
        n = int(parts[1])
    except:
        return None

    for i in range(len(parts) - 1, 1, -1):
        candidate_studio = '.'.join(parts[2:i + 1])
        if candidate_studio in known_studios:
            if i + 1 < len(parts) and parts[i + 1].lower() == 'wr':
                desc = '.'.join(parts[i + 2:]) if i + 2 < len(parts) else ""
                return n, candidate_studio, desc, ext.lower(), pack_id_in_name

    if len(parts) > 3 and parts[3].lower() == 'wr':
        studio = parts[2]
        desc = '.'.join(parts[4:]) if len(parts) > 4 else ""
        return n, studio, desc, ext.lower(), pack_id_in_name

    return None

# ============================================================================
# SECTION 5.1 — DISCOVER KNOWN STUDIOS (Fix for studio names with dots)
# ============================================================================
def discover_known_studios():
    studios = set()
    if os.path.isdir(WOMEN_JSON_DIR):
        for d in os.listdir(WOMEN_JSON_DIR):
            if os.path.isdir(os.path.join(WOMEN_JSON_DIR, d)):
                studios.add(d)
    if os.path.isdir(WOMEN_IMG_DIR):
        for d in os.listdir(WOMEN_IMG_DIR):
            if os.path.isdir(os.path.join(WOMEN_IMG_DIR, d)):
                studios.add(d)
    if os.path.isdir(IMG_SRC_BASE):
        for d in os.listdir(IMG_SRC_BASE):
            if os.path.isdir(os.path.join(IMG_SRC_BASE, d)):
                studios.add(d)
    return studios


def find_pack_json(studio, pack_id):
    """FULL json lives at: Women Json/{studio}/{pack_id}/FULL/{pack_id}.{studio}.{desc}.json"""
    if not os.path.isdir(WOMEN_JSON_DIR):
        return None
    pack_json_dir = os.path.join(WOMEN_JSON_DIR, studio, str(pack_id), "FULL")
    if not os.path.isdir(pack_json_dir):
        pack_json_dir = os.path.join(WOMEN_JSON_DIR, studio, str(pack_id))
        if not os.path.isdir(pack_json_dir):
            return None
    prefix = f"{pack_id}.{studio}."
    try:
        matches = sorted(fn for fn in os.listdir(pack_json_dir)
                         if fn.startswith(prefix) and fn.endswith(".json"))
        if matches:
            return os.path.join(pack_json_dir, matches[0])
        any_json = sorted(fn for fn in os.listdir(pack_json_dir) if fn.endswith(".json"))
        if any_json:
            return os.path.join(pack_json_dir, any_json[0])
    except:
        pass
    return None

def build_pack_output_dir(cloth_category, pack_id):
    d = os.path.join(OUTPUT_BASE, safe_name(cloth_category), "Original", str(pack_id))
    os.makedirs(d, exist_ok=True)
    return d

def build_output_image_path(cloth_category, pack_id, img_num, model_id, cloth_id, studio):
    d = build_pack_output_dir(cloth_category, pack_id)
    fn = f"{pack_id}.{img_num}.{model_id}.{cloth_id}.{studio}.Original.png"
    return os.path.join(d, fn)

def update_pack_manifest(job):
    pack_dir = build_pack_output_dir(job["cloth_category"], job["pack_id"])
    manifest_path = os.path.join(pack_dir, "manifest.json")
    manifest = load_json_file(manifest_path, {
        "pack_id": job["pack_id"], "cloth_category": job["cloth_category"],
        "studio": job["studio"], "model_id": job["model_id"],
        "cloth_id": job["cloth_id"], "source_json": job["json_path"],
        "images": {},
    })
    de_score = job.get("de_score")
    manifest["images"][str(job["img_num"])] = {
        "desc": job["desc"],
        "output": os.path.basename(job["output_original"]),
        "de_score": None if (de_score is None or de_score == float("inf")) else round(de_score, 2),
        "match_source": job["match_source"],
    }
    save_json_file(manifest_path, manifest)

# ============================================================================
# SECTION 6 — SCAN ALL 1 ITERATION PACKS (WR IMAGES, PACK-WISE)
# ============================================================================
def scan_iter1_packs():
    """Returns { (cloth_category, pack_id): {"studio": str, "images": [(n, desc, path), ...]} }"""
    packs = {}
    if not os.path.isdir(ITER1_BASE):
        print(f"❌ ITER1 base not found: {ITER1_BASE}")
        return packs

    known_studios = discover_known_studios()
    print(f"🔍 Discovered {len(known_studios)} known studios for filename parsing.")

    mismatch_warned = 0

    for cloth_dir in sorted(os.listdir(ITER1_BASE)):
        cloth_path = os.path.join(ITER1_BASE, cloth_dir)
        if not os.path.isdir(cloth_path):
            continue
        wr_root = os.path.join(cloth_path, "WR")
        if not os.path.isdir(wr_root):
            continue
        for pack_id_str in sorted(os.listdir(wr_root)):
            pack_dir = os.path.join(wr_root, pack_id_str)
            if not os.path.isdir(pack_dir):
                continue
            try:
                pack_id = int(pack_id_str)
            except:
                continue
            images = []
            studio = None
            for fn in sorted(os.listdir(pack_dir)):
                if os.path.splitext(fn)[1].lower() not in IMG_EXTS:
                    continue

                parsed = parse_iter1_wr_filename(fn, known_studios)
                if not parsed:
                    continue

                n, st, desc, _, pack_id_in_name = parsed
                if pack_id_in_name != pack_id and mismatch_warned < 5:
                    print(f"   ⚠️ '{fn}': filename PackID ({pack_id_in_name}) != folder PackID ({pack_id}) — folder wins")
                    mismatch_warned += 1
                studio = studio or st
                images.append((n, desc, os.path.join(pack_dir, fn)))

            if images:
                images.sort(key=lambda x: x[0])
                packs[(cloth_dir, pack_id)] = {"studio": studio, "images": images}
    return packs

def parse_pack_range(rs, avail_pack_ids):
    s = rs.strip().lower()
    if s == "all":
        return sorted(avail_pack_ids)
    result = set()
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            h = part.split("-", 1)
            try:
                lo, hi = int(h[0].strip()), int(h[1].strip())
                result.update(p for p in range(lo, hi + 1) if p in avail_pack_ids)
            except:
                pass
        else:
            try:
                v = int(part)
                if v in avail_pack_ids:
                    result.add(v)
            except:
                pass
    return sorted(result)

# ============================================================================
# SECTION 7 — FEMALE MODEL CATALOG + BEST-MATCH-WITH-ROTATION
# ----------------------------------------------------------------------------
# model_index.json is a FIXED CATALOG:
#   { "models": [ {"no":"M001","name":"Sophia","ethnicity":"European White",
#                  "skin_tone":"fair","body_type":"slim","age_approx":"22-30"},
#                 ... ] }
# Each entry's actual image lives at MODEL_IMG_DIR/{name}.{ext}
#
# Matching scores ethnicity + skin_tone as the PRIMARY signal, body_type +
# age as secondary. Among candidates within a small tolerance of the best
# score, the LEAST-USED model is picked so the same face doesn't repeat
# pack after pack.
#
# 🆕 v2: usage counts come from scanning existing OUTPUT FILENAMES on disk
# (compute_model_usage_from_filenames), NOT from a persistent JSON file.
# ============================================================================
ETHNICITY_ALIASES = {
    "european white": "european", "european": "european", "caucasian": "european",
    "south asian": "south asian", "southeast asian": "southeast asian",
    "east asian": "east asian", "asian": "east asian",
    "african": "african", "african american": "african", "black": "african",
    "middle eastern": "middle eastern", "arab": "middle eastern",
    "latin": "latin", "latin american": "latin", "hispanic": "latin", "mixed": "mixed",
}
SKIN_SIMILARITY = {
    "fair":       ["fair", "light", "pale", "porcelain", "cream"],
    "warm beige": ["warm beige", "beige", "warm", "wheatish"],
    "wheatish":   ["wheatish", "warm beige", "wheat", "beige"],
    "medium":     ["medium", "medium brown", "tan"],
    "warm tan":   ["warm tan", "tan", "warm beige"],
    "brown":      ["brown", "medium brown", "warm brown"],
    "deep brown": ["deep brown", "deep", "dark brown", "dark"],
}
BUILD_ALIASES = {
    "slim": ["slim", "slender", "lean"], "athletic": ["athletic", "fit", "toned"],
    "average": ["average", "medium", "regular"],
    "curvy": ["curvy", "plus"], "plus": ["plus", "curvy"],
}

def _parse_age_range(age_str):
    m = re.search(r'(\d+)[–\-](\d+)', age_str or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 99)

def load_model_catalog():
    """Loads the fixed model catalog and resolves each entry to its actual
    image file in MODEL_IMG_DIR (matched by name, case-insensitive)."""
    raw = load_json_file(MODEL_INDEX_PATH, {"models": []})
    entries = raw.get("models", []) if isinstance(raw, dict) else []

    dir_listing = {}
    if os.path.isdir(MODEL_IMG_DIR):
        for fn in os.listdir(MODEL_IMG_DIR):
            base, ext = os.path.splitext(fn)
            if ext.lower() in IMG_EXTS:
                dir_listing[base.lower()] = fn

    pool = []
    missing = []
    for m in entries:
        no   = (m.get("no") or "").strip()
        name = (m.get("name") or "").strip()
        if not no or not name:
            continue

        img_path = None
        exact_fn = dir_listing.get(name.lower())
        if exact_fn:
            img_path = os.path.join(MODEL_IMG_DIR, exact_fn)

        if not img_path:
            missing.append(name)
            continue

        age_lo, age_hi = _parse_age_range(m.get("age_approx", ""))
        pool.append({
            "no": no,
            "name": name,
            "ethnicity": (m.get("ethnicity") or "").lower().strip(),
            "skin_tone": (m.get("skin_tone") or "").lower().strip(),
            "body_type": (m.get("body_type") or "").lower().strip(),
            "age_lo": age_lo, "age_hi": age_hi,
            "path": img_path,
        })

    print(f"✅ Loaded {len(pool)} models from catalog: {MODEL_INDEX_PATH}")
    if missing:
        shown = ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else "")
        print(f"   ⚠️ {len(missing)} catalog model(s) have no matching image "
              f"in {MODEL_IMG_DIR}: {shown}")
    return pool

def compute_model_usage_from_filenames():
    """🆕 v2 — Model usage is derived fresh every run by scanning every
    already-generated output filename under OUTPUT_BASE
    ({pack}.{n}.{Mxxx}.{Cxxx}.{studio}.Original.ext) and counting how many
    times each Mxxx model id appears. No metadata/model_usage.json needed —
    this is always in sync with what's actually on disk."""
    usage = defaultdict(int)
    if os.path.isdir(OUTPUT_BASE):
        for root, _, files in os.walk(OUTPUT_BASE):
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in IMG_EXTS:
                    continue
                m = re.search(r'\.(M\d+)\.', fn)
                if m:
                    usage[m.group(1)] += 1
    return usage

_model_usage = compute_model_usage_from_filenames()

def _mark_model_used(no):
    """In-memory only bump so rotation stays fair WITHIN this run too
    (no file write — the count is recomputed from disk again next run)."""
    _model_usage[no] = _model_usage.get(no, 0) + 1

MATCH_TOLERANCE = 6   # candidates within this many points of the best score count as "equally good"

def match_model_best(json_model, model_pool):
    """Scores every catalog model against the pack's required attributes.
    ethnicity + skin_tone are the PRIMARY signal; body_type + age are
    secondary tie-breakers. Among all candidates within MATCH_TOLERANCE
    points of the top score, picks the model used LEAST so far (per
    compute_model_usage_from_filenames) — so the same face isn't reused
    pack after pack when several models fit."""
    if not model_pool:
        return None

    req_eth_raw = (json_model.get("ethnicity") or "").lower().strip()
    req_eth     = ETHNICITY_ALIASES.get(req_eth_raw, req_eth_raw)
    req_skin    = (json_model.get("skin_tone") or "").lower().strip()
    req_build_raw = (json_model.get("body_type") or "").lower().strip()
    req_build   = BUILD_ALIASES.get(req_build_raw, [req_build_raw])[0]
    age_lo, age_hi = _parse_age_range(json_model.get("age_approx", ""))

    scored = []
    for m in model_pool:
        score = 0
        m_eth = ETHNICITY_ALIASES.get(m["ethnicity"], m["ethnicity"])

        # PRIMARY: ethnicity
        if req_eth and m_eth == req_eth:
            score += 50
        elif req_eth and (req_eth in m_eth or m_eth in req_eth):
            score += 25

        # PRIMARY: skin tone
        skin_syns = next((s for k, s in SKIN_SIMILARITY.items()
                          if req_skin in k or k in req_skin), [req_skin])
        for rank, syn in enumerate(skin_syns):
            if syn in m["skin_tone"] or m["skin_tone"] in syn:
                score += max(30 - rank * 5, 4)
                break

        # SECONDARY: body type
        build_syns = BUILD_ALIASES.get(req_build, [req_build])
        for rank, syn in enumerate(build_syns):
            if syn in m["body_type"] or m["body_type"] in syn:
                score += max(8 - rank * 2, 1)
                break

        # SECONDARY: age overlap
        score += max(0, min(age_hi, m["age_hi"]) - max(age_lo, m["age_lo"]))

        scored.append((score, m))

    if not scored:
        return None

    best_score = max(s for s, _ in scored)
    top_candidates = [m for s, m in scored if s >= best_score - MATCH_TOLERANCE]

    # Anti-repeat rotation: among equally-good candidates, prefer whichever
    # has been used least so far. Ties broken by model "no" for determinism.
    top_candidates.sort(key=lambda m: (_model_usage.get(m["no"], 0), m["no"]))
    return top_candidates[0]

# ============================================================================
# SECTION 8 — COLOR MATH (RGB → LAB, Delta-E CIE76)
# ============================================================================
def _srgb_lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def rgb_to_lab(rgb):
    r, g, b = [_srgb_lin(x) for x in rgb]
    X = r*0.4124564 + g*0.3575761 + b*0.1804375
    Y = r*0.2126729 + g*0.7151522 + b*0.0721750
    Z = r*0.0193339 + g*0.1191920 + b*0.9503041
    f = lambda t: t**(1/3) if t > 0.008856 else 7.787*t + 16/116
    fx, fy, fz = f(X/0.95047), f(Y/1.0), f(Z/1.08883)
    return 116*fy - 16, 500*(fx - fy), 200*(fy - fz)

def delta_e(rgb1, rgb2):
    L1, a1, b1 = rgb_to_lab(rgb1)
    L2, a2, b2 = rgb_to_lab(rgb2)
    return math.sqrt((L1-L2)**2 + (a1-a2)**2 + (b1-b2)**2)

def extract_rgb(s):
    m = re.search(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', s or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

# ============================================================================
# SECTION 9 — CLOTH RGB MATCHING — TWO-TIER DELTA-E
# ============================================================================
DE_GOOD_THRESHOLD = 10

def _resolve_cloth_dir(cloth_category, base_dir, cache_map):
    key = cloth_category.lower()
    if key in cache_map:
        return os.path.join(base_dir, cache_map[key])
    exact = os.path.join(base_dir, cloth_category)
    if os.path.isdir(exact):
        return exact
    if os.path.isdir(base_dir):
        for entry in os.listdir(base_dir):
            if entry.lower() == key and os.path.isdir(os.path.join(base_dir, entry)):
                return os.path.join(base_dir, entry)
    return None

def scan_cloth_rgb_jsons(cloth_category):
    cloth_dir = _resolve_cloth_dir(cloth_category, CLOTH_RGB_BASE, _cloth_rgb_map)
    if not cloth_dir:
        return []
    scan_dirs = []
    rgb_sub = os.path.join(cloth_dir, "RGB")
    if os.path.isdir(rgb_sub):
        scan_dirs.append(rgb_sub)
    scan_dirs.append(cloth_dir)
    results = []
    seen = set()
    for sd in scan_dirs:
        try:
            for fn in sorted(os.listdir(sd)):
                if not fn.endswith(".json"):
                    continue
                jp = os.path.join(sd, fn)
                if jp in seen:
                    continue
                seen.add(jp)
                try:
                    with open(jp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cs = (data.get("primary_outfit") or {}).get("color") or []
                    colors = [extract_rgb(c) for c in cs if extract_rgb(c)]
                    results.append({
                        "id": str(data.get("id", os.path.splitext(fn)[0])),
                        "colors": colors, "color_strings": cs, "json_path": jp,
                    })
                except:
                    pass
        except:
            pass
        if results:
            break
    return results

def _compute_best_de(target_rgbs, cloth_rgb_data):
    if not cloth_rgb_data or not target_rgbs:
        return None, float("inf")
    best_cloth, best_de = None, float("inf")
    for cloth in cloth_rgb_data:
        if not cloth["colors"]:
            continue
        avg = sum(min(delta_e(t, c) for c in cloth["colors"])
                  for t in target_rgbs) / len(target_rgbs)
        if avg < best_de:
            best_de, best_cloth = avg, cloth
    return best_cloth, best_de

def find_closest_cloth_id_two_tier(json_data, cloth_rgb_data):
    if not cloth_rgb_data:
        return None, float("inf"), "none"
    primary_colors = (json_data.get("primary_outfit") or {}).get("color") or []
    primary_rgbs = [extract_rgb(c) for c in primary_colors if extract_rgb(c)]
    best_primary, de_primary = _compute_best_de(primary_rgbs, cloth_rgb_data)
    if best_primary and de_primary <= DE_GOOD_THRESHOLD:
        return best_primary, de_primary, "primary"
    bg_colors = json_data.get("best_primary_outfit_colour_based_on_background") or []
    bg_rgbs = [extract_rgb(c) for c in bg_colors if extract_rgb(c)]
    best_bg, de_bg = _compute_best_de(bg_rgbs, cloth_rgb_data)
    if best_primary and best_bg:
        if de_primary <= de_bg:
            return best_primary, de_primary, "primary"
        else:
            return best_bg, de_bg, "bg_based"
    elif best_primary:
        return best_primary, de_primary, "primary"
    elif best_bg:
        return best_bg, de_bg, "bg_based"
    else:
        return cloth_rgb_data[0] if cloth_rgb_data else None, float("inf"), "fallback"

def get_cloth_wr_image_path(cloth_category, cloth_id):
    cloth_dir = _resolve_cloth_dir(cloth_category, CLOTH_WR_BASE, _cloth_wr_map)
    if not cloth_dir:
        return None
    wr_dir = os.path.join(cloth_dir, "WR")
    if not os.path.isdir(wr_dir):
        wr_dir = cloth_dir
    try:
        imgs = [f for f in sorted(os.listdir(wr_dir))
                if os.path.splitext(f)[1].lower() in IMG_EXTS]
    except:
        return None
    if not imgs:
        return None
    cid = str(cloth_id).strip()
    for fn in imgs:
        if fn.startswith(f"{cid}.") and "wr" in fn.lower():
            return os.path.join(wr_dir, fn)
    for fn in imgs:
        if fn.startswith(f"{cid}."):
            return os.path.join(wr_dir, fn)
    for fn in imgs:
        m = re.match(r'^(\d+)[\.\-_]', fn)
        if m and m.group(1) == cid:
            return os.path.join(wr_dir, fn)
    for fn in imgs:
        if cid in fn:
            return os.path.join(wr_dir, fn)
    return os.path.join(wr_dir, imgs[0])

def resolve_cloth_path_by_id(cloth_id):
    """🆕 v2 — Given a Cxxx id already in the persistent cloth_index, locate
    its actual image file on disk. Used to REUSE the exact cloth image a
    pack was previously generated with (see scan_existing_pack_output)."""
    info = _cloth_index.get(cloth_id)
    if not info:
        return None
    fn  = info.get("filename")
    cat = info.get("cloth_type")
    if not fn:
        return None
    if cat:
        cat_dir = _resolve_cloth_dir(cat, CLOTH_WR_BASE, _cloth_wr_map)
        if cat_dir:
            wr_sub = os.path.join(cat_dir, "WR")
            scan_dir = wr_sub if os.path.isdir(wr_sub) else cat_dir
            p = os.path.join(scan_dir, fn)
            if os.path.exists(p):
                return p
    # Fallback: full walk of CLOTH_WR_BASE
    if os.path.isdir(CLOTH_WR_BASE):
        for root, _, files in os.walk(CLOTH_WR_BASE):
            if fn in files:
                return os.path.join(root, fn)
    return None

# ============================================================================
# SECTION 9.5 — 🆕 v2: DETECT ALREADY-PROCESSED PACK OUTPUT
# ----------------------------------------------------------------------------
# Scans OUTPUT_BASE/{cloth_category}/Original/{pack_id}/ and, for any
# {pack}.{n}.{Mxxx}.{Cxxx}.{studio}.Original.ext file already there:
#   - records n as "already done" (skip that image number, regardless of
#     what model/cloth THIS run would otherwise have picked)
#   - remembers the Mxxx / Cxxx tokens so the REST of the pack (if any
#     images are still missing) reuses the SAME model + cloth, instead of
#     re-matching and possibly picking a different one.
# ============================================================================
def scan_existing_pack_output(cloth_category, pack_id):
    pack_dir = build_pack_output_dir(cloth_category, pack_id)
    model_id, cloth_id = None, None
    done_nums = set()
    if not os.path.isdir(pack_dir):
        return model_id, cloth_id, done_nums
    for fn in os.listdir(pack_dir):
        if os.path.splitext(fn)[1].lower() not in IMG_EXTS:
            continue
        parts = fn.split(".")
        try:
            pid = int(parts[0]); n = int(parts[1])
        except:
            continue
        if pid != pack_id:
            continue
        fp = os.path.join(pack_dir, fn)
        if not (os.path.exists(fp) and os.path.getsize(fp) > 1000):
            continue
        done_nums.add(n)
        if not model_id:
            m_tok = next((p for p in parts if re.match(r'^M\d+$', p)), None)
            if m_tok:
                model_id = m_tok
        if not cloth_id:
            c_tok = next((p for p in parts if re.match(r'^C\d+$', p)), None)
            if c_tok:
                cloth_id = c_tok
    return model_id, cloth_id, done_nums

# ============================================================================
# SECTION 10 — PACK-WISE JOB BUILDER
# (model + cloth matched ONCE per pack, reused for every image in the pack)
# ============================================================================
def build_pack_job(cloth_category, pack_id, studio, images, model_pool):
    # 🆕 v2 EARLY SKIP — if every image number for this pack is already in
    # the output folder (any model/cloth id), skip the whole pack instantly:
    # no JSON read, no model matching, no cloth matching, no usage counted.
    existing_model_id, existing_cloth_id, done_nums = scan_existing_pack_output(cloth_category, pack_id)
    all_nums = {n for n, _, _ in images}
    if all_nums and all_nums.issubset(done_nums):
        print(f"   ✅ Pack {pack_id}: all {len(images)} image(s) already in output → skip pack entirely")
        return []

    json_path = find_pack_json(studio, pack_id)
    if not json_path:
        print(f"   ⚠️ Pack {pack_id}: FULL json not found for studio '{studio}' → skip pack")
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            jdata = json.load(f)
        print(f"   📄 Pack {pack_id}: JSON → {os.path.basename(json_path)}")
    except Exception as e:
        print(f"   ⚠️ Pack {pack_id}: JSON read error: {e} → skip pack")
        return []

    cloth_name = (jdata.get("cloth_name") or {}).get("women") or cloth_category

    if done_nums:
        print(f"   📂 Pack {pack_id}: {len(done_nums)}/{len(images)} image(s) already in output → will skip those")

    # ---------------- MODEL: reuse existing, else best-match-with-rotation ----------------
    chosen_model = None
    if existing_model_id:
        chosen_model = next((m for m in model_pool if m["no"] == existing_model_id), None)
        if chosen_model:
            print(f"   👤 Pack {pack_id}: reusing model from existing output → {chosen_model['name']} ({existing_model_id})  [no re-match, no usage bump]")
        else:
            print(f"   ⚠️ Pack {pack_id}: existing model id {existing_model_id} not found in current catalog → re-matching")

    if not chosen_model:
        json_model = jdata.get("model") or {}
        chosen_model = match_model_best(json_model, model_pool)
        if not chosen_model:
            print(f"   ⚠️ Pack {pack_id}: no model found → skip pack")
            return []
        _mark_model_used(chosen_model["no"])
        req_eth = json_model.get("ethnicity", "?")
        req_skin = json_model.get("skin_tone", "?")
        print(f"   👤 Pack {pack_id}: model → {chosen_model['name']} ({chosen_model['no']})  "
              f"[req: {req_eth}/{req_skin}]  [used {_model_usage[chosen_model['no']]}x on disk]")

    model_path = chosen_model["path"]
    model_id   = chosen_model["no"]

    # ---------------- CLOTH: reuse existing, else RGB two-tier match ----------------
    cloth_wr_path = None
    cloth_id = None
    de_score, match_source = None, None

    if existing_cloth_id:
        p = resolve_cloth_path_by_id(existing_cloth_id)
        if p:
            cloth_wr_path = p
            cloth_id = existing_cloth_id
            match_source = "reused_from_existing_output"
            print(f"   👗 Pack {pack_id}: reusing cloth from existing output → {cloth_id}")
        else:
            print(f"   ⚠️ Pack {pack_id}: existing cloth id {existing_cloth_id} file not found on disk → re-matching")

    if not cloth_wr_path:
        lookup_category = cloth_name
        cloth_rgb_data = scan_cloth_rgb_jsons(lookup_category)
        if not cloth_rgb_data and lookup_category != cloth_category:
            print(f"   🔄 Pack {pack_id}: trying folder name '{cloth_category}' instead of '{lookup_category}'")
            cloth_rgb_data = scan_cloth_rgb_jsons(cloth_category)
            if cloth_rgb_data:
                lookup_category = cloth_category

        best_cloth, de_score, match_source = find_closest_cloth_id_two_tier(jdata, cloth_rgb_data)
        if best_cloth:
            cloth_wr_path = get_cloth_wr_image_path(lookup_category, best_cloth["id"])
            if cloth_wr_path:
                de_str = f"{de_score:.1f}" if de_score != float("inf") else "∞"
                if de_score <= 2:     qlabel = "🟢 identical"
                elif de_score <= 5:   qlabel = "🟢 very close"
                elif de_score <= 10:  qlabel = "🟡 good"
                elif de_score <= 20:  qlabel = "🟠 weak"
                elif de_score <= 30:  qlabel = "🔴 poor"
                else:                 qlabel = "⛔ different"
                src_tag = "primary" if match_source == "primary" else "bg-color"
                print(f"   👗 Pack {pack_id}: cloth #{best_cloth['id']} (ΔE={de_str} {qlabel} via {src_tag}) → {os.path.basename(cloth_wr_path)}")

        if not cloth_wr_path:
            cloth_wr_path = get_cloth_wr_image_path(lookup_category, str(pack_id))
            if cloth_wr_path:
                print(f"   👗 Pack {pack_id}: fallback A (id={pack_id}) → {os.path.basename(cloth_wr_path)}")
        if not cloth_wr_path:
            cloth_wr_path = get_cloth_wr_image_path(lookup_category, "1")
            if cloth_wr_path:
                print(f"   👗 Pack {pack_id}: fallback B (id=1) → {os.path.basename(cloth_wr_path)}")
        if not cloth_wr_path:
            print(f"   ⚠️ Pack {pack_id}: ALL cloth lookups failed for '{lookup_category}' → skip pack")
            return []

        cloth_id = get_or_assign_cloth_id(cloth_wr_path, cloth_name)   # already pre-assigned; lookup
        print(f"   🏷️ Pack {pack_id}: cloth id → {cloth_id}")

    accessory_list = extract_accessories_from_json(jdata)
    job_prompt     = ITER2_PROMPT_TEMPLATE.format(accessory_list=accessory_list)
    print(f"   👜 Pack {pack_id}: accessories → {accessory_list}")

    flush_indexes()

    jobs = []
    for n, desc, wr_img_path in images:
        if n in done_nums:
            print(f"      ✅ #{n}: already in output → skip")
            continue
        out_path = build_output_image_path(cloth_category, pack_id, n, model_id, cloth_id, studio)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            print(f"      ✅ #{n}: already done → skip")
            continue
        jobs.append({
            "pack_id": pack_id, "img_num": n, "desc": desc, "studio": studio,
            "cloth_category": cloth_category, "cloth_name": cloth_name,
            "wr_img_path": wr_img_path,
            "model_path": model_path, "model_id": model_id,
            "cloth_wr_path": cloth_wr_path, "cloth_id": cloth_id,
            "json_path": json_path, "json_data": jdata,
            "de_score": de_score, "match_source": match_source or "unknown",
            "accessory_list": accessory_list, "prompt": job_prompt,
            "output_original": out_path,
            "status": S_IDLE, "tab_id": None, "result": None, "retries": 0,
        })
    return jobs

# ============================================================================
# SECTION 11 — CHROME WEBDRIVER SETUP
# ============================================================================
driver = None

def make_driver():
    opts = Options()
    opts.binary_location = chrome_bin
    opts.add_argument(f"--window-size={SCREEN_W},{SCREEN_H}")
    opts.add_argument("--start-maximized")
    opts.add_argument("--lang=en-US,en")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-renderer-backgrounding")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option("prefs", {
        "download.default_directory":   CHROME_DL_BASE,
        "download.prompt_for_download": False,
        "download.directory_upgrade":   True,
        "safebrowsing.enabled":         True,
    })
    opts.page_load_strategy = "normal"
    try:
        svc = Service(ChromeDriverManager().install())
    except:
        svc = Service()
    d   = webdriver.Chrome(service=svc, options=opts)
    d.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    d.set_page_load_timeout(60)
    d.set_script_timeout(60)
    d.implicitly_wait(3)
    print("✅ Chrome ready")
    return d

def create_tab(drv, url=GEMINI_APP_URL, wait_sec=1.0):
    try:
        before = set(drv.window_handles)
        drv.execute_cdp_cmd("Target.createTarget", {"url": url})
        nh = None
        for _ in range(int(wait_sec * 33)):
            diff = list(set(drv.window_handles) - before)
            if diff:
                nh = diff[0]
                break
            time.sleep(0.03)
        if not nh:
            all_h = drv.window_handles
            if len(all_h) > len(before):
                nh = all_h[-1]
        if not nh:
            return None
        drv.switch_to.window(nh)
        time.sleep(wait_sec)
        return nh
    except Exception as e:
        print(f"❌Tab:{e}")
        return None

def setup_tabs(drv, total=TOTAL_TABS):
    print(f"\n{'='*60}\n📑 SETTING UP {total} GENERATION TABS\n{'='*60}")
    handles = []
    try:
        drv.get(GEMINI_APP_URL)
        time.sleep(1.5)
        handles.append(drv.current_window_handle)
        print("✅ Tab 1 ready")
    except Exception as e:
        print(f"❌ Tab 1: {e}")
    for i in range(2, total + 1):
        print(f"📑 Tab {i}...", end=" ")
        h = create_tab(drv, url=GEMINI_APP_URL, wait_sec=0.8)
        if h:
            handles.append(h)
            print("✅")
        else:
            print("⚠️ FAILED")
    print(f"✅ {len(handles)}/{total} tabs ready")
    return handles

# ============================================================================
# SECTION 12 — COOKIE MANAGEMENT
# ============================================================================
def save_cookies(drv):
    try:
        with open(COOKIES_FILE, "wb") as f:
            pickle.dump(drv.get_cookies(), f)
        print("💾 Cookies saved")
    except Exception as e:
        print(f"⚠️ Cookie save: {e}")

def load_cookies(drv):
    if not os.path.exists(COOKIES_FILE):
        return False
    try:
        with open(COOKIES_FILE, "rb") as f:
            cookies = pickle.load(f)
        drv.get("https://myaccount.google.com")
        time.sleep(2)
        for c in cookies:
            try:
                if "sameSite" in c and c["sameSite"] not in ("Strict","Lax","None"):
                    c["sameSite"] = "None"
                drv.add_cookie(c)
            except:
                pass
        print("🍪 Cookies loaded")
        return True
    except:
        return False

# ============================================================================
# SECTION 13 — LOGIN & NAVIGATION
# ============================================================================
def check_captcha(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        url  = drv.current_url.lower()
        for sig in CAPTCHA_SIGNALS:
            if sig in body:
                return True
        for sig in SORRY_URL_SIGNALS:
            if sig in url:
                return True
    except:
        pass
    return False

def quick_check_logged_in(drv):
    try:
        url = drv.current_url.lower()
        if "accounts.google.com" in url or "signin" in url:
            return False
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for sig in SORRY_URL_SIGNALS + CAPTCHA_SIGNALS:
            if sig in body:
                return False
        return True
    except:
        return False

def get_user_input(prompt_text):
    return input(prompt_text).strip()

def handle_login(drv, wait):
    print("\n" + "=" * 60 + "\n🔐 GOOGLE LOGIN\n" + "=" * 60)
    if load_cookies(drv):
        drv.refresh()
        time.sleep(1.5)
        drv.get("https://myaccount.google.com/")
        time.sleep(1.5)
        if quick_check_logged_in(drv):
            ipy_display(HTML(
                "<h2 style='color:#34a853'>✅ LOGGED IN WITH COOKIES!</h2>"))
            return True

    drv.get("https://accounts.google.com/")
    time.sleep(1.5)
    if quick_check_logged_in(drv):
        save_cookies(drv)
        return True

    email = get_user_input("Email: ")
    if not email:
        return False
    try:
        ef = wait.until(EC.presence_of_element_located((By.ID, "identifierId")))
        ef.send_keys(email)
        time.sleep(0.5)
        drv.find_element(By.ID, "identifierNext").click()
        time.sleep(2)
    except:
        return False

    pwd = get_user_input("Password: ")
    if not pwd:
        return False
    try:
        pf = wait.until(EC.presence_of_element_located((By.NAME, "Passwd")))
        pf.send_keys(pwd)
        time.sleep(0.5)
        drv.find_element(By.ID, "passwordNext").click()
        time.sleep(3)
    except:
        return False

    if quick_check_logged_in(drv):
        save_cookies(drv)
        return True

    page = drv.find_element(By.TAG_NAME, "body").text.lower()
    if any(w in page for w in ["check your", "tap yes", "notification"]):
        ipy_display(HTML(
            "<h4 style='color:#fbbc04'>📱 Check phone for push notification</h4>"))
        for _ in range(12):
            time.sleep(5)
            if quick_check_logged_in(drv):
                save_cookies(drv)
                return True

    for sel in ["input[type='tel']", "input[name='totpPin']"]:
        try:
            for f in drv.find_elements(By.CSS_SELECTOR, sel):
                if f.is_displayed():
                    otp = get_user_input("2FA Code: ")
                    if otp:
                        f.clear()
                        f.send_keys(otp)
                        f.send_keys(Keys.RETURN)
                        time.sleep(3)
                        if quick_check_logged_in(drv):
                            save_cookies(drv)
                            return True
        except:
            continue

    if quick_check_logged_in(drv):
        save_cookies(drv)
        return True

    drv.get("https://myaccount.google.com/")
    time.sleep(1.5)
    if quick_check_logged_in(drv):
        save_cookies(drv)
        return True

    if get_user_input("Manually logged in? (y/n): ").lower() == "y":
        save_cookies(drv)
        return True
    return False

# ============================================================================
# SECTION 14 — TAB MANAGEMENT
# ============================================================================
tab_handles = []
tab_states  = {}

def switch_to_tab(tid):
    if tid < len(tab_handles):
        driver.switch_to.window(tab_handles[tid])
        return True
    return False

def find_idle_tab():
    for tid, st in tab_states.items():
        if st["state"] == S_IDLE:
            return tid
    return None

# ============================================================================
# SECTION 14.5 — FLASH MODE SWITCHER (UPDATED FOR NEW UI)
# ============================================================================
class ModelLimitReached(Exception):
    pass

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
        except:
            continue
    try:
        txt = drv.execute_script(
            "var el=document.querySelector("
            "  'div[data-test-id=\"logo-pill-label-container\"] "
            "  span.picker-primary-text,"
            "  div[data-test-id=\"logo-pill-label-container\"] "
            "  span.gds-body-m');"
            "return el ? el.textContent.trim() : '';"
        )
        return (txt or "").strip()
    except:
        return ""

def _open_model_picker(drv):
    try:
        btn = drv.find_element(
            By.CSS_SELECTOR, "button[data-test-id='bard-mode-menu-button']")
        if btn and btn.is_displayed():
            drv.execute_script("arguments[0].click();", btn)
            time.sleep(0.45)
            print("🔽Picker(btn)", end=" | ")
            return True
    except:
        pass
    try:
        el = drv.find_element(
            By.CSS_SELECTOR,
            "div[data-test-id='logo-pill-label-container']")
        if el and el.is_displayed():
            drv.execute_script("arguments[0].click();", el)
            time.sleep(0.45)
            print("🔽Picker(div)", end=" | ")
            return True
    except:
        pass
    try:
        icon = drv.find_element(
            By.CSS_SELECTOR,
            "div[data-test-id='logo-pill-label-container'] "
            "mat-icon[fonticon='keyboard_arrow_down'],"
            "div[data-test-id='logo-pill-label-container'] "
            "mat-icon[data-mat-icon-name='keyboard_arrow_down']"
        )
        if icon and icon.is_displayed():
            drv.execute_script("arguments[0].click();", icon)
            time.sleep(0.45)
            print("🔽Picker(icon)", end=" | ")
            return True
    except:
        pass
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[aria-label]"):
            lbl = (btn.get_attribute("aria-label") or "").lower()
            if ("mode picker" in lbl or "open mode" in lbl
                or "flash" in lbl or "pro" in lbl):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.45)
                    print("🔽Picker(aria)", end=" | ")
                    return True
    except:
        pass
    try:
        result = drv.execute_script(
            "var spans=document.querySelectorAll("
            "  'span.picker-primary-text,span.gds-body-m');"
            "for(var i=0;i<spans.length;i++){"
            "  var s=spans[i];"
            "  if(!s.offsetParent) continue;"
            "  var b=s.closest('button');"
            "  if(b&&!b.disabled){"
            "    b.click();return 'OK';"
            "  }"
            "} return 'NO';"
        )
        if result == "OK":
            time.sleep(0.45)
            print("🔽Picker(JS)", end=" | ")
            return True
    except:
        pass
    print("⚠️NoPicker", end=" | ")
    return False

def _wait_for_picker_open(drv, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            items = drv.find_elements(
                By.CSS_SELECTOR,
                "mat-option, "
                "[role='option'], "
                "[role='menuitem'], "
                "[role='menuitemradio'], "
                "button[data-test-id*='bard-mode-option']"
            )
            for item in items:
                if item.is_displayed():
                    return True
            overlays = drv.find_elements(
                By.CSS_SELECTOR,
                ".mat-mdc-select-panel,"
                ".cdk-overlay-pane,"
                "mat-select-panel,"
                "[role='listbox']"
            )
            for ov in overlays:
                if ov.is_displayed() and "flash" in ov.text.lower():
                    return True
        except:
            pass
        time.sleep(0.1)
    return False

def _click_flash_in_picker(drv):
    def _is_valid_flash_option(el):
        try:
            txt = (el.text or "").strip().lower()
            # Select 'flash', but explicitly exclude 'lite'
            return "flash" in txt and "lite" not in txt
        except:
            return False

    def _is_disabled(el):
        try:
            if el.get_attribute("disabled"):
                return True
            if el.get_attribute("aria-disabled") == "true":
                return True
            cls = (el.get_attribute("class") or "").lower()
            if "disabled" in cls:
                return True
        except:
            pass
        return False

    for tid in ["bard-mode-option-flash", "mode-option-flash",
                "flash-option", "model-flash"]:
        try:
            for el in drv.find_elements(
                By.CSS_SELECTOR, f"[data-test-id='{tid}']"):
                if el.is_displayed():
                    if _is_disabled(el):
                        raise ModelLimitReached(f"Flash disabled ({tid})")
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    print("✅Flash(tid)", end=" | ")
                    return True
        except ModelLimitReached:
            raise
        except:
            continue

    for sel in [
        "mat-option",
        "[role='option']",
        "[role='menuitem']",
        "[role='menuitemradio']",
        "button[class*='mode-option']",
        "button[class*='picker']",
    ]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed() and _is_valid_flash_option(el):
                    if _is_disabled(el):
                        raise ModelLimitReached("Flash option disabled")
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    print("✅Flash(role)", end=" | ")
                    return True
        except ModelLimitReached:
            raise
        except:
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
                    if _is_disabled(el):
                        raise ModelLimitReached("Flash disabled (xpath)")
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    print("✅Flash(xpath)", end=" | ")
                    return True
        except ModelLimitReached:
            raise
        except:
            continue

    try:
        result = drv.execute_script("""
        var candidates = document.querySelectorAll(
            'mat-option, [role="option"], [role="menuitem"],'
            '[role="menuitemradio"], button');
        for (var i = 0; i < candidates.length; i++) {
            var el = candidates[i];
            if (!el.offsetParent) continue;
            var txt = (el.textContent || '').trim().toLowerCase();
            if (txt.indexOf('flash') === -1) continue;
            if (txt.indexOf('lite') !== -1) continue; // Exclude 'lite'
            if (txt.length > 60) continue;
            var dis = el.getAttribute('disabled') ||
            el.getAttribute('aria-disabled') === 'true';
            if (dis) return 'DISABLED';
            el.click();
            return 'OK:' + txt;
        }
        return 'NO';
        """)
        if result and result.startswith("OK"):
            time.sleep(0.4)
            print(f"✅Flash(JS:{result[3:20]})", end=" | ")
            return True
        if result == "DISABLED":
            raise ModelLimitReached("Flash disabled (JS scan)")
    except ModelLimitReached:
        raise
    except:
        pass
    return False

def _verify_flash_selected(drv, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            txt = _get_current_model_text(drv)
            if txt and "flash" in txt.lower() and "lite" not in txt.lower():
                return True
        except:
            pass
        time.sleep(0.15)
        try:
            txt = _get_current_model_text(drv)
            return bool(txt and "flash" in txt.lower() and "lite" not in txt.lower())
        except:
            return False

def switch_to_flash(drv):
    current = _get_current_model_text(drv)
    if current and "flash" in current.lower() and "lite" not in current.lower():
        print("✅Flash(already)", end=" | ")
        return True
    print(f"🔄SwitchFlash(cur:{current or '?'})", end=" | ")
    for attempt in range(1, 3):
        if not _open_model_picker(drv):
            if attempt == 2:
                raise Exception("Flash: could not open model picker")
            time.sleep(0.5)
            continue
        opened = _wait_for_picker_open(drv, timeout=3.0)
        if not opened:
            print("⚠️PickerNotOpen(retry)", end=" | ")
            try:
                drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except:
                pass
            time.sleep(0.4)
            if attempt == 2:
                raise Exception("Flash: picker did not open")
            continue
        try:
            clicked = _click_flash_in_picker(drv)
        except ModelLimitReached:
            try:
                drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except:
                pass
            raise
        if not clicked:
            try:
                drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except:
                pass
            if attempt == 2:
                raise Exception("Flash: option not found in picker")
            time.sleep(0.5)
            continue
        if _verify_flash_selected(drv, timeout=3.0):
            print("✅Flash(verified)", end=" | ")
            return True
        now = _get_current_model_text(drv)
        print(f"⚠️FlashVerifyFail(now:{now or '?'})(a{attempt})", end=" | ")
        if attempt == 2:
            time.sleep(0.8)
            if _verify_flash_selected(drv, timeout=1.5):
                print("✅Flash(delayed)", end=" | ")
                return True
            raise Exception(
                f"Flash: selected but pill shows '{now}' after 2 attempts")
    raise Exception("Flash: exhausted all attempts")


# ============================================================================
# SECTION 15 — SELENIUM UI HELPERS
# ============================================================================
def grant_clipboard(drv):
    try:
        drv.execute_cdp_cmd("Browser.grantPermissions", {
            "origin": "https://gemini.google.com",
            "permissions": ["clipboardReadWrite", "clipboardSanitizedWrite"],
        })
    except:
        pass

def close_dialogs(drv):
    for sel in ["//button[@aria-label='Close']", "//button[@aria-label='Dismiss']"]:
        try:
            btn = drv.find_element(By.XPATH, sel)
            if btn.is_displayed():
                drv.execute_script("arguments[0].click();", btn)
        except:
            continue

def handle_consent(drv):
    try:
        for bsel in [
            "button[data-test-id='upload-image-agree-button']",
            "//button[.//span[contains(text(),'Agree')]]",
            "//span[text()='Agree']/ancestor::button",
        ]:
            try:
                by  = By.XPATH if bsel.startswith("//") else By.CSS_SELECTOR
                btn = drv.find_element(by, bsel)
                if btn and btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.15)
                    return True
            except:
                continue
    except:
        pass
    return False

def set_tab_download_dir(drv, path):
    ap = os.path.abspath(path)
    os.makedirs(ap, exist_ok=True)
    try:
        drv.execute_cdp_cmd("Page.setDownloadBehavior",
                            {"behavior": "allow", "downloadPath": ap})
    except:
        try:
            drv.execute_cdp_cmd("Browser.setDownloadBehavior",
                                {"behavior": "allow", "downloadPath": ap,
                                 "eventsEnabled": False})
        except:
            pass

def snapshot_urls(drv):
    try:
        return set(drv.execute_script(
            "return Array.from(document.querySelectorAll("
            "  'img[src^=\"blob:\"],img[src*=\"googleusercontent\"]'))"
            ".map(i=>i.src).filter(s=>s&&s.length>10);") or [])
    except:
        return set()

# ============================================================================
# SECTION 16: FAST UPLOAD FLOW
# ============================================================================
def _click_plus_button(drv):
    try:
        result = drv.execute_script(
            "var btns=document.querySelectorAll('button');"
            "for(var i=0;i<btns.length;i++){"
            "  var b=btns[i];"
            "  if(b.offsetParent===null) continue;"
            "  var lbl=(b.getAttribute('aria-label')||'').toLowerCase();"
            "  if(lbl.indexOf('upload')!==-1||lbl.indexOf('tools')!==-1||lbl.indexOf('plus')!==-1){"
            "    b.click();return 'OK';"
            "  }"
            "  var icon=b.querySelector('mat-icon[fonticon=\"plus\"],mat-icon[data-mat-icon-name=\"plus\"]');"
            "  if(icon){b.click();return 'OK';}"
            "}"
            "return 'NO';"
        )
        if result == "OK":
            time.sleep(0.3)
            return True
    except:
        pass
    for sel in ['button[aria-label="Upload and tools"]',
                'button[jslog*="300142"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except:
            continue
    return False

def _find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs:
        return inputs[0]
    try:
        drv.execute_script(
            "document.querySelectorAll('input[type=\"file\"]').forEach(function(el){"
            "  el.style.cssText='display:block!important;opacity:1!important;"
            "position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';"
            "});"
        )
    except:
        pass
    time.sleep(0.1)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def _wait_for_attachment_chip(drv, timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            for sel in ['button[aria-label="close attachment"]',
                        "gem-media-attachment", "uploader-file-preview",
                        ".attachment-preview-wrapper"]:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        return True
        except:
            pass
        time.sleep(0.15)
    return False

def _click_upload_files_in_drawer(drv):
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
        except:
            continue
    try:
        result = drv.execute_script(
            "var btns=document.querySelectorAll('button');"
            "for(var i=0;i<btns.length;i++){"
            "  if(btns[i].offsetParent!==null&&"
            "     btns[i].textContent.toLowerCase().indexOf('upload files')!==-1){"
            "    btns[i].click();return 'OK';"
            "  }"
            "}"
            "return 'NO';"
        )
        if result == "OK":
            time.sleep(0.2)
            return True
    except:
        pass
    return False

def _activate_image_mode_and_upload(drv, abs_paths):
    try:
        ta = drv.find_elements(By.CSS_SELECTOR,
            "div.ql-editor[data-placeholder='Describe your image']")
        if not ta:
            if _click_plus_button(drv):
                time.sleep(0.2)
                try:
                    btns = drv.find_elements(By.CSS_SELECTOR,
                        "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button")
                    for btn in btns:
                        if btn.is_displayed() and "Create image" in btn.text:
                            drv.execute_script("arguments[0].click();", btn)
                            time.sleep(0.25)
                            break
                    else:
                        for icon in drv.find_elements(By.CSS_SELECTOR,
                            "mat-icon[data-mat-icon-name='image_create'],"
                            "mat-icon[fonticon='image_create']"):
                            if icon.is_displayed():
                                btn = drv.execute_script(
                                    "var e=arguments[0];while(e&&e.tagName!=='BUTTON')e=e.parentElement;return e;",
                                    icon)
                                if btn and btn.is_displayed():
                                    drv.execute_script("arguments[0].click();", btn)
                                    time.sleep(0.25)
                                    break
                except:
                    pass
    except:
        pass

    if not _click_plus_button(drv):
        return False
    time.sleep(0.2)
    if not _click_upload_files_in_drawer(drv):
        try:
            drv.execute_script(
                "var b=document.querySelector("
                "  'button.hidden-local-file-image-selector-button,"
                "   button[xapfileselectortrigger]');"
                "if(b)b.click();"
            )
            time.sleep(0.1)
        except:
            pass

    fi = _find_file_input(drv)
    if not fi:
        return False

    try:
        if isinstance(abs_paths, list):
            fi.send_keys("\n".join(abs_paths))
        else:
            fi.send_keys(abs_paths)
    except Exception as e:
        print(f"⚠️FileInputErr:{str(e)[:20]}", end=" | ")
        return False

    expected_count = len(abs_paths) if isinstance(abs_paths, list) else 1
    attached = _wait_for_attachment_chip(drv, timeout=6.0)
    if attached:
        print(f"✅Attached({expected_count})", end=" | ")
    else:
        print("⚠️NoChip(cont)", end=" | ")
    return True

# ============================================================================
# SECTION 17: FAST CLIPBOARD INJECTION
# ============================================================================
def _set_clipboard_xclip(text):
    disp = os.environ.get("DISPLAY", ":99")
    env  = {**os.environ, "DISPLAY": disp}
    try:
        proc = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=env)
        proc.communicate(input=text.encode("utf-8"), timeout=5)
        return proc.returncode == 0
    except:
        return False

def _get_quill_editor(drv):
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
        except:
            pass
    return None

def _verify_editor_content(drv, editor, expected_text, timeout=4.0):
    min_len = max(10, int(len(expected_text) * 0.85))
    first40 = expected_text[:40].strip()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            content = (editor.text or "").strip()
            if not content:
                content = drv.execute_script(
                    "return (arguments[0].textContent || '').trim();", editor) or ""
            if len(content) >= min_len and first40 in content:
                return True
        except:
            pass
        time.sleep(0.1)
    return False

def _inject_prompt_fast(drv, text):
    editor = _get_quill_editor(drv)
    if not editor:
        print("⚠️NoEditor", end=" | ")
        return False

    try:
        drv.execute_script("arguments[0].focus();", editor)
        ActionChains(drv).click(editor)\
            .key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL)\
            .perform()
        editor.send_keys(Keys.DELETE)
    except:
        pass

    if _set_clipboard_xclip(text):
        try:
            drv.execute_script("arguments[0].focus();", editor)
            ActionChains(drv).click(editor)\
                .key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL)\
                .perform()
            time.sleep(0.2)
            if _verify_editor_content(drv, editor, text, timeout=3.0):
                print("✏️xclip✅", end=" | ")
                return True

            drv.execute_script("arguments[0].focus();", editor)
            ActionChains(drv).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
            time.sleep(0.2)
            if _verify_editor_content(drv, editor, text, timeout=2.0):
                print("✏️xclip2✅", end=" | ")
                return True
        except:
            pass

    try:
        drv.execute_script("arguments[0].focus();", editor)
        drv.execute_script(
            "document.execCommand('selectAll',false,null);"
            "document.execCommand('delete',false,null);"
            "document.execCommand('insertText',false,arguments[0]);", text)
        time.sleep(0.2)
        if _verify_editor_content(drv, editor, text, timeout=3.0):
            print("✏️execCmd✅", end=" | ")
            return True
    except:
        pass

    try:
        drv.execute_script("arguments[0].focus();", editor)
        ActionChains(drv).click(editor)\
            .key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL)\
            .perform()
        editor.send_keys(Keys.DELETE)
        for i in range(0, len(text), 500):
            editor.send_keys(text[i:i+500])
            time.sleep(0.02)
        time.sleep(0.2)
        if _verify_editor_content(drv, editor, text, timeout=4.0):
            print("✏️sendkeys✅", end=" | ")
            return True
    except:
        pass

    print("❌InjectFail", end=" | ")
    return False

# ============================================================================
# SECTION 18: FAST SEND BUTTON
# ============================================================================
def _click_send_button(drv):
    try:
        result = drv.execute_script(
            "var sels=['mat-icon[fonticon=\"arrow_upward\"]',"
            "  'mat-icon[data-mat-icon-name=\"arrow_upward\"]',"
            "  'mat-icon[fonticon=\"send\"]',"
            "  'button[aria-label=\"Send message\"]'];"
            "for(var s=0;s<sels.length;s++){"
            "  var els=document.querySelectorAll(sels[s]);"
            "  for(var i=0;i<els.length;i++){"
            "    var b=els[i].tagName==='BUTTON'?els[i]:els[i].closest('button');"
            "    if(b&&!b.disabled&&b.offsetParent!==null){b.click();return 'OK';}"
            "  }"
            "}"
            "return 'NO';"
        )
        return result == "OK"
    except:
        pass
    for xpath in [
        "//mat-icon[@data-mat-icon-name='arrow_upward']/ancestor::button",
        "//mat-icon[@fonticon='arrow_upward']/ancestor::button",
        "//button[@aria-label='Send message']",
    ]:
        try:
            for btn in drv.find_elements(By.XPATH, xpath):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].click();", btn)
                    return True
        except:
            continue
    return False

# ============================================================================
# SECTION 19: COMPLETE UPLOAD+SEND FLOW (FAST)
# ============================================================================
def _copy_local(src, tag=""):
    dst = os.path.join(LOCAL_COPY_BASE,
        f"{tag}_{os.path.basename(src)}" if tag else os.path.basename(src))
    try:
        shutil.copy2(src, dst)
        return dst
    except:
        return src

def upload_and_send_fast(job, tab_id, max_send_retries=6):
    drv = driver
    try:
        switch_to_tab(tab_id)
        time.sleep(0.3)

        set_tab_download_dir(drv, CHROME_DL_BASE)

        drv.get(GEMINI_APP_URL)
        time.sleep(1.5)

        if check_captcha(drv):
            print("⚠️CAPTCHA", end=" | ")
            return "CAPTCHA"

        try:
            body = drv.find_element(By.TAG_NAME, "body").text.lower()
            for p in PRO_LIMIT_PHRASES:
                if p in body:
                    print(f"🛑LIMIT:{p}", end=" | ")
                    return "LIMIT"
        except:
            pass

        imgs = [
            _copy_local(job["wr_img_path"],   f"pose_{job['pack_id']}_{job['img_num']}"),
            _copy_local(job["model_path"],     f"face_{job['pack_id']}_{job['img_num']}"),
            _copy_local(job["cloth_wr_path"],  f"cloth_{job['pack_id']}_{job['img_num']}"),
        ]
        abs_paths = [os.path.abspath(p) for p in imgs if os.path.exists(p)]
        if not abs_paths:
            print("❌NoFiles", end=" | ")
            return False

        print(f"\n📤 Pack{job['pack_id']}#{job['img_num']}: ", end="")

        try:
            switch_to_flash(drv)
        except ModelLimitReached:
            print("🛑LIMIT(Flash)", end=" | ")
            return "LIMIT"
        except Exception as e:
            print(f"⚠️FlashSwitch:{str(e)[:30]}", end=" | ")

        if not _activate_image_mode_and_upload(drv, abs_paths):
            print("❌UploadFail", end=" | ")
            return False

        handle_consent(drv)

        if not _inject_prompt_fast(drv, job["prompt"]):
            print("❌PromptFail", end=" | ")
            return False

        time.sleep(0.1)
        handle_consent(drv)

        for _ in range(max_send_retries):
            if _click_send_button(drv):
                print("✅Sent", end=" | ")
                return True
            time.sleep(0.2)
            handle_consent(drv)

        try:
            editor = _get_quill_editor(drv)
            if editor and editor.is_displayed():
                editor.send_keys(Keys.RETURN)
                print("✅Sent(↵)", end=" | ")
                return True
        except:
            pass

        print("❌SendFail", end=" | ")
        return False

    except Exception as e:
        print(f"\n❌ Upload error tab {tab_id}: {e}")
        try:
            drv.save_screenshot(os.path.join(ERR_SS_DIR, f"err_t{tab_id}_{int(time.time())}.png"))
        except:
            pass
        return False

# ============================================================================
# SECTION 20: GENERATION DETECTION
# ============================================================================
def check_text_error(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for p in TEXT_REFUSAL:
            if p in body: return "refusal"
        for p in PRO_LIMIT_PHRASES:
            if p in body: return "limit"
    except:
        pass
    return None

def check_gemini_error(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        url  = drv.current_url.lower()
        for p in GEMINI_ERROR_SIG:
            if p in body: return "error"
        for s in SORRY_URL_SIGNALS:
            if s in url: return "sorry"
    except:
        pass
    return None

def _send_btn_enabled(drv):
    try:
        return drv.execute_script(
            "var sels=['mat-icon[fonticon=\"arrow_upward\"]',"
            "  'mat-icon[data-mat-icon-name=\"arrow_upward\"]',"
            "  'mat-icon[fonticon=\"send\"]',"
            "  'button[aria-label=\"Send message\"]'];"
            "for(var s=0;s<sels.length;s++){"
            "  var els=document.querySelectorAll(sels[s]);"
            "  for(var i=0;i<els.length;i++){"
            "    var b=els[i].tagName==='BUTTON'?els[i]:els[i].closest('button');"
            "    if(b&&!b.disabled&&b.offsetParent!==null)return true;"
            "  }"
            "}"
            "return false;"
        )
    except:
        return False

def _thumb_up_visible(drv):
    try:
        return drv.execute_script(
            "var icons=document.querySelectorAll("
            "  'mat-icon[data-mat-icon-name=\"thumb_up\"]',"
            "   mat-icon[fonticon=\"thumb_up\"]');"
            "for(var i=0;i<icons.length;i++){"
            "  if(icons[i].offsetParent!==null)return true;"
            "}"
            "return false;"
        )
    except:
        return False

def _is_gemini_processing(drv):
    try:
        stop = drv.execute_script(
            "var sels=['button[aria-label=\"Stop generating\"]',"
            "  'button[aria-label=\"Cancel\"]',"
            "  'mat-icon[fonticon=\"stop\"]',"
            "  'mat-icon[data-mat-icon-name=\"stop\"]'];"
            "for(var s=0;s<sels.length;s++){"
            "  var els=document.querySelectorAll(sels[s]);"
            "  for(var i=0;i<els.length;i++){"
            "    if(els[i].offsetParent!==null)return true;"
            "  }"
            "}"
            "return false;"
        )
        if stop:
            return True
        loading = drv.execute_script(
            "var el=document.querySelector("
            "  'image-loading-overlay [data-test-id=\"image-loading-overlay\"]');"
            "if(el&&el.offsetParent!==null){"
            "  return !el.classList.contains('done-generating');"
            "}"
            "return false;"
        )
        return bool(loading)
    except:
        return False

def _has_generated_image(drv, urls_before):
    try:
        blob_srcs = drv.execute_script(
            "var srcs=[];"
            "var imgs=document.querySelectorAll('img[src^=\"blob:https://gemini.google.com\"]');"
            "for(var i=imgs.length-1;i>=0;i--){"
            "  var img=imgs[i];if(!img.offsetParent)continue;"
            "  var src=img.getAttribute('src')||'';"
            "  var tid=img.getAttribute('data-test-id')||'';"
            "  if(tid.indexOf('uploaded-img')!==-1||tid==='image-preview')continue;"
            "  if(src.length>10)srcs.push(src);"
            "}"
            "return srcs;"
        ) or []
        for src in blob_srcs:
            if src not in urls_before:
                return src
    except:
        pass
    for sel in ["generated-image img", "single-image img",
                "img[src*='googleusercontent']",
                "model-response img", ".response-container-content img"]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if not img.is_displayed():
                        continue
                    src = img.get_attribute("src") or ""
                    tid = img.get_attribute("data-test-id") or ""
                    if len(src) < 10 or "uploaded-img" in tid or tid == "image-preview":
                        continue
                    if src in urls_before:
                        continue
                    if (src.startswith("blob:https://gemini.google.com")
                        or "googleusercontent" in src):
                        return src
                except:
                    continue
        except:
            pass
    return None

def nb_check_image(drv, urls_before, chat_urls):
    rc = check_text_error(drv)
    if rc:
        return (GEN_REFUSED if rc == "refusal" else GEN_LIMIT), None

    ge = check_gemini_error(drv)
    if ge:
        return GEN_ERROR, None

    img_src = _has_generated_image(drv, urls_before)
    if img_src and img_src not in chat_urls:
        chat_urls.add(img_src)
        return GEN_SUCCESS, img_src

    if _thumb_up_visible(drv):
        rc2 = check_text_error(drv)
        if rc2:
            return (GEN_REFUSED if rc2 == "refusal" else GEN_LIMIT), None

        ge2 = check_gemini_error(drv)
        if ge2:
            return GEN_ERROR, None

        img_src2 = _has_generated_image(drv, urls_before)
        if img_src2 and img_src2 not in chat_urls:
            chat_urls.add(img_src2)
            return GEN_SUCCESS, img_src2

        return GEN_TIMEOUT_S, None   # text-only response, no image

    if _is_gemini_processing(drv):
        return S_GEN_WAITING, None

    if _send_btn_enabled(drv) and not _is_gemini_processing(drv):
        return S_GEN_WAITING, None

    return S_GEN_WAITING, None

# ============================================================================
# SECTION 21: DOWNLOAD (saves straight to final Original path)
# ============================================================================
def _direct_fetch(drv, save_path, urls_before):
    try:
        blob = drv.execute_script(
            "var imgs=document.querySelectorAll("
            "  'single-image img,generated-image img,"
            "   img[src^=\"blob:https://gemini.google.com\"]');"
            "for(var i=imgs.length-1;i>=0;i--){"
            "  var s=imgs[i].getAttribute('src');"
            "  if(s&&s.startsWith('blob:https://gemini.google.com'))return s;"
            "}"
            "return null;"
        )
        if not blob or blob in urls_before:
            return False
        expr = (
            "fetch('" + blob + "').then(function(r){return r.blob();})"
            ".then(function(b){return new Promise(function(resolve){"
            "  var fr=new FileReader();"
            "  fr.onloadend=function(){resolve(fr.result.split(',')[1]);};"
            "  fr.readAsDataURL(b);"
            "});})"
        )
        result = drv.execute_cdp_cmd("Runtime.evaluate", {
            "expression": expr, "awaitPromise": True, "returnByValue": True})
        if result and "result" in result and "value" in result["result"]:
            data = base64.b64decode(result["result"]["value"])
            if len(data) > 5000:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                Path(save_path).write_bytes(data)
                print(f"✅Fetch({len(data)//1024}KB)", end=" | ")
                return True
    except:
        pass
    return False

def _hover_and_dl(drv, urls_before, excluded, dl_dir):
    def _try_hover(img):
        try:
            drv.execute_script("arguments[0].scrollIntoView({block:'center'});", img)
            time.sleep(0.3)
            try:
                ActionChains(drv).move_to_element(img).perform()
                time.sleep(0.4)
                for sel in [
                    "button[data-test-id='download-generated-image-button']",
                    "//mat-icon[@data-mat-icon-name='download']/ancestor::button",
                    "//mat-icon[@fonticon='download']/ancestor::button",
                    "button[aria-label='Download full-sized image']",
                ]:
                    by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                    for btn in reversed(drv.find_elements(by, sel)):
                        if btn.is_displayed() and btn.is_enabled():
                            drv.execute_script("arguments[0].click();", btn)
                            return True
            except:
                pass
        except:
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
                if ("uploaded-img" in tid or tid == "image-preview"
                    or src in urls_before or src in excluded
                    or src in seen or len(src) < 10):
                    continue
                seen.add(src)
                candidates.append(img)
        except:
            continue

    for img in reversed(candidates):
        try:
            if img.is_displayed() and _try_hover(img):
                return True
        except:
            continue

    try:
        clicked = drv.execute_script(
            "window.scrollTo(0,document.body.scrollHeight);"
            "var btns=document.querySelectorAll("
            "  'button[data-test-id=\"download-generated-image-button\"],"
            "   button[aria-label*=\"Download\"]');"
            "for(var i=btns.length-1;i>=0;i--){"
            "  var b=btns[i];"
            "  if(b.offsetParent!==null&&!b.disabled){"
            "    b.scrollIntoView({block:'center'});b.click();return 'OK';"
            "  }"
            "}"
            "return null;"
        )
        if clicked:
            return True
    except:
        pass
    return False

def _wait_for_dl_file(dl_dir, files_before, timeout=None):
    if timeout is None:
        timeout = DOWNLOAD_TIMEOUT
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            cur = set(os.listdir(dl_dir))
            new_files = {f for f in (cur - files_before)
                         if not f.endswith((".crdownload", ".tmp", ".part"))
                         and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))}
            if new_files:
                fn = sorted(new_files,
                            key=lambda f: os.path.getmtime(os.path.join(dl_dir, f)),
                            reverse=True)[0]
                fp = os.path.join(dl_dir, fn)
                if os.path.getsize(fp) > 5000:
                    return fp
        except:
            pass
        time.sleep(0.3)
    return None

def download_generated_image(drv, save_path, urls_before, chat_urls, dl_dir):
    if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
        return True
    if _direct_fetch(drv, save_path, urls_before):
        return True
    time.sleep(0.3)
    for attempt in range(1, 4):
        print(f"⬇️A{attempt}", end=" | ")
        try:
            files_before_dl = set(os.listdir(dl_dir)) if os.path.exists(dl_dir) else set()
            drv.execute_script("window.scrollTo(0,document.body.scrollHeight);")
            time.sleep(0.2)
            hover_ok = _hover_and_dl(drv, urls_before, chat_urls, dl_dir)
            fp = _wait_for_dl_file(dl_dir, files_before_dl,
                                   timeout=DOWNLOAD_TIMEOUT if hover_ok else 6)
            if fp:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(fp, save_path)
                except:
                    shutil.copy2(fp, save_path)
                try:
                    os.remove(fp)
                except:
                    pass
                if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
                    print(f"✅DL({os.path.getsize(save_path)//1024}KB)", end=" | ")
                    return True
        except Exception as e:
            print(f"⚠️DLErr:{str(e)[:15]}", end=" | ")
            time.sleep(0.3)
        if _direct_fetch(drv, save_path, urls_before):
            return True
    print("❌DLFail", end=" | ")
    return False

# ============================================================================
# SECTION 22 — MAIN EXECUTION LOOP (pack-wise, Original only)
# 🆕 v2: faster stuck-tab detection + explicit refresh on timeout, so all 6
# tabs keep cycling continuously (download → refresh → upload next → send)
# instead of one tab quietly blocking the whole pipeline.
# ============================================================================
def main():
    global driver
    print("\n" + "=" * 70)
    print("🚀 ECOM 2 ITERATION — PACK-WISE Pipeline v2 (Original only)")
    print("   ✨ True Multi-Tab Polling | Model/Cloth matched once per pack")
    print("   ✨ Skip-detection fixed | Usage counted from filenames")
    print("=" * 70)

    if not os.path.isdir(WOMEN_JSON_DIR):
        print(f"\n❌ FATAL: WOMEN_JSON_DIR invalid: '{WOMEN_JSON_DIR}'")
        return

    # ------------------------------------------------------------------
    # STEP 0a — Load the FIXED model catalog (model_index.json) and
    # resolve every entry to its actual image file under
    # Female Model/R WEBP/{name}.ext. Usage counts (for anti-repeat
    # rotation) are computed fresh from existing OUTPUT filenames.
    # ------------------------------------------------------------------
    model_pool = load_model_catalog()
    print(f"📊 Model usage snapshot from disk: "
          f"{dict(sorted(_model_usage.items())) if _model_usage else '(none yet)'}")

    # ------------------------------------------------------------------
    # STEP 0b — BULK PRE-ASSIGNMENT (cloths only): assign IDs to EVERY
    # cloth image on disk BEFORE anything else runs.
    # ------------------------------------------------------------------
    run_bulk_pre_assignment()

    print(f"\n📂 Scanning ITER1 packs: {ITER1_BASE}")
    packs = scan_iter1_packs()
    if not packs:
        print("❌ No pack folders found!")
        return

    pack_ids_all = sorted(set(pid for (_, pid) in packs.keys()))
    total_imgs = sum(len(v["images"]) for v in packs.values())

    print("\n" + "=" * 70)
    print(f"👗 {len(packs)} pack(s), {total_imgs} image(s) total\n")
    by_cloth_count = defaultdict(int)
    for (cloth, pid), v in packs.items():
        by_cloth_count[cloth] += len(v["images"])
    for cloth in sorted(by_cloth_count):
        print(f"  {cloth:<40s} {by_cloth_count[cloth]:>5d} images")
    print(f"\nPack ID range: {min(pack_ids_all)} – {max(pack_ids_all)}")
    print("=" * 70)

    range_str = input("\nEnter PACK ID range:  1-50  |  1,5,10  |  all\nRange: ").strip()
    selected_packs = parse_pack_range(range_str, set(pack_ids_all))
    if not selected_packs:
        print("❌ No valid packs in range")
        return
    print(f"✅ Selected {len(selected_packs)} pack(s)")

    print("\n🖥️ Setting up remote desktop...")
    setup_novnc_ui()

    print("\n🌐 Starting Chrome...")
    driver = make_driver()
    wait = WebDriverWait(driver, 15)

    if not handle_login(driver, wait):
        print("❌ Login failed!")
        return

    print("✅ LOGGED IN — PACK-WISE pipeline ready")

    global tab_handles, tab_states
    tab_handles = setup_tabs(driver, TOTAL_TABS)

    tab_states = {}
    for tid in range(len(tab_handles)):
        tab_states[tid] = {
            "state": S_IDLE, "job": None, "start_time": 0,
            "urls_before": set(), "chat_urls": set(), "next_poll": 0,
            "stuck_polls": 0,
        }

    switch_to_tab(0)

    # Build job queue PACK-WISE: model matched via best-match-with-rotation
    # against the fixed catalog, or REUSED from existing output if the pack
    # already has some images done. Cloth is either reused from existing
    # output or matched/pre-assigned as before.
    job_queue = []
    skipped_pre = 0
    for (cloth_category, pack_id), info in sorted(packs.items(), key=lambda kv: kv[0][1]):
        if pack_id not in selected_packs:
            continue
        print(f"\n{'─'*50}")
        print(f"🔧 Pack {pack_id} ({cloth_category}): building job(s) for {len(info['images'])} image(s)...")
        pjobs = build_pack_job(cloth_category, pack_id, info["studio"], info["images"], model_pool)
        if pjobs:
            job_queue.extend(pjobs)
        else:
            print(f"   ⏭️ Pack {pack_id}: build failed or already complete → skip")
            skipped_pre += len(info["images"])

    total     = len(job_queue)
    completed = 0
    failed    = 0
    limit_hit = False

    print(f"\n{'='*70}")
    print(f"🏭 PROCESSING {total} IMAGES (Pack-wise, Original only)")
    print(f"{'='*70}\n")

    last_status = 0
    while True:
        now = time.time()

        if now - last_status > 15:
            last_status = now
            active_count = sum(1 for tid in range(len(tab_handles)) if tab_states[tid]["state"] == S_GEN_WAITING)
            status_str = " | ".join(
                f"T{tid}:{tab_states[tid]['state'][0]}#{tab_states[tid]['job']['img_num'] if tab_states[tid]['job'] else '-'}"
                for tid in range(len(tab_handles))
            )
            print(f"\n📊 [STATUS] Q:{len(job_queue)} ✅{completed} ❌{failed} ⏭️{skipped_pre} | {active_count} generating | {status_str}\n")

        if limit_hit:
            busy = any(tab_states[tid]["state"] != S_IDLE for tid in range(len(tab_handles)))
            if not busy:
                break

        all_idle = all(tab_states[tid]["state"] == S_IDLE for tid in range(len(tab_handles)))
        if all_idle and not job_queue:
            break

        # 1. ASSIGN IDLE TABS — immediately grab the next job the moment a
        #    tab goes idle (right after a successful download, a skip, or a
        #    requeue), so all 6 tabs keep cycling continuously.
        for tid in range(len(tab_handles)):
            if tab_states[tid]["state"] != S_IDLE or not job_queue or limit_hit:
                continue

            job = job_queue.pop(0)
            switch_to_tab(tid)

            print(f"\n🟢 [T{tid}] Pack{job['pack_id']}#{job['img_num']}: {job['desc'][:40]}…", end=" | ")

            urls_before = snapshot_urls(driver)
            result = upload_and_send_fast(job, tid)

            if result is True:
                chat_urls = snapshot_urls(driver) - urls_before
                tab_states[tid]["state"] = S_GEN_WAITING
                tab_states[tid]["job"] = job
                tab_states[tid]["start_time"] = now
                tab_states[tid]["urls_before"] = urls_before
                tab_states[tid]["chat_urls"] = chat_urls
                tab_states[tid]["next_poll"] = now + 2.0
                tab_states[tid]["stuck_polls"] = 0
                print(f"📤 generating…")
            elif result == "CAPTCHA":
                print(f"\n⚠️ [T{tid}] CAPTCHA — waiting 60s...")
                job_queue.insert(0, job)
                time.sleep(60)
                break
            elif result == "LIMIT":
                print(f"\n🛑 [T{tid}] PRO LIMIT → HARD STOP")
                limit_hit = True
                job_queue.insert(0, job)
                tab_states[tid]["state"] = S_IDLE
                tab_states[tid]["job"] = None
                break
            else:
                print(f"❌ [T{tid}] setup failed")
                failed += 1
                tab_states[tid]["state"] = S_IDLE
                tab_states[tid]["job"] = None

        # 2. POLL ACTIVE TABS — go tab-by-tab every round; if one tab isn't
        #    ready to be polled yet (next_poll in the future) we simply move
        #    on to check the next tab immediately (no blocking wait).
        for tid in range(len(tab_handles)):
            if tab_states[tid]["state"] != S_GEN_WAITING:
                continue
            if now < tab_states[tid]["next_poll"]:
                continue

            switch_to_tab(tid)
            info = tab_states[tid]
            job = info["job"]
            elapsed = now - info["start_time"]

            if elapsed > MAX_STATE_TIMEOUT:
                print(f"\n⏰ [T{tid}] Pack{job['pack_id']}#{job['img_num']}: TIMEOUT ({elapsed:.0f}s) → refreshing tab")
                try:
                    driver.get(GEMINI_APP_URL)
                    time.sleep(0.5)
                except:
                    pass
                if job.get("retries", 0) < 1:
                    job["retries"] = job.get("retries", 0) + 1
                    job_queue.insert(0, job)
                else:
                    failed += 1
                tab_states[tid]["state"] = S_IDLE
                tab_states[tid]["job"] = None
                tab_states[tid]["stuck_polls"] = 0
                continue

            err = check_gemini_error(driver)
            if err:
                print(f"\n❌ [T{tid}] Pack{job['pack_id']}#{job['img_num']}: PAGE ERROR — {err} → refreshing tab")
                try:
                    driver.get(GEMINI_APP_URL)
                    time.sleep(0.5)
                except:
                    pass
                if job.get("retries", 0) < 1:
                    job["retries"] = job.get("retries", 0) + 1
                    job_queue.insert(0, job)
                else:
                    failed += 1
                tab_states[tid]["state"] = S_IDLE
                tab_states[tid]["job"] = None
                tab_states[tid]["stuck_polls"] = 0
                continue

            status, msg = nb_check_image(driver, info["urls_before"], info["chat_urls"])

            if status == GEN_SUCCESS:
                print(f"\n✅ [T{tid}] Pack{job['pack_id']}#{job['img_num']}: done ({elapsed:.0f}s)")
                save_path = job["output_original"]
                print(f"   ⬇️ Downloading: ", end="")
                dl_ok = download_generated_image(
                    driver, save_path, info["urls_before"], info["chat_urls"], CHROME_DL_BASE
                )
                print()
                if dl_ok:
                    update_pack_manifest(job)
                    completed += 1
                    print(f"   🎉 [T{tid}] Pack{job['pack_id']}#{job['img_num']} DONE [{completed}/{total}]")
                else:
                    print(f"   ❌ [T{tid}] Download failed Pack{job['pack_id']}#{job['img_num']}")
                    failed += 1
                # 🆕 v2: tab goes IDLE immediately — the very next loop
                # iteration's "ASSIGN IDLE TABS" step will refresh this tab
                # (upload_and_send_fast starts with driver.get) and send the
                # next queued image, right away.
                tab_states[tid]["state"] = S_IDLE
                tab_states[tid]["job"] = None
                tab_states[tid]["stuck_polls"] = 0

            elif status == GEN_LIMIT:
                print(f"\n🛑 [T{tid}] PRO LIMIT: {msg}")
                limit_hit = True
                job_queue.insert(0, job)
                tab_states[tid]["state"] = S_IDLE
                tab_states[tid]["job"] = None
                tab_states[tid]["stuck_polls"] = 0

            elif status == GEN_REFUSED:
                print(f"\n🚫 [T{tid}] Pack{job['pack_id']}#{job['img_num']}: REFUSED — {msg}")
                failed += 1
                tab_states[tid]["state"] = S_IDLE
                tab_states[tid]["job"] = None
                tab_states[tid]["stuck_polls"] = 0

            elif status == GEN_ERROR:
                print(f"\n❌ [T{tid}] Pack{job['pack_id']}#{job['img_num']}: ERROR — {msg}")
                if job.get("retries", 0) < 1:
                    job["retries"] = job.get("retries", 0) + 1
                    job_queue.insert(0, job)
                else:
                    failed += 1
                tab_states[tid]["state"] = S_IDLE
                tab_states[tid]["job"] = None
                tab_states[tid]["stuck_polls"] = 0

            elif status == GEN_TIMEOUT_S:
                print(f"\n⏭️ [T{tid}] Pack{job['pack_id']}#{job['img_num']}: TEXT-ONLY (no image)")
                failed += 1
                tab_states[tid]["state"] = S_IDLE
                tab_states[tid]["job"] = None
                tab_states[tid]["stuck_polls"] = 0

            else:
                # status == S_GEN_WAITING
                if _is_gemini_processing(driver):
                    tab_states[tid]["stuck_polls"] = 0
                    tab_states[tid]["next_poll"] = now + 1.0
                elif _send_btn_enabled(driver):
                    # 🆕 v2 — Gemini finished responding (send button is
                    # enabled again) but we detected no image, no thumb-up,
                    # no refusal, no error. Count consecutive "nothing
                    # happening" polls; after SOFT_STUCK_POLLS, stop waiting
                    # for the full MAX_STATE_TIMEOUT — refresh this tab and
                    # requeue the job so another tab (or this one, refreshed)
                    # can pick it up right away.
                    tab_states[tid]["stuck_polls"] = tab_states[tid].get("stuck_polls", 0) + 1
                    if tab_states[tid]["stuck_polls"] >= SOFT_STUCK_POLLS:
                        print(f"\n⚠️ [T{tid}] Pack{job['pack_id']}#{job['img_num']}: "
                              f"no image detected after response finished → refresh & requeue")
                        try:
                            driver.get(GEMINI_APP_URL)
                            time.sleep(0.5)
                        except:
                            pass
                        if job.get("retries", 0) < 1:
                            job["retries"] = job.get("retries", 0) + 1
                            job_queue.insert(0, job)
                        else:
                            failed += 1
                        tab_states[tid]["state"] = S_IDLE
                        tab_states[tid]["job"] = None
                        tab_states[tid]["stuck_polls"] = 0
                        continue
                    tab_states[tid]["next_poll"] = now + 2.0
                else:
                    tab_states[tid]["stuck_polls"] = 0
                    tab_states[tid]["next_poll"] = now + 2.5

        has_idle = any(tab_states[tid]["state"] == S_IDLE for tid in range(len(tab_handles)))
        if has_idle and job_queue and not limit_hit:
            time.sleep(0.1)
        else:
            time.sleep(0.5)

    flush_indexes()

    print(f"\n{'='*70}")
    print(f"📊 PIPELINE COMPLETE — PACK-WISE v2")
    print(f"   ✅ Completed: {completed}")
    print(f"   ❌ Failed:    {failed}")
    print(f"   ⏭️ Skipped:   {skipped_pre}")
    if limit_hit:
        remaining = len(job_queue)
        print(f"   🛑 Pro limit reached — {remaining} images remaining")
    final_usage = compute_model_usage_from_filenames()
    print(f"   👤 Final model usage (from filenames): {dict(sorted(final_usage.items()))}")
    print(f"{'='*70}")

    try:
        driver.quit()
    except:
        pass

# ============================================================================
# RUN
# ============================================================================
if __name__ == "__main__":
    main()