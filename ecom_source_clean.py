# @title 🚀 ECOM PHOTOSHOOT ORDER
# ============================================================================
# FOLDER STRUCTURE EXPECTED:
#   /content/drive/MyDrive/Gemini/order/<order_id>/by-combo/<combo_folder>/ref/*.png|webp
#
# Each <combo_folder> = ONE job:
#   ref/    -> 3-7 reference images (face, mannequin, clothing x N) — ALL uploaded
#   image/  -> generated output goes here: <combo_folder>.image.png
#   WR/     -> watermark-removed output goes here: <combo_folder>.WR.png
#
# FLOW PER JOB (Gen phase):
#   navigate Gemini -> switch to Flash -> + -> Create image -> + -> Upload files
#   -> upload ALL ref images -> inject FIXED prompt via clipboard -> send
#   -> poll for generated image -> download -> save to image/
#
# FLOW PER JOB (WR phase, separate pass after all gen done):
#   open logo-remover-fawn.vercel.app/gemini -> upload image/<combo>.image.png
#   -> wait for "Download PNG" button -> click -> save to WR/<combo>.WR.png
#
# Uses 6 parallel Chrome tabs for each phase. noVNC + Cloudflare tunnel for
# live viewing (needed to solve captchas / 2FA manually).
# ============================================================================

import os, re, json, time, shutil, base64, subprocess, pickle, socket, threading
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from queue import Queue as TQueue
from IPython.display import display as ipy_display, HTML

# ============================================================================
# SECTION 1: INSTALL DEPENDENCIES
# ============================================================================
print("=" * 70)
print("🔧 INSTALLING DEPENDENCIES")
print("=" * 70)

os.environ["DEBIAN_FRONTEND"] = "noninteractive"


def run_cmd(cmd, shell=True, timeout=120):
    try:
        return subprocess.run(cmd, shell=shell, capture_output=True, text=True,
                              check=False, timeout=timeout)
    except Exception:
        return None


def _bin_exists(name):
    r = run_cmd(f"which {name}", timeout=5)
    return r is not None and r.returncode == 0 and r.stdout.strip() != ""


run_cmd("apt-get update -y", timeout=60)
run_cmd("apt-get install -y wget xvfb x11vnc novnc websockify unzip zip "
        "xclip xsel curl dbus-x11 python3-numpy", timeout=120)

novnc_web_dir = None
for p in ["/usr/share/novnc", "/usr/share/noVNC", "/opt/novnc", "/opt/noVNC"]:
    if (os.path.isfile(os.path.join(p, "vnc.html")) or
            os.path.isfile(os.path.join(p, "vnc_lite.html"))):
        novnc_web_dir = p
        print(f"✅ noVNC web dir: {p}")
        break

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
    for path in ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome"]:
        if os.path.exists(path):
            chrome_bin = path
            break
if not chrome_bin:
    chrome_bin = "google-chrome"
try:
    print(f"✅ {run_cmd(f'{chrome_bin} --version', timeout=5).stdout.strip()}")
except Exception:
    print("⚠️ Chrome version unknown")

cf_path = "/usr/local/bin/cloudflared"
cf_ok = False
if os.path.exists(cf_path):
    r = run_cmd(f"{cf_path} --version", timeout=5)
    cf_ok = r is not None and r.returncode == 0
if not cf_ok:
    run_cmd(f"wget -q --timeout=20 --tries=1 -O {cf_path} "
            "https://github.com/cloudflare/cloudflared/releases/latest/download/"
            "cloudflared-linux-amd64", timeout=60)
    if os.path.exists(cf_path) and os.path.getsize(cf_path) > 100_000:
        run_cmd(f"chmod +x {cf_path}", timeout=5)
        r = run_cmd(f"{cf_path} --version", timeout=5)
        cf_ok = r is not None and r.returncode == 0
if not cf_ok:
    cf_path = None

run_cmd("pip install -q selenium webdriver-manager pyvirtualdisplay requests",
        timeout=120)
print("✅ Python packages ready")

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from pyvirtualdisplay import Display

try:
    from google.colab import drive
    print("📁 Mounting Drive...")
    drive.mount("/content/drive")
except Exception:
    print("⚠️ Drive already mounted or not in Colab")

print("\n✅ ALL DEPENDENCIES READY\n")

# ============================================================================
# SECTION 2: VIRTUAL DISPLAY + noVNC + CLOUDFLARE TUNNEL  (IMPROVED)
# ----------------------------------------------------------------------------
# Drop-in replacement for the old Section 2. Keeps the same public functions
# (start_display, start_vnc, start_tunnel, setup_novnc_ui) so the rest of the
# pipeline doesn't need to change, but adds:
#
#   • Real verification that each stage actually works (not just "process
#     started") before moving to the next stage
#   • Retry loops with backoff for Xvfb / x11vnc / websockify / cloudflared
#   • A background monitor thread that detects a dead tunnel / dead VNC and
#     auto-restarts it, so a 4-hour run doesn't die because cloudflared
#     silently dropped
#   • stop_novnc_ui() for a clean teardown
#   • novnc_web_dir auto-repair if it wasn't found in Section 1 (installs it
#     on the fly instead of silently falling back to no UI)
#
# Assumes these already exist from Section 1: run_cmd, _bin_exists, cf_path,
# novnc_web_dir, ipy_display, HTML, and `from pyvirtualdisplay import Display`.
# ============================================================================

import os, re, time, socket, subprocess, threading
from IPython.display import display as ipy_display, HTML

try:
    from pyvirtualdisplay import Display
except Exception:
    Display = None

SCREEN_W, SCREEN_H   = 1920, 1080
VNC_PORT, NOVNC_PORT = 5900, 6080

# ---- global process/state handles -----------------------------------------
_display_obj  = None
_x11vnc_proc  = None
_novnc_proc   = None
_cf_proc      = None
_active_display = None   # e.g. ":99"
_active_tunnel_url = None
_monitor_thread = None
_monitor_stop = threading.Event()


# ============================================================================
# LOW-LEVEL HELPERS
# ============================================================================
def _port_open(port, host="127.0.0.1", timeout=1.0):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def _wait_for_port(port, label="service", max_wait=15, interval=0.5):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        if _port_open(port):
            print(f"✅ {label} up on :{port} ({time.time()-t0:.1f}s)")
            return True
        time.sleep(interval)
    print(f"⚠️ {label} did NOT come up on :{port} after {max_wait}s")
    return False


def _kill_port(port):
    run_cmd(f"fuser -k {port}/tcp", timeout=5)
    time.sleep(0.2)


def _proc_alive(p):
    return p is not None and p.poll() is None


def _xdisplay_works(disp):
    """Actually verify the X display responds, not just that a process exists."""
    if _bin_exists("xdpyinfo"):
        r = run_cmd(f"DISPLAY={disp} xdpyinfo", timeout=5)
        return r is not None and r.returncode == 0
    # xdpyinfo not installed — fall back to a softer check via Xvfb pidfile/socket
    sock_path = f"/tmp/.X11-unix/X{disp.lstrip(':')}"
    return os.path.exists(sock_path)


def _ensure_novnc_web_dir():
    """Locate (or install) the noVNC static web assets. Returns a path or None."""
    global novnc_web_dir
    for p in ["/usr/share/novnc", "/usr/share/noVNC", "/opt/novnc", "/opt/noVNC"]:
        if os.path.isfile(os.path.join(p, "vnc.html")) or \
           os.path.isfile(os.path.join(p, "vnc_lite.html")):
            novnc_web_dir = p
            return p
    print("⚠️ noVNC web assets not found — attempting install...")
    run_cmd("apt-get install -y novnc websockify", timeout=90)
    for p in ["/usr/share/novnc", "/usr/share/noVNC"]:
        if os.path.isfile(os.path.join(p, "vnc.html")):
            novnc_web_dir = p
            print(f"✅ noVNC installed at {p}")
            return p
    # last resort: clone from GitHub
    if _bin_exists("git"):
        run_cmd("rm -rf /opt/noVNC", timeout=5)
        run_cmd("git clone --depth 1 https://github.com/novnc/noVNC /opt/noVNC", timeout=60)
        if os.path.isfile("/opt/noVNC/vnc.html"):
            novnc_web_dir = "/opt/noVNC"
            print("✅ noVNC cloned to /opt/noVNC")
            return "/opt/noVNC"
    print("❌ Could not obtain noVNC web assets — will run VNC without web UI")
    novnc_web_dir = None
    return None


# ============================================================================
# STAGE 1: VIRTUAL DISPLAY
# ============================================================================
def start_display(retries=3):
    """Start an X virtual framebuffer and verify it actually accepts connections."""
    global _display_obj, _active_display

    run_cmd("pkill -f Xvfb", timeout=5)
    time.sleep(0.3)

    for attempt in range(1, retries + 1):
        print(f"🖥️  Starting display (attempt {attempt}/{retries})...")

        # Try pyvirtualdisplay first (cleaner lifecycle management)
        if Display is not None:
            try:
                _display_obj = Display(visible=0, size=(SCREEN_W, SCREEN_H))
                _display_obj.start()
                disp_num = getattr(_display_obj, "display", None) or \
                           getattr(_display_obj, "new_display_var", ":99").lstrip(":")
                disp = f":{disp_num}"
                os.environ["DISPLAY"] = disp
                time.sleep(0.5)
                if _xdisplay_works(disp):
                    _active_display = disp
                    print(f"✅ Display {disp} ready (pyvirtualdisplay)")
                    return disp
                print(f"⚠️ Display {disp} started but not responding, retrying...")
            except Exception as e:
                print(f"⚠️ pyvirtualdisplay failed: {str(e)[:80]}")

        # Fallback: raw Xvfb subprocess on a fixed display number
        if _bin_exists("Xvfb"):
            disp = ":99"
            run_cmd("rm -f /tmp/.X99-lock", timeout=3)
            subprocess.Popen(
                ["Xvfb", disp, "-screen", "0", f"{SCREEN_W}x{SCREEN_H}x24", "-ac"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.environ["DISPLAY"] = disp
            time.sleep(1.2)
            if _xdisplay_works(disp):
                _active_display = disp
                print(f"✅ Display {disp} ready (raw Xvfb)")
                return disp
            print(f"⚠️ Xvfb on {disp} not responding, retrying...")

        time.sleep(1.0 * attempt)  # backoff

    print("❌ Could not bring up a working X display after all retries")
    return None


# ============================================================================
# STAGE 2: x11vnc + websockify (noVNC)
# ============================================================================
def start_vnc(retries=2):
    global _x11vnc_proc, _novnc_proc

    disp = os.environ.get("DISPLAY", _active_display or ":99")

    run_cmd("pkill -f x11vnc", timeout=5)
    run_cmd("pkill -f websockify", timeout=5)
    _kill_port(VNC_PORT)
    _kill_port(NOVNC_PORT)
    time.sleep(0.4)

    if not _bin_exists("x11vnc"):
        print("❌ x11vnc not installed — cannot start VNC")
        return False

    for attempt in range(1, retries + 1):
        print(f"📡 Starting x11vnc (attempt {attempt}/{retries})...")
        _x11vnc_proc = subprocess.Popen(
            ["x11vnc", "-display", disp, "-forever", "-nopw", "-shared",
             "-quiet", "-rfbport", str(VNC_PORT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if _wait_for_port(VNC_PORT, "x11vnc", max_wait=10) and _proc_alive(_x11vnc_proc):
            break
        print("⚠️ x11vnc failed to bind, retrying...")
        run_cmd("pkill -f x11vnc", timeout=5)
        time.sleep(1.0)
    else:
        print("❌ x11vnc never came up")
        return False

    web_dir = _ensure_novnc_web_dir()
    if not _bin_exists("websockify"):
        print("❌ websockify not installed — VNC has no web UI")
        return False

    for attempt in range(1, retries + 1):
        print(f"🌉 Starting websockify (attempt {attempt}/{retries})...")
        cmd = (["websockify", "--web", web_dir, str(NOVNC_PORT), f"localhost:{VNC_PORT}"]
               if web_dir else ["websockify", str(NOVNC_PORT), f"localhost:{VNC_PORT}"])
        _novnc_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if _wait_for_port(NOVNC_PORT, "noVNC", max_wait=10) and _proc_alive(_novnc_proc):
            return True
        print("⚠️ websockify failed to bind, retrying...")
        run_cmd("pkill -f websockify", timeout=5)
        time.sleep(1.0)

    print("❌ websockify never came up")
    return False


# ============================================================================
# STAGE 3: CLOUDFLARE TUNNEL
# ============================================================================
def start_tunnel(retries=3):
    global _cf_proc, _active_tunnel_url

    local_url = f"http://localhost:{NOVNC_PORT}"
    if not _port_open(NOVNC_PORT):
        time.sleep(4)
        if not _port_open(NOVNC_PORT):
            ipy_display(HTML(
                "<div style='background:#ea4335;color:white;padding:12px;"
                "border-radius:8px;'>❌ noVNC not listening — cannot open tunnel.</div>"))
            return local_url

    if not (cf_path and os.path.exists(cf_path)):
        fallback = f"{local_url}/vnc.html"
        ipy_display(HTML(
            f"<div style='background:#fbbc04;color:#333;padding:12px;"
            f"border-radius:8px;'>⚠️ cloudflared not available. Local only: "
            f"<b>{fallback}</b></div>"))
        return fallback

    for attempt in range(1, retries + 1):
        print(f"🌐 Starting Cloudflare tunnel (attempt {attempt}/{retries})...")
        run_cmd("pkill -f cloudflared", timeout=5)
        time.sleep(0.4)
        try:
            _cf_proc = subprocess.Popen(
                [cf_path, "tunnel", "--url", local_url],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except Exception as e:
            print(f"⚠️ cloudflared failed to launch: {e}")
            continue

        deadline = time.time() + 30
        while time.time() < deadline:
            if not _proc_alive(_cf_proc):
                print("⚠️ cloudflared process died before producing a URL")
                break
            line = _cf_proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
            m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if m:
                base = m.group(0)
                vnc_url = f"{base}/vnc.html?autoconnect=true&resize=scale"
                _active_tunnel_url = base
                ipy_display(HTML(f"""
<div style='background:linear-gradient(135deg,#34a853,#0d652d);color:white;
padding:16px;border-radius:10px;font-size:15px;font-weight:bold;margin:10px 0;'>
🌐 noVNC Remote Desktop:<br>
<a href='{vnc_url}' target='_blank' style='color:#a8e6cf;font-size:16px;'>{vnc_url}</a><br>
<span style='font-size:12px;opacity:0.85;'>← Click to open in new tab</span>
</div>"""))
                return base
        print("⚠️ Tunnel attempt timed out without a URL, retrying...")

    fallback = f"{local_url}/vnc.html"
    ipy_display(HTML(
        f"<div style='background:#fbbc04;color:#333;padding:12px;"
        f"border-radius:8px;'>⚠️ Tunnel failed after {retries} attempts. "
        f"Local only: <b>{fallback}</b></div>"))
    return fallback


# ============================================================================
# AUTO-HEAL MONITOR (background thread)
# ============================================================================
def _monitor_loop(check_interval=20):
    """Runs in the background for the life of the notebook session. If x11vnc,
    websockify, or the cloudflared tunnel dies, this brings it back up so a
    multi-hour run doesn't silently lose the VNC view."""
    while not _monitor_stop.is_set():
        time.sleep(check_interval)
        try:
            if not _port_open(VNC_PORT) or not _proc_alive(_x11vnc_proc):
                print("🔧 [monitor] x11vnc down — restarting VNC stack...")
                start_vnc(retries=2)
                start_tunnel(retries=2)
                continue

            if not _port_open(NOVNC_PORT) or not _proc_alive(_novnc_proc):
                print("🔧 [monitor] websockify down — restarting VNC stack...")
                start_vnc(retries=2)
                start_tunnel(retries=2)
                continue

            if cf_path and (_cf_proc is None or not _proc_alive(_cf_proc)):
                print("🔧 [monitor] cloudflared tunnel down — restarting tunnel...")
                start_tunnel(retries=2)
        except Exception as e:
            print(f"⚠️ [monitor] error: {str(e)[:80]}")


def start_monitor(check_interval=20):
    global _monitor_thread
    _monitor_stop.clear()
    _monitor_thread = threading.Thread(
        target=_monitor_loop, args=(check_interval,), daemon=True)
    _monitor_thread.start()
    print(f"🩺 Auto-heal monitor started (checks every {check_interval}s)")


def stop_monitor():
    _monitor_stop.set()


# ============================================================================
# TEARDOWN
# ============================================================================
def stop_novnc_ui():
    stop_monitor()
    for p in (_cf_proc, _novnc_proc, _x11vnc_proc):
        try:
            if p and _proc_alive(p):
                p.terminate()
        except Exception:
            pass
    run_cmd("pkill -f cloudflared", timeout=5)
    run_cmd("pkill -f websockify", timeout=5)
    run_cmd("pkill -f x11vnc", timeout=5)
    global _display_obj
    if _display_obj is not None:
        try:
            _display_obj.stop()
        except Exception:
            pass
    run_cmd("pkill -f Xvfb", timeout=5)
    print("🧹 noVNC stack stopped")


# ============================================================================
# ORCHESTRATOR
# ============================================================================
def setup_novnc_ui(auto_heal=True, monitor_interval=20):
    """Full bring-up: display -> vnc -> tunnel -> (optional) auto-heal monitor.
    Returns the tunnel/VNC URL, or the best fallback URL available."""
    disp = start_display()
    if not disp:
        ipy_display(HTML(
            "<div style='background:#ea4335;color:white;padding:12px;"
            "border-radius:8px;'>❌ Could not start virtual display. "
            "Aborting noVNC setup.</div>"))
        return None

    if not start_vnc():
        ipy_display(HTML(
            "<div style='background:#ea4335;color:white;padding:12px;"
            "border-radius:8px;'>❌ Could not start x11vnc/websockify.</div>"))
        return None

    url = start_tunnel()

    if auto_heal:
        start_monitor(check_interval=monitor_interval)

    return url

# ============================================================================
# SECTION 3: CONFIGURATION
# ============================================================================
BASE_ORDER      = "/content/drive/MyDrive/Gemini/order"
CHROME_DL_BASE  = "/content/downloads"
LOCAL_COPY_BASE = "/content/image_copies"
ERR_SS_DIR      = "/content/error_screenshots"
COOKIES_FILE    = "/content/drive/MyDrive/google_cookies.pkl"
GEMINI_APP_URL  = "https://gemini.google.com/app"
WMR_URL         = "https://logo-remover-fawn.vercel.app/gemini"
WMR_DL_DIR      = "/content/wmr_downloads"

for d in [CHROME_DL_BASE, LOCAL_COPY_BASE, ERR_SS_DIR, WMR_DL_DIR]:
    os.makedirs(d, exist_ok=True)

TIMEOUT           = 15
MAX_RETRY_ROUNDS  = 5
GEN_TIMEOUT       = 400
DOWNLOAD_TIMEOUT  = 60
WMR_UPLOAD_WAIT   = 90
WMR_PROCESS_WAIT  = 600
IMG_EXTS          = (".jpg", ".jpeg", ".png", ".webp")
TOTAL_TABS        = 6
MAX_REFS_PER_JOB  = 7          # upload ALL refs found, capped at 7

GEN_SUCCESS   = "SUCCESS"
GEN_REFUSED   = "REFUSED"
GEN_TIMEOUT_S = "TIMEOUT"
GEN_LIMIT     = "LIMIT"
GEN_ERROR     = "ERROR"

S_IDLE     = "IDLE"
S_GEN_WAIT = "GW"

CAPTCHA_SIGNALS = [
    "select all squares", "select all images", "i'm not a robot",
    "verify you are human", "recaptcha", "type the characters"
]
SORRY_URL_SIGNALS = ["google.com/sorry", "recaptcha"]
SOMETHING_WRONG_SIGNALS = [
    "something went wrong", "error occurred", "try again later"
]
IMAGE_LIMIT_PHRASES = [
    "you've reached your image-generation limit",
    "reached your image-generation limit",
    "can't generate more images for you today",
    "upgrade to gemini advanced",
    "you've reached your limit",
    "reached your daily limit",
    "rate limit",
]
TEXT_REFUSAL_PHRASES = [
    "can't create images of minors",
    "i'm not able to create that image",
    "i can't create this image",
    "sorry, i can't create",
]
GEMINI_ERROR_SIGNALS = [
    "i encountered an error",
    "something went wrong. try again",
    "an error occurred. please try again",
]

# ── FIXED PROMPT — sent identically for every job ──────────────────────────
PROMPT_TEXT = """
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


def tab_dl_dir(tid):
    d = os.path.join(CHROME_DL_BASE, f"tab_{tid}")
    os.makedirs(d, exist_ok=True)
    return d


def tab_local_dir(tid):
    d = os.path.join(LOCAL_COPY_BASE, f"tab_{tid}")
    os.makedirs(d, exist_ok=True)
    return d

# ============================================================================
# SECTION 4: UTILITY HELPERS
# ============================================================================
def get_user_input(p):
    return input(p).strip()


def save_cookies(drv):
    try:
        with open(COOKIES_FILE, "wb") as f:
            pickle.dump(drv.get_cookies(), f)
        print("💾 Cookies saved")
    except Exception:
        pass


def load_cookies(drv):
    try:
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, "rb") as f:
                cookies = pickle.load(f)
            drv.get("https://www.google.com")
            time.sleep(0.5)
            for c in cookies:
                try:
                    drv.add_cookie(c)
                except Exception:
                    pass
            print("💾 Cookies loaded")
            return True
    except Exception:
        pass
    return False


def quick_check_logged_in(drv):
    try:
        url = drv.current_url
        if "myaccount.google.com" in url and "signin" not in url:
            return True
        drv.find_element(By.XPATH, "//a[@aria-label='Google Account']")
        return True
    except Exception:
        return False


def copy_local(src, max_attempts=3, dest_dir=None):
    if dest_dir is None:
        dest_dir = LOCAL_COPY_BASE
    os.makedirs(dest_dir, exist_ok=True)
    safe = re.sub(r"[^\w.\-]", "_", os.path.basename(src))
    dst  = os.path.join(dest_dir, re.sub(r"_+", "_", safe))
    for _ in range(max_attempts):
        try:
            if not os.path.exists(src):
                return None
            shutil.copy2(src, dst)
            if os.path.exists(dst) and os.path.getsize(dst) > 0:
                return dst
        except Exception:
            time.sleep(0.3)
    return None


def clean_tab_downloads(tid):
    dl = tab_dl_dir(tid)
    try:
        for f in os.listdir(dl):
            try:
                os.remove(os.path.join(dl, f))
            except Exception:
                pass
    except Exception:
        pass

# ============================================================================
# SECTION 5: REF IMAGE COLLECTION (ALL images in ref/, capped at 7)
# ============================================================================
def collect_all_refs(ref_dir, label, verbose=True):
    if not os.path.isdir(ref_dir):
        if verbose: print(f"   ⚠️ {label}: ref dir not found: {ref_dir}")
        return []
    all_files = sorted(os.listdir(ref_dir))
    refs = [os.path.join(ref_dir, f)
            for f in all_files if f.lower().endswith(IMG_EXTS)]
    if not refs:
        if verbose: print(f"   ⚠️ {label}: NO refs found in {ref_dir}")
        return []
    if len(refs) > MAX_REFS_PER_JOB:
        dropped = [os.path.basename(r) for r in refs[MAX_REFS_PER_JOB:]]
        if verbose: print(f"   ⚠️ {label}: {len(refs)} refs, capping to {MAX_REFS_PER_JOB}. "
              f"Dropped: {dropped}")
        refs = refs[:MAX_REFS_PER_JOB]
    if verbose: print(f"   📎 {label}: {len(refs)} ref(s): "
          f"{[os.path.basename(r) for r in refs]}")
    return refs

# ============================================================================
# SECTION 6: CAPTCHA + ERROR DETECTION
# ============================================================================
def check_captcha(drv):
    try:
        url = drv.current_url.lower()
        if any(sig in url for sig in SORRY_URL_SIGNALS):
            return True
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        if any(sig in body for sig in CAPTCHA_SIGNALS):
            return True
        for iframe in drv.find_elements(By.TAG_NAME, "iframe"):
            src = (iframe.get_attribute("src") or "").lower()
            if "recaptcha" in src:
                return True
    except Exception:
        pass
    return False


def check_something_wrong(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for sig in SOMETHING_WRONG_SIGNALS:
            if sig in body:
                return sig
    except Exception:
        pass
    return None


def check_gemini_error(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for sig in GEMINI_ERROR_SIGNALS:
            if sig in body:
                return sig
    except Exception:
        pass
    return None


def check_pro_limit(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for phrase in IMAGE_LIMIT_PHRASES:
            if phrase in body:
                return True
    except Exception:
        pass
    return False


def check_text_error(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for p in TEXT_REFUSAL_PHRASES:
            if p in body:
                return "refusal"
        for p in IMAGE_LIMIT_PHRASES:
            if p in body:
                return "limit"
    except Exception:
        pass
    return None


def recover_from_error(drv):
    try:
        drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.2)
        drv.get(GEMINI_APP_URL)
        time.sleep(1.5)
        return True
    except Exception:
        return False


def do_captcha_pause(drv, tabs, tl_fn):
    captcha_tabs = []
    for t in tabs:
        try:
            drv.switch_to.window(t["handle"])
            if check_captcha(drv):
                captcha_tabs.append(t)
        except Exception:
            pass
    if not captcha_tabs:
        return False
    labels = [tl_fn(t) for t in captcha_tabs]
    ipy_display(HTML(f"""<div style='background:#ea4335;padding:20px;border-radius:10px;
color:white;font-family:monospace;font-size:16px;font-weight:bold;'>
🤖 CAPTCHA DETECTED on tabs: {', '.join(labels)}<br>
<span style='font-size:13px;font-weight:normal;'>Solve in VNC then type <b>resume</b></span>
</div>"""))
    while True:
        try:
            ans = input("Type 'resume': ").strip().lower()
        except EOFError:
            ans = "resume"
        if ans == "resume":
            break
    for t in captcha_tabs:
        try:
            drv.switch_to.window(t["handle"])
            if check_captcha(drv):
                drv.get(GEMINI_APP_URL)
                time.sleep(2)
        except Exception:
            pass
        t["job"]   = None
        t["state"] = S_IDLE
    ipy_display(HTML(
        "<div style='background:#34a853;color:white;padding:10px;"
        "border-radius:8px;'>✅ Resuming</div>"))
    return True

# ============================================================================
# SECTION 7: SELENIUM UI HELPERS (+  → Create image → + → Upload files)
# ============================================================================
def grant_clipboard(drv):
    try:
        drv.execute_cdp_cmd("Browser.grantPermissions", {
            "origin": "https://gemini.google.com",
            "permissions": ["clipboardReadWrite", "clipboardSanitizedWrite"],
        })
    except Exception:
        pass


def close_dialogs(drv):
    for sel in ["//button[@aria-label='Close']", "//button[@aria-label='Dismiss']"]:
        try:
            btn = drv.find_element(By.XPATH, sel)
            if btn.is_displayed():
                drv.execute_script("arguments[0].click();", btn)
        except Exception:
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
            except Exception:
                continue
    except Exception:
        pass
    return False


def set_tab_download_dir(drv, path):
    ap = os.path.abspath(path)
    os.makedirs(ap, exist_ok=True)
    try:
        drv.execute_cdp_cmd("Page.setDownloadBehavior",
                            {"behavior": "allow", "downloadPath": ap})
    except Exception:
        try:
            drv.execute_cdp_cmd("Browser.setDownloadBehavior",
                                {"behavior": "allow", "downloadPath": ap,
                                 "eventsEnabled": False})
        except Exception:
            pass


def snapshot_urls(drv):
    try:
        return set(drv.execute_script(
            "return Array.from(document.querySelectorAll("
            "  'img[src^=\"blob:\"],img[src*=\"googleusercontent\"]'))"
            ".map(i=>i.src).filter(s=>s&&s.length>10);") or [])
    except Exception:
        return set()


def _response_done(drv):
    try:
        for sel in ["button[aria-label='Good response']",
                    "button[aria-label='Bad response']",
                    ".message-actions button"]:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return True
    except Exception:
        pass
    return False


def _send_btn_enabled(drv):
    try:
        return drv.execute_script("""
            var sels=['mat-icon[fonticon="send"]',
                      'mat-icon[data-mat-icon-name="send"]',
                      'mat-icon[fonticon="arrow_upward"]',
                      'mat-icon[data-mat-icon-name="arrow_upward"]',
                      'button[aria-label="Send message"]'];
            for(var s=0;s<sels.length;s++){
                var els=document.querySelectorAll(sels[s]);
                for(var i=0;i<els.length;i++){
                    var b=els[i].tagName==='BUTTON'?els[i]:els[i].closest('button');
                    if(b&&!b.disabled&&b.offsetParent!==null)return true;
                }
            } return false;""")
    except Exception:
        return False


def _click_plus_button(drv):
    selectors = [
        'button[aria-label="Upload and tools"]',
        'button[aria-haspopup="menu"][aria-label*="Upload"]',
        'button[jslog*="300142"]',
    ]
    for sel in selectors:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue
    try:
        result = drv.execute_script(
            "var btns=document.querySelectorAll('button');"
            "for(var i=0;i<btns.length;i++){"
            "  var b=btns[i];"
            "  if(b.offsetParent!==null){"
            "    var lbl=(b.getAttribute('aria-label')||'').toLowerCase();"
            "    if(lbl.indexOf('upload')!==-1||lbl.indexOf('tools')!==-1){"
            "      b.click();return 'OK';"
            "    }"
            "    var icon=b.querySelector('mat-icon[fonticon=\"plus\"],"
            "mat-icon[data-mat-icon-name=\"plus\"]');"
            "    if(icon){b.click();return 'OK';}"
            "  }"
            "} return 'NO';"
        )
        if result == "OK":
            time.sleep(0.4)
            return True
    except Exception:
        pass
    return False


def _click_create_image_in_drawer(drv):
    try:
        btns = drv.find_elements(
            By.CSS_SELECTOR,
            "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button")
        for btn in btns:
            if btn.is_displayed() and "Create image" in btn.text:
                drv.execute_script("arguments[0].click();", btn)
                time.sleep(0.35)
                print("✅CreateImg", end=" | ")
                return True
    except Exception:
        pass

    try:
        icons = drv.find_elements(
            By.CSS_SELECTOR,
            "mat-icon[data-mat-icon-name='image_create'],"
            "mat-icon[fonticon='image_create']")
        for icon in icons:
            if not icon.is_displayed():
                continue
            btn = drv.execute_script(
                "var e=arguments[0];"
                "while(e&&e.tagName!=='BUTTON') e=e.parentElement;"
                "return e;", icon)
            if btn and btn.is_displayed():
                drv.execute_script("arguments[0].click();", btn)
                time.sleep(0.35)
                print("✅CreateImg(icon)", end=" | ")
                return True
    except Exception:
        pass

    try:
        for xpath in [
            "//div[normalize-space(text())='Create image']/ancestor::button",
            "//div[contains(@class,'label') and "
            "contains(text(),'Create image')]/ancestor::button",
        ]:
            for btn in drv.find_elements(By.XPATH, xpath):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.35)
                    print("✅CreateImg(text)", end=" | ")
                    return True
    except Exception:
        pass

    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[jslog*='271906']"):
            if btn.is_displayed():
                drv.execute_script("arguments[0].click();", btn)
                time.sleep(0.35)
                print("✅CreateImg(jslog)", end=" | ")
                return True
    except Exception:
        pass

    try:
        drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass
    return False


def _wait_for_image_mode(drv, timeout=4.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            ta = drv.find_elements(
                By.CSS_SELECTOR,
                "div.ql-editor[data-placeholder='Describe your image']")
            if ta:
                return True
            for c in drv.find_elements(By.CSS_SELECTOR,
                                        "button[aria-label='Deselect Images'],"
                                        "span.gds-body-s"):
                if c.is_displayed() and "Images" in c.text:
                    return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def activate_create_image_mode(drv):
    try:
        ta = drv.find_elements(
            By.CSS_SELECTOR,
            "div.ql-editor[data-placeholder='Describe your image']")
        if ta:
            print("✅ImgMode(already)", end=" | ")
            return True
    except Exception:
        pass

    if not _click_plus_button(drv):
        print("⚠️NoPlusBtn", end=" | ")
        return False

    if not _click_create_image_in_drawer(drv):
        print("⚠️NoCreateImgBtn", end=" | ")
        try:
            drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
        return False

    active = _wait_for_image_mode(drv, timeout=4.0)
    print("✅ImgMode(confirmed)" if active else "⚠️ImgMode(unconfirmed)", end=" | ")
    return True


def _click_upload_files_in_drawer(drv):
    selectors = [
        "button[data-test-id='local-images-files-uploader-button']",
        "//span[contains(text(),'Upload files')]/ancestor::button",
        "//div[contains(text(),'Upload files')]/ancestor::button",
    ]
    for sel in selectors:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            for btn in drv.find_elements(by, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    print("📁UploadFiles", end=" | ")
                    return True
        except Exception:
            continue

    try:
        result = drv.execute_script(
            "var btns=document.querySelectorAll('button');"
            "for(var i=0;i<btns.length;i++){"
            "  if(btns[i].offsetParent!==null&&"
            "     btns[i].textContent.toLowerCase().indexOf('upload files')!==-1){"
            "    btns[i].click();return 'OK';"
            "  }"
            "} return 'NO';"
        )
        if result == "OK":
            time.sleep(0.3)
            print("📁UploadFiles(JS)", end=" | ")
            return True
    except Exception:
        pass
    return False


def _find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs:
        return inputs[0]
    try:
        drv.execute_script(
            "document.querySelectorAll('input[type=\"file\"]').forEach("
            "function(el){"
            "  el.style.cssText='display:block!important;opacity:1!important;"
            "position:fixed!important;top:0;left:0;z-index:99999;"
            "width:200px;height:50px;';"
            "});"
        )
    except Exception:
        pass
    time.sleep(0.1)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None


def _wait_for_attachment_chip(drv, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            els = drv.find_elements(
                By.CSS_SELECTOR, 'button[aria-label="close attachment"]')
            for el in els:
                if el.is_displayed():
                    return True
            chips = drv.find_elements(
                By.CSS_SELECTOR, "gem-media-attachment,uploader-file-preview")
            for chip in chips:
                if chip.is_displayed():
                    return True
            wrappers = drv.find_elements(
                By.CSS_SELECTOR,
                ".attachment-preview-wrapper,uploader-file-preview-container")
            for w in wrappers:
                if w.is_displayed():
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def _jsdrop_multi(drv, image_paths):
    try:
        files_js = []
        for abs_path in image_paths:
            if os.path.getsize(abs_path) > 10_000_000:
                continue
            with open(abs_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("ascii")
            ext  = os.path.splitext(abs_path)[1].lower()
            mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png",  ".webp": "image/webp"}.get(
                ext, "image/jpeg")
            files_js.append({
                "b64": b64_data, "mime": mime,
                "name": os.path.basename(abs_path)
            })
        if not files_js:
            return False
        result = drv.execute_script("""
            var filesData=arguments[0];var dt=new DataTransfer();
            for(var f=0;f<filesData.length;f++){
                var binary=atob(filesData[f].b64);
                var arr=new Uint8Array(binary.length);
                for(var i=0;i<binary.length;i++) arr[i]=binary.charCodeAt(i);
                var blob=new Blob([arr],{type:filesData[f].mime});
                var file=new File([blob],filesData[f].name,
                    {type:filesData[f].mime,lastModified:Date.now()});
                dt.items.add(file);
            }
            var sels=['rich-textarea','.ql-editor',
                      'div[contenteditable="true"]','.input-area-container'];
            for(var s=0;s<sels.length;s++){
                var targets=document.querySelectorAll(sels[s]);
                for(var t=0;t<targets.length;t++){
                    var el=targets[t];if(el.offsetParent===null) continue;
                    el.dispatchEvent(new DragEvent('dragenter',
                        {dataTransfer:dt,bubbles:true}));
                    el.dispatchEvent(new DragEvent('dragover',
                        {dataTransfer:dt,bubbles:true}));
                    el.dispatchEvent(new DragEvent('drop',
                        {dataTransfer:dt,bubbles:true,cancelable:true}));
                    return 'OK';
                }
            } return 'NO';
        """, files_js)
        time.sleep(0.3)
        handle_consent(drv)
        return result == "OK"
    except Exception:
        return False


def _jsdrop_single(drv, image_path):
    try:
        abs_path = os.path.abspath(image_path)
        if os.path.getsize(abs_path) > 10_000_000:
            return False
        with open(abs_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("ascii")
        ext  = os.path.splitext(abs_path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png",  ".webp": "image/webp"}.get(ext, "image/jpeg")
        fname = os.path.basename(abs_path)
        result = drv.execute_script("""
            var b64=arguments[0],mime=arguments[1],fname=arguments[2];
            var binary=atob(b64);var arr=new Uint8Array(binary.length);
            for(var i=0;i<binary.length;i++) arr[i]=binary.charCodeAt(i);
            var blob=new Blob([arr],{type:mime});
            var file=new File([blob],fname,{type:mime,lastModified:Date.now()});
            var dt=new DataTransfer();dt.items.add(file);
            var sels=['rich-textarea','.ql-editor',
                      'div[contenteditable="true"]','.input-area-container'];
            for(var s=0;s<sels.length;s++){
                var targets=document.querySelectorAll(sels[s]);
                for(var t=0;t<targets.length;t++){
                    var el=targets[t];if(el.offsetParent===null) continue;
                    el.dispatchEvent(new DragEvent('dragenter',
                        {dataTransfer:dt,bubbles:true}));
                    el.dispatchEvent(new DragEvent('dragover',
                        {dataTransfer:dt,bubbles:true}));
                    el.dispatchEvent(new DragEvent('drop',
                        {dataTransfer:dt,bubbles:true,cancelable:true}));
                    return 'OK';
                }
            } return 'NO';
        """, b64_data, mime, fname)
        time.sleep(0.3)
        handle_consent(drv)
        return result == "OK"
    except Exception:
        return False


def _upload_refs_in_image_mode(drv, ref_paths):
    """Upload ALL ref images (no cap to 3) while already in Create Image mode."""
    valid = [os.path.abspath(p) for p in ref_paths
             if os.path.exists(os.path.abspath(p))]
    if not valid:
        print("❌NoValidRefs", end=" | ")
        return False

    if not _click_plus_button(drv):
        print("⚠️NoPlusBtn(upload)", end=" | ")
        return False

    if not _click_upload_files_in_drawer(drv):
        try:
            drv.execute_script(
                "var b=document.querySelector("
                "  'button.hidden-local-file-image-selector-button,"
                "   button[data-test-id=\"hidden-local-image-upload-button\"],"
                "   button[xapfileselectortrigger]');"
                "if(b) b.click();"
            )
            time.sleep(0.15)
        except Exception:
            pass

    fi = _find_file_input(drv)
    if fi:
        try:
            fi.send_keys("\n".join(valid))
            print(f"📎FileInput({len(valid)})", end=" | ")
            return True
        except Exception as e:
            print(f"⚠️FileInputErr:{str(e)[:20]}", end=" | ")

    ok = _jsdrop_multi(drv, valid)
    if ok:
        print(f"✅JSDrop({len(valid)})", end=" | ")
        return True

    for i, rp in enumerate(valid):
        _click_plus_button(drv)
        time.sleep(0.2)
        _click_upload_files_in_drawer(drv)
        time.sleep(0.2)
        fi2 = _find_file_input(drv)
        if fi2:
            fi2.send_keys(rp)
        else:
            _jsdrop_single(drv, rp)
        time.sleep(0.35)
        handle_consent(drv)
    print(f"✅Fallback1by1({len(valid)})", end=" | ")
    return True

# ============================================================================
# SECTION 8: CLIPBOARD-BASED PROMPT INJECTION
# ============================================================================
def _get_quill_editor(drv):
    priority_selectors = [
        "div.ql-editor[data-placeholder='Describe your image']",
        "div.ql-editor[contenteditable='true']",
        "rich-textarea div[contenteditable='true']",
    ]
    for sel in priority_selectors:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return el
        except Exception:
            pass
    try:
        for el in drv.find_elements(
                By.CSS_SELECTOR, "div[contenteditable='true']"):
            if el.is_displayed():
                return el
    except Exception:
        pass
    return None


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
    except Exception:
        return False


def _set_clipboard_js(drv, text):
    try:
        result = drv.execute_async_script(
            "var text=arguments[0],done=arguments[1];"
            "navigator.clipboard.writeText(text)"
            "  .then(function(){done('OK');})"
            "  .catch(function(e){done('ERR:'+e.toString());});",
            text)
        return result == "OK"
    except Exception:
        return False


def _verify_editor_content(drv, editor, expected_text, timeout=5.0):
    min_len = max(10, int(len(expected_text) * 0.90))
    first40 = expected_text[:40].strip()
    last40  = expected_text[-40:].strip()
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            content = (editor.text or "").strip()
            if not content:
                content = drv.execute_script(
                    "return (arguments[0].textContent||'').trim();", editor) or ""
            if (len(content) >= min_len
                    and first40 in content
                    and last40 in content):
                return True
            if (len(content) >= int(len(expected_text) * 0.80)
                    and first40 in content):
                print(f"⚠️Partial({len(content)}/{len(expected_text)})",
                      end=" | ")
                return True
        except Exception:
            pass
        time.sleep(0.1)

    try:
        content = drv.execute_script(
            "return (arguments[0].textContent||'').trim();", editor) or ""
        if len(content) >= min_len:
            return True
    except Exception:
        pass
    return False


def _clear_editor(drv, editor):
    try:
        drv.execute_script("arguments[0].focus();", editor)
        ActionChains(drv).click(editor) \
            .key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL) \
            .perform()
        time.sleep(0.05)
        editor.send_keys(Keys.DELETE)
        time.sleep(0.05)
    except Exception:
        pass


def _inject_prompt_via_clipboard(drv, text, max_attempts=3):
    editor = _get_quill_editor(drv)
    if not editor:
        print("⚠️NoEditor", end=" | ")
        return False

    try:
        drv.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", editor)
        time.sleep(0.1)
        drv.execute_script("arguments[0].focus();", editor)
        time.sleep(0.1)
        _clear_editor(drv, editor)
    except Exception as e:
        print(f"⚠️ClearErr:{str(e)[:20]}", end=" | ")

    for attempt in range(max_attempts):
        clip_ok = _set_clipboard_xclip(text)
        if not clip_ok:
            grant_clipboard(drv)
            clip_ok = _set_clipboard_js(drv, text)

        if clip_ok:
            try:
                drv.execute_script("arguments[0].focus();", editor)
                time.sleep(0.1)
                ActionChains(drv).click(editor) \
                    .key_down(Keys.CONTROL).send_keys("v") \
                    .key_up(Keys.CONTROL).perform()
                time.sleep(0.3)

                if _verify_editor_content(drv, editor, text, timeout=4.0):
                    print("✏️Paste✅", end=" | ")
                    return True
                else:
                    print(f"⚠️PasteVerify(a{attempt+1})", end=" | ")
                    _clear_editor(drv, editor)
            except Exception as e:
                print(f"⚠️PasteErr:{str(e)[:20]}", end=" | ")
        else:
            print(f"⚠️ClipFail(a{attempt+1})", end=" | ")

    print("↩️ExecCmd", end=" | ")
    try:
        editor = _get_quill_editor(drv)
        if editor:
            drv.execute_script("arguments[0].focus();", editor)
            time.sleep(0.1)
            drv.execute_script(
                "document.execCommand('selectAll',false,null);"
                "document.execCommand('delete',false,null);"
                "document.execCommand('insertText',false,arguments[0]);",
                text)
            time.sleep(0.3)
            if _verify_editor_content(drv, editor, text, timeout=4.0):
                print("✏️ExecCmd✅", end=" | ")
                return True
    except Exception as e:
        print(f"⚠️ExecCmdErr:{str(e)[:20]}", end=" | ")

    print("↩️SendKeys", end=" | ")
    try:
        editor = _get_quill_editor(drv)
        if editor:
            drv.execute_script("arguments[0].focus();", editor)
            time.sleep(0.1)
            _clear_editor(drv, editor)
            chunk = 500
            for i in range(0, len(text), chunk):
                editor.send_keys(text[i:i + chunk])
                time.sleep(0.03)
            time.sleep(0.3)
            if _verify_editor_content(drv, editor, text, timeout=6.0):
                print("✏️SendKeys✅", end=" | ")
                return True
    except Exception as e:
        print(f"⚠️SendKeysErr:{str(e)[:20]}", end=" | ")

    print("❌AllInjectFailed", end=" | ")
    return False

# ============================================================================
# SECTION 9: SEND BUTTON
# ============================================================================
def _click_send_button(drv):
    try:
        result = drv.execute_script(
            "var icons=document.querySelectorAll("
            "  'mat-icon[fonticon=\"arrow_upward\"],"
            "   mat-icon[data-mat-icon-name=\"arrow_upward\"]');"
            "for(var i=0;i<icons.length;i++){"
            "  var b=icons[i].closest('button');"
            "  if(b&&!b.disabled&&b.offsetParent!==null){b.click();return 'OK_UP';}"
            "}"
            "var sendIcons=document.querySelectorAll("
            "  'mat-icon[fonticon=\"send\"],"
            "   mat-icon[data-mat-icon-name=\"send\"]');"
            "for(var i=0;i<sendIcons.length;i++){"
            "  var b=sendIcons[i].closest('button');"
            "  if(b&&!b.disabled&&b.offsetParent!==null){b.click();return 'OK_SEND';}"
            "}"
            "var btns=document.querySelectorAll("
            "  'button[aria-label=\"Send message\"],"
            "   button[data-test-id=\"send-button\"]');"
            "for(var i=0;i<btns.length;i++){"
            "  if(!btns[i].disabled&&btns[i].offsetParent!==null){"
            "    btns[i].click();return 'OK_ARIA';"
            "  }"
            "} return 'NO';"
        )
        if result and result.startswith("OK"):
            return True
    except Exception:
        pass

    for sel in [
        "button[aria-label='Send message']",
        "button[data-test-id='send-button']",
        "button[aria-label*='Send']",
    ]:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].click();", btn)
                    return True
        except Exception:
            continue

    for xpath in [
        "//mat-icon[@fonticon='arrow_upward']/ancestor::button",
        "//mat-icon[@data-mat-icon-name='arrow_upward']/ancestor::button",
        "//mat-icon[@fonticon='send']/ancestor::button",
        "//button[@aria-label='Send message']",
    ]:
        try:
            for btn in drv.find_elements(By.XPATH, xpath):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].click();", btn)
                    return True
        except Exception:
            continue

    return False

# ============================================================================
# SECTION 10: MODEL PICKER — FLASH MODE (not Pro)
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
        except Exception:
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
    except Exception:
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
    except Exception:
        pass

    try:
        el = drv.find_element(
            By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container']")
        if el and el.is_displayed():
            drv.execute_script("arguments[0].click();", el)
            time.sleep(0.45)
            print("🔽Picker(div)", end=" | ")
            return True
    except Exception:
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
    except Exception:
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
    except Exception:
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
    except Exception:
        pass

    print("⚠️NoPicker", end=" | ")
    return False


def _wait_for_picker_open(drv, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            items = drv.find_elements(
                By.CSS_SELECTOR,
                "mat-option, [role='option'], [role='menuitem'], "
                "[role='menuitemradio'], button[data-test-id*='bard-mode-option']"
            )
            for item in items:
                if item.is_displayed():
                    return True
            overlays = drv.find_elements(
                By.CSS_SELECTOR,
                ".mat-mdc-select-panel,.cdk-overlay-pane,"
                "mat-select-panel,[role='listbox']"
            )
            for ov in overlays:
                if ov.is_displayed() and ("pro" in ov.text.lower()
                                          or "flash" in ov.text.lower()):
                    return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def _click_flash_in_picker(drv):
    """
    Click the plain 'Flash' option (NOT 'Flash-Lite', NOT 'Pro').
    Raises ModelLimitReached if the option is disabled.
    """
    def _is_flash_option(txt):
        t = (txt or "").strip().lower()
        return "flash" in t and "lite" not in t

    def _is_disabled(el):
        try:
            if el.get_attribute("disabled"):
                return True
            if el.get_attribute("aria-disabled") == "true":
                return True
            cls = (el.get_attribute("class") or "").lower()
            if "disabled" in cls:
                return True
        except Exception:
            pass
        return False

    for tid in ["bard-mode-option-flash", "mode-option-flash", "flash-option"]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, f"[data-test-id='{tid}']"):
                if el.is_displayed() and _is_flash_option(el.text):
                    if _is_disabled(el):
                        raise ModelLimitReached(f"Flash disabled ({tid})")
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    print("✅Flash(tid)", end=" | ")
                    return True
        except ModelLimitReached:
            raise
        except Exception:
            continue

    for sel in [
        "mat-option", "[role='option']", "[role='menuitem']",
        "[role='menuitemradio']", "button[class*='mode-option']",
        "button[class*='picker']",
    ]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed() and _is_flash_option(el.text):
                    if _is_disabled(el):
                        raise ModelLimitReached("Flash option disabled")
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    print("✅Flash(role)", end=" | ")
                    return True
        except ModelLimitReached:
            raise
        except Exception:
            continue

    xpaths = [
        "//*[normalize-space(text())='Flash']/ancestor-or-self::button[1]",
        "//mat-option[.//span[contains(text(),'Flash') and "
        "not(contains(text(),'Lite'))]]",
        "//button[.//span[contains(text(),'Flash') and "
        "not(contains(text(),'Lite'))]]",
        "//*[@role='option' and contains(.,'Flash') and not(contains(.,'Lite'))]",
    ]
    for xp in xpaths:
        try:
            for el in drv.find_elements(By.XPATH, xp):
                if el.is_displayed() and _is_flash_option(el.text):
                    if _is_disabled(el):
                        raise ModelLimitReached("Flash disabled (xpath)")
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    print("✅Flash(xpath)", end=" | ")
                    return True
        except ModelLimitReached:
            raise
        except Exception:
            continue

    try:
        result = drv.execute_script("""
            var candidates = document.querySelectorAll(
                'mat-option, [role="option"], [role="menuitem"],'
                '[role="menuitemradio"], button');
            for (var i = 0; i < candidates.length; i++) {
                var el = candidates[i];
                if (!el.offsetParent) continue;
                var txt = (el.textContent || '').trim();
                var lower = txt.toLowerCase();
                if (lower.indexOf('flash') === -1 || lower.indexOf('lite') !== -1) continue;
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
    try:
        txt = _get_current_model_text(drv)
        return bool(txt and "flash" in txt.lower() and "lite" not in txt.lower())
    except Exception:
        return False


def switch_to_flash(drv):
    """Full Flash-mode switcher, mirrors switch_to_pro but targets plain Flash."""
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
            except Exception:
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
            except Exception:
                pass
            raise

        if not clicked:
            try:
                drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception:
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
# SECTION 11: MAIN GEN SEND FUNCTION
# ============================================================================
def send_image_gen_request(drv, ref_paths, prompt_text, max_send_retries=6):
    if check_captcha(drv):
        return "CAPTCHA"

    if not activate_create_image_mode(drv):
        print("❌ImgModeActivate", end=" | ")
        return False

    time.sleep(0.3)
    if check_captcha(drv):
        return "CAPTCHA"

    upload_ok = _upload_refs_in_image_mode(drv, ref_paths)
    if not upload_ok:
        print("❌UploadFail", end=" | ")
        return False

    attached = _wait_for_attachment_chip(drv, timeout=8.0)
    print("✅Attached" if attached else "⚠️NoChip(continue)", end=" | ")

    handle_consent(drv)
    time.sleep(0.25)

    if check_captcha(drv):
        return "CAPTCHA"

    inject_ok = _inject_prompt_via_clipboard(drv, prompt_text)
    if not inject_ok:
        print("❌PromptInjectFail", end=" | ")
        return False

    time.sleep(0.25)
    handle_consent(drv)

    for attempt in range(max_send_retries):
        if _click_send_button(drv):
            print("✅Sent", end=" | ")
            return True
        time.sleep(0.3)
        handle_consent(drv)

    try:
        editor = _get_quill_editor(drv)
        if editor and editor.is_displayed():
            editor.send_keys(Keys.RETURN)
            print("✅Sent(↵)", end=" | ")
            return True
    except Exception:
        pass

    print("❌SendFail", end=" | ")
    return False

# ============================================================================
# SECTION 12: IMAGE DETECTION (double-scan false-positive fix)
# ============================================================================
def poll_gen_response(drv, urls_before, chat_urls):
    rc = check_text_error(drv)
    if rc:
        return (GEN_REFUSED if rc == "refusal" else GEN_LIMIT), None
    if check_gemini_error(drv):
        if _send_btn_enabled(drv) or _response_done(drv):
            return GEN_ERROR, None

    try:
        blob_srcs = drv.execute_script("""
            var srcs=[];
            var imgs=document.querySelectorAll(
                'img[src^="blob:https://gemini.google.com"]');
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
                chat_urls.add(src)
                return GEN_SUCCESS, src
    except Exception:
        pass

    for sel in [
        "generated-image img", "single-image img",
        "img[src*='googleusercontent']",
        "model-response img", ".response-container-content img",
    ]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if not img.is_displayed():
                        continue
                    src = img.get_attribute("src") or ""
                    tid = img.get_attribute("data-test-id") or ""
                    if (len(src) < 10 or "uploaded-img" in tid
                            or tid == "image-preview"):
                        continue
                    if src in urls_before or src in chat_urls:
                        continue
                    if (src.startswith("blob:https://gemini.google.com")
                            or "googleusercontent" in src):
                        chat_urls.add(src)
                        return GEN_SUCCESS, src
                except Exception:
                    continue
        except Exception:
            pass

    if _response_done(drv) and _send_btn_enabled(drv):
        time.sleep(0.5)
        try:
            blob_srcs2 = drv.execute_script("""
                var srcs=[];
                var imgs=document.querySelectorAll(
                    'img[src^="blob:https://gemini.google.com"]');
                for(var i=imgs.length-1;i>=0;i--){
                    var img=imgs[i]; if(!img.offsetParent) continue;
                    var src=img.getAttribute('src')||'';
                    var tid=img.getAttribute('data-test-id')||'';
                    if(tid.includes('uploaded-img')||tid==='image-preview') continue;
                    if(src.length>10) srcs.push(src);
                } return srcs;
            """) or []
            for src in blob_srcs2:
                if src not in urls_before and src not in chat_urls:
                    chat_urls.add(src)
                    return GEN_SUCCESS, src
        except Exception:
            pass
        ge = check_gemini_error(drv)
        if ge:
            return GEN_ERROR, None
        rc2 = check_text_error(drv)
        if rc2:
            return (GEN_REFUSED if rc2 == "refusal" else GEN_LIMIT), None
        return GEN_TIMEOUT_S, None

    return "WAITING", None

# ============================================================================
# SECTION 13: DOWNLOAD
# ============================================================================
def _direct_fetch(drv, save_path, urls_before):
    try:
        blob = drv.execute_script("""
            var imgs=document.querySelectorAll(
                'single-image img,generated-image img,'
                'img[src^="blob:https://gemini.google.com"]');
            for(var i=imgs.length-1;i>=0;i--){
                var s=imgs[i].getAttribute('src');
                if(s&&s.startsWith('blob:https://gemini.google.com'))return s;
            } return null;""")
        if not blob or blob in urls_before:
            return False
        result = drv.execute_cdp_cmd("Runtime.evaluate", {
            "expression":
                f"fetch('{blob}').then(r=>r.blob())"
                ".then(b=>new Promise(resolve=>{"
                "const fr=new FileReader();"
                "fr.onloadend=()=>resolve(fr.result.split(',')[1]);"
                "fr.readAsDataURL(b);}));",
            "awaitPromise": True, "returnByValue": True,
        })
        if (result and "result" in result and "value" in result["result"]):
            data = base64.b64decode(result["result"]["value"])
            if len(data) > 5000:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                Path(save_path).write_bytes(data)
                print(f"✅Fetch({len(data)//1024}KB)", end=" | ")
                return True
    except Exception:
        pass
    return False


def _click_dl_btn(drv):
    selectors = [
        ("css",  "button[data-test-id='download-generated-image-button']"),
        ("css",  "button[aria-label='Download']"),
        ("css",  "button[aria-label='Download image']"),
        ("css",  "button[aria-label*='Download']"),
        ("xpath","//button[contains(@aria-label,'Download')]"),
        ("xpath","//mat-icon[contains(@fonticon,'download')]/ancestor::button"),
    ]
    for by_type, sel in selectors:
        try:
            by = By.XPATH if by_type == "xpath" else By.CSS_SELECTOR
            for btn in reversed(drv.find_elements(by, sel)):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(0.1)
                    drv.execute_script("arguments[0].click();", btn)
                    print("🔘DLBtn", end=" | ")
                    return True
        except Exception:
            continue
    return False


def _hover_and_download(drv, urls_before, excluded):
    def _try_hover(img):
        try:
            drv.execute_script(
                "arguments[0].scrollIntoView("
                "{block:'center',behavior:'smooth'});", img)
            time.sleep(0.4)
            try:
                ActionChains(drv).move_to_element(img).perform()
                time.sleep(0.5)
                if _click_dl_btn(drv):
                    return True
            except Exception:
                pass
            try:
                drv.execute_script("""
                    var el=arguments[0];
                    ['mouseenter','mouseover','mousemove'].forEach(function(evt){
                        el.dispatchEvent(new MouseEvent(evt,{bubbles:true,
                            cancelable:true,view:window,
                            clientX:el.getBoundingClientRect().left+el.offsetWidth/2,
                            clientY:el.getBoundingClientRect().top+el.offsetHeight/2}));
                    });
                """, img)
                time.sleep(0.5)
                if _click_dl_btn(drv):
                    return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    try:
        drv.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        time.sleep(0.4)
    except Exception:
        pass

    for sel in [
        "single-image img", "generated-image img",
        "img[src^='blob:https://gemini.google.com']",
        "img[src*='googleusercontent']",
    ]:
        try:
            for img in reversed(drv.find_elements(By.CSS_SELECTOR, sel)):
                src = img.get_attribute("src") or ""
                tid = img.get_attribute("data-test-id") or ""
                if "uploaded-img" in tid or tid == "image-preview":
                    continue
                if src in urls_before or src in excluded or len(src) < 10:
                    continue
                if img.is_displayed():
                    if _try_hover(img):
                        return True
        except Exception:
            continue

    try:
        clicked = drv.execute_script("""
            window.scrollTo(0,document.body.scrollHeight);
            var containers=document.querySelectorAll(
                'single-image,generated-image,.response-container-content');
            for(var i=containers.length-1;i>=0;i--){
                containers[i].dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));
            }
            var btns=document.querySelectorAll(
                'button[data-test-id="download-generated-image-button"],'
                +'button[aria-label*="Download"]');
            for(var i=btns.length-1;i>=0;i--){
                var b=btns[i];
                if(b.offsetParent!==null&&!b.disabled){
                    b.scrollIntoView({block:'center'});b.click();return 'OK';
                }
            } return null;
        """)
        if clicked:
            return True
    except Exception:
        pass
    return False


def _wait_for_dl(dl_dir, files_before, timeout=None):
    timeout = timeout or DOWNLOAD_TIMEOUT
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            cur = set(os.listdir(dl_dir))
            new_files = {
                f for f in (cur - files_before)
                if not f.endswith((".crdownload", ".tmp", ".part"))
                and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            }
            if new_files:
                fn = sorted(
                    new_files,
                    key=lambda f: os.path.getmtime(os.path.join(dl_dir, f)),
                    reverse=True,
                )[0]
                fp = os.path.join(dl_dir, fn)
                if os.path.getsize(fp) > 5000:
                    return fp
        except Exception:
            pass
        time.sleep(0.4)
    return None


def download_image(drv, save_path, urls_before, chat_urls, dl_dir, retries=3):
    if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
        print("✅AlreadyDL", end=" | ")
        return True
    if _direct_fetch(drv, save_path, urls_before):
        return True
    time.sleep(0.5)
    os.makedirs(dl_dir, exist_ok=True)
    for attempt in range(1, retries + 1):
        print(f"⬇️A{attempt}", end=" | ")
        try:
            files_before_dl = (set(os.listdir(dl_dir))
                               if os.path.exists(dl_dir) else set())
            drv.execute_script("window.scrollTo(0,document.body.scrollHeight);")
            time.sleep(0.3)
            hover_ok = _hover_and_download(drv, urls_before, chat_urls)
            fp = _wait_for_dl(
                dl_dir, files_before_dl,
                timeout=DOWNLOAD_TIMEOUT if hover_ok else 8)
            if fp:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(fp, save_path)
                except Exception:
                    shutil.copy2(fp, save_path)
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
                if (os.path.exists(save_path)
                        and os.path.getsize(save_path) > 1000):
                    print(f"✅DL({os.path.getsize(save_path)//1024}KB)",
                          end=" | ")
                    return True
        except Exception as e:
            print(f"⚠️DLErr:{str(e)[:15]}", end=" | ")
        time.sleep(0.5)
    if _direct_fetch(drv, save_path, urls_before):
        return True
    print("❌DLFail", end=" | ")
    return False

# ============================================================================
# SECTION 14: DRIVER + TABS
# ============================================================================
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
    svc = Service(ChromeDriverManager().install())
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


def setup_tabs(drv, url, total=TOTAL_TABS):
    print(f"\n{'='*60}\n📑 SETTING UP {total} TABS ({url})\n{'='*60}")
    handles = []
    try:
        drv.get(url)
        time.sleep(1.5)
        handles.append(drv.current_window_handle)
        print("✅ Tab 1 ready")
    except Exception as e:
        print(f"❌ Tab 1: {e}")
    for i in range(2, total + 1):
        print(f"📑 Tab {i}...", end=" ")
        h = create_tab(drv, url=url, wait_sec=0.8)
        if h:
            handles.append(h)
            print("✅")
        else:
            print("⚠️ FAILED")
    print(f"✅ {len(handles)}/{total} tabs ready")
    return handles

# ============================================================================
# SECTION 15: LOGIN
# ============================================================================
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
    except Exception:
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
    except Exception:
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
        except Exception:
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
# SECTION 16: JOB SCANNER (by-combo structure)
# ============================================================================
def scan_order_combo_jobs(order_id, order_path, verbose=True):
    """
    order_path/by-combo/<combo_folder>/ref/*.{png,webp}
    -> image/<combo_folder>.image.png
    -> WR/<combo_folder>.WR.png
    """
    jobs = []
    by_combo_path = os.path.join(order_path, "by-combo")
    if not os.path.isdir(by_combo_path):
        return jobs

    try:
        combo_folders = sorted(os.listdir(by_combo_path))
    except Exception:
        return jobs

    for combo_folder in combo_folders:
        combo_path = os.path.join(by_combo_path, combo_folder)
        if not os.path.isdir(combo_path):
            continue

        ref_dir   = os.path.join(combo_path, "ref")
        image_dir = os.path.join(combo_path, "image")
        wr_dir    = os.path.join(combo_path, "WR")

        safe_name = re.sub(r"[^\w.\-]", "_", combo_folder)[:80]
        image_path = os.path.join(image_dir, f"{safe_name}.image.png")
        wr_path    = os.path.join(wr_dir, f"{safe_name}.WR.png")

        img_exists = os.path.exists(image_path) and os.path.getsize(image_path) > 1000
        wr_exists  = os.path.exists(wr_path) and os.path.getsize(wr_path) > 1000

        label = combo_folder[:60]

        if img_exists and wr_exists:
            continue  # fully done

        if img_exists and not wr_exists:
            os.makedirs(wr_dir, exist_ok=True)
            jobs.append({
                "order_id": order_id, "combo_folder": combo_folder,
                "label": label, "refs": [], "prompt_text": PROMPT_TEXT,
                "image_path": image_path, "wr_path": wr_path,
                "wr_only": True,
            })
            if verbose: print(f"   🔧 WR-only: {label}")
            continue

        refs = collect_all_refs(ref_dir, label, verbose=verbose)
        if not refs:
            continue

        os.makedirs(image_dir, exist_ok=True)
        os.makedirs(wr_dir, exist_ok=True)
        jobs.append({
            "order_id": order_id, "combo_folder": combo_folder,
            "label": label, "refs": refs, "prompt_text": PROMPT_TEXT,
            "image_path": image_path, "wr_path": wr_path,
            "wr_only": False,
        })
    return jobs


def scan_all_orders(order_dirs):
    result = []
    total_jobs = 0
    for order_id, order_path in order_dirs:
        jobs = scan_order_combo_jobs(order_id, order_path)
        total_jobs += len(jobs)
        result.append((order_id, jobs))
        wr_only_count = sum(1 for j in jobs if j.get("wr_only"))
        gen_count = len(jobs) - wr_only_count
        print(f"   📋 {order_id[:24]}… → {len(jobs)} jobs "
              f"({gen_count} gen, {wr_only_count} WR-only)")
    print(f"\n   ✅ Total: {total_jobs} jobs across {len(order_dirs)} orders")
    return result, total_jobs

# ============================================================================
# SECTION 17: GENERATION SETUP (per job)
# ============================================================================
def setup_gen_job(drv, job, tab_id):
    drv.get(GEMINI_APP_URL)
    time.sleep(0.9)
    if check_captcha(drv):
        print("🤖CAPTCHA(nav)", end=" | ")
        return "CAPTCHA"

    close_dialogs(drv)
    grant_clipboard(drv)

    try:
        switch_to_flash(drv)
    except ModelLimitReached:
        print("🛑FlashLimit", end=" | ")
        return "MODEL_LIMIT"
    except Exception as e:
        print(f"⚠️Flash:{str(e)[:20]}", end=" | ")
        if check_captcha(drv):
            return "CAPTCHA"
        drv.get(GEMINI_APP_URL)
        time.sleep(1)
        try:
            switch_to_flash(drv)
        except ModelLimitReached:
            return "MODEL_LIMIT"
        except Exception:
            return "FAIL"

    local_refs = []
    for ref_path in job["refs"]:
        local = copy_local(ref_path, dest_dir=tab_local_dir(tab_id))
        local_refs.append(local if local and os.path.exists(local) else ref_path)
    if not local_refs:
        print("❌NoRefs", end=" | ")
        return "FAIL"

    result = send_image_gen_request(drv, local_refs, job["prompt_text"])
    if result == "CAPTCHA":
        return "CAPTCHA"
    if result:
        return "OK"

    if check_captcha(drv):
        return "CAPTCHA"

    print("↩️Fallback(JSDrop)", end=" | ")
    drv.get(GEMINI_APP_URL)
    time.sleep(0.9)
    if check_captcha(drv):
        return "CAPTCHA"
    close_dialogs(drv)
    try:
        switch_to_flash(drv)
    except ModelLimitReached:
        return "MODEL_LIMIT"
    except Exception:
        return "FAIL"

    if not activate_create_image_mode(drv):
        return "FAIL"

    for i, ref_path in enumerate(local_refs):
        print(f"📎JSD{i+1}/{len(local_refs)}", end=" | ")
        ok = _jsdrop_single(drv, ref_path)
        if not ok:
            return "FAIL"
        time.sleep(0.4)
        handle_consent(drv)

    if not _inject_prompt_via_clipboard(drv, job["prompt_text"]):
        return "FAIL"

    time.sleep(0.25)
    for _ in range(6):
        if _click_send_button(drv):
            print("✅Sent(JSD)", end=" | ")
            return "OK"
        time.sleep(0.25)
    return "FAIL"

# ============================================================================
# SECTION 18: 6-TAB GEN SCHEDULER
# ============================================================================
def run_gen_pass(drv, job_queue, stats_label="Main"):
    if not job_queue:
        return []

    wr_only_jobs = [j for j in job_queue if j.get("wr_only")]
    gen_jobs     = [j for j in job_queue if not j.get("wr_only")]

    if not gen_jobs:
        return []

    tab_handles = setup_tabs(drv, GEMINI_APP_URL, TOTAL_TABS)
    if not tab_handles:
        print("❌ No tabs created")
        return list(gen_jobs)

    tabs = []
    for i, h in enumerate(tab_handles, 1):
        tabs.append({
            "id": i, "handle": h, "state": S_IDLE, "job": None,
            "urls_before": set(), "chat_urls": set(),
            "state_start": 0.0, "next_poll": 0.0,
            "dl_dir": tab_dl_dir(i), "errors": 0,
        })
        set_tab_download_dir(drv, tab_dl_dir(i))

    queue             = list(gen_jobs)
    completed, failed = [], []
    total             = len(gen_jobs)
    last_print = last_captcha = 0.0
    rnd = 0

    def tl(t):
        job = t["job"]
        return f"G{t['id']}[{job['label'] if job else '-'}]"

    while True:
        rnd += 1
        now = time.time()

        if now - last_captcha > 8.0:
            last_captcha = now
            do_captcha_pause(drv, tabs, tl)

        all_idle = all(t["state"] == S_IDLE and t["job"] is None for t in tabs)
        if all_idle and not queue:
            break

        if now - last_print > 10:
            last_print = now
            active = sum(1 for t in tabs if t["state"] == S_GEN_WAIT)
            ipy_display(HTML(
                f"<div style='background:#1a1a2e;color:#a8dadc;padding:8px;"
                f"border-radius:6px;font-family:monospace;font-size:11px;'>"
                f"[{stats_label}] R{rnd} | Q:{len(queue)} "
                f"✅{len(completed)} ❌{len(failed)}/{total} "
                f"| Active:{active}/6</div>"))

        for t in tabs:
            if t["state"] != S_IDLE or t["job"] is not None:
                continue
            if not queue:
                continue
            job = queue.pop(0)

            if os.path.exists(job["wr_path"]) and os.path.getsize(job["wr_path"]) > 1000:
                completed.append(job)
                continue

            if os.path.exists(job["image_path"]) and os.path.getsize(job["image_path"]) > 1000:
                completed.append(job)
                continue

            t["job"] = job
            t["urls_before"] = set()
            t["chat_urls"] = set()
            t["state_start"] = time.time()
            t["errors"] = 0

            print(f"\n🟢 [G{t['id']}] {job['label']} "
                  f"({len(job['refs'])} refs) | ", end="")
            drv.switch_to.window(t["handle"])
            result = setup_gen_job(drv, job, t["id"])

            if result == "CAPTCHA":
                do_captcha_pause(drv, tabs, tl)
                queue.insert(0, job)
                t["job"] = None
                t["state"] = S_IDLE
            elif result == "OK":
                t["urls_before"] = snapshot_urls(drv)
                t["state"] = S_GEN_WAIT
                t["state_start"] = time.time()
                t["next_poll"] = time.time() + 0.5
                print("→ Waiting gen…")
            elif result == "MODEL_LIMIT":
                ipy_display(HTML(
                    "<div style='background:#e67e22;color:white;padding:10px;"
                    "border-radius:8px;font-weight:bold;'>🛑 FLASH LIMIT HIT</div>"))
                failed.append(job)
                for q_job in queue:
                    failed.append(q_job)
                queue.clear()
                for other_t in tabs:
                    if other_t["job"] and other_t["id"] != t["id"]:
                        failed.append(other_t["job"])
                        other_t["job"] = None
                        other_t["state"] = S_IDLE
                t["job"] = None
                t["state"] = S_IDLE
                break
            else:
                print("❌Setup failed → skip")
                failed.append(job)
                t["job"] = None
                t["state"] = S_IDLE

        for t in tabs:
            if t["state"] != S_GEN_WAIT:
                continue
            if time.time() < t["next_poll"]:
                continue
            elapsed = time.time() - t["state_start"]
            job = t["job"]
            drv.switch_to.window(t["handle"])

            if elapsed > GEN_TIMEOUT:
                print(f"\n   ⏭️ [G{t['id']}] TIMEOUT({int(elapsed)}s): {job['label']}")
                failed.append(job)
                t["job"] = None
                t["state"] = S_IDLE
                continue

            if check_something_wrong(drv):
                print(f"\n   ⚠️ [G{t['id']}] page error: {job['label']}")
                failed.append(job)
                recover_from_error(drv)
                t["job"] = None
                t["state"] = S_IDLE
                continue

            if check_pro_limit(drv):
                ipy_display(HTML(
                    "<div style='background:#e67e22;color:white;padding:10px;"
                    "border-radius:8px;font-weight:bold;'>🛑 GEN LIMIT</div>"))
                failed.append(job)
                for q_job in queue:
                    failed.append(q_job)
                queue.clear()
                t["job"] = None
                t["state"] = S_IDLE
                continue

            status, url = poll_gen_response(drv, t["urls_before"], t["chat_urls"])

            if status == GEN_SUCCESS:
                print(f"\n   🖼️ [G{t['id']}] image({int(elapsed)}s): {job['label']} | ", end="")
                time.sleep(0.3)
                set_tab_download_dir(drv, t["dl_dir"])
                clean_tab_downloads(t["id"])
                dl_ok = download_image(
                    drv, job["image_path"], t["urls_before"],
                    t["chat_urls"], t["dl_dir"], retries=3)
                if (dl_ok and os.path.exists(job["image_path"])
                        and os.path.getsize(job["image_path"]) > 1000):
                    print(f"🎉 DONE: {job['label']}")
                    completed.append(job)
                else:
                    print(f"⚠️ DL failed: {job['label']}")
                    failed.append(job)
                t["job"] = None
                t["state"] = S_IDLE

            elif status == GEN_ERROR:
                print(f"\n   ⚠️ [G{t['id']}] Gemini error: {job['label']}")
                failed.append(job)
                t["job"] = None
                t["state"] = S_IDLE
            elif status == GEN_REFUSED:
                print(f"\n   🚫 [G{t['id']}] Refused: {job['label']}")
                failed.append(job)
                t["job"] = None
                t["state"] = S_IDLE
            elif status == GEN_LIMIT:
                ipy_display(HTML(
                    "<div style='background:#e67e22;color:white;padding:10px;"
                    "border-radius:8px;font-weight:bold;'>🛑 GEN LIMIT</div>"))
                failed.append(job)
                for q_job in queue:
                    failed.append(q_job)
                queue.clear()
                t["job"] = None
                t["state"] = S_IDLE
            elif status == GEN_TIMEOUT_S:
                print(f"\n   ⏭️ [G{t['id']}] text-only: {job['label']}")
                failed.append(job)
                t["job"] = None
                t["state"] = S_IDLE
            else:
                t["next_poll"] = time.time() + 0.2

        waiting = [t for t in tabs if t["state"] == S_GEN_WAIT]
        if waiting:
            nearest = min(t["next_poll"] for t in waiting)
            sleep_s = max(0.02, min(nearest - time.time(), 0.25))
        elif any(t["state"] == S_IDLE and t["job"] is None for t in tabs) and queue:
            sleep_s = 0.02
        else:
            sleep_s = 0.3
        time.sleep(sleep_s)

    return failed

# ============================================================================
# SECTION 19: WMR (WATERMARK REMOVER) — DOWNLOAD-DIRECTORY BUG FIXED
# ----------------------------------------------------------------------------
# ROOT CAUSE (confirmed from your log — "Current: 0 files" for the full 60s
# on every tab, on every attempt):
#
#   1. set_tab_download_dir() calls execute_cdp_cmd("Page.setDownloadBehavior")
#      after switch_to.window(h). In Selenium 4 this CDP call does NOT
#      reliably rebind to the newly-focused tab — it can stay attached to
#      whichever target was active when the CDP session was first opened.
#      So the per-tab "tab_N" override was silently a no-op.
#
#   2. Because of (1), every download fell back to the browser's actual
#      default directory — which was ALSO wrong, because the WMR driver was
#      built with the generic make_driver(), whose Chrome prefs point
#      download.default_directory at CHROME_DL_BASE (the Gemini GEN tabs'
#      folder), not WMR_DL_DIR at all.
#
# Net effect: files were downloading somewhere neither tab_1/ nor tab_2/
# ever looked, so every job "processed successfully" in the browser but
# timed out in the script.
#
# FIX (matches your working ECOM 2 script's proven approach):
#   • A dedicated make_wmr_driver() sets download.default_directory to ONE
#     single shared folder (WMR_DL_DIR) at browser-launch time — a real
#     Chrome preference, not a per-tab CDP override, so it's reliable no
#     matter which tab in the browser triggers the download.
#   • No more per-tab CDP overrides / no more tab_N subfolders.
#   • Right before clicking Download on any given tab, that shared folder
#     is cleaned and snapshotted. Since the monitor loop is single-threaded
#     and only ever has ONE tab inside its click+wait sequence at a time,
#     this stays race-free even with 6 tabs all finishing around the same
#     time — exactly how your ECOM 2 script does it.
# ============================================================================

import os, re, time, shutil, threading
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from IPython.display import display as ipy_display, HTML

SCRIPT_TIMEOUT        = 3
STATUS_SCRIPT_TIMEOUT = 5
TAB_CHECK_INTERVAL    = 0.5
MAX_WR_RETRIES        = 2
STALL_TIMEOUT         = 300

_wr_print_lock = threading.Lock()


def _wr_print(msg):
    with _wr_print_lock:
        print(msg, flush=True)


# ============================================================================
# DEDICATED WMR DRIVER — fixes the CHROME_DL_BASE-instead-of-WMR_DL_DIR bug
# ============================================================================
def make_wmr_driver():
    """
    Separate from the pipeline's generic make_driver(): sets the browser's
    ACTUAL default download directory to WMR_DL_DIR at launch time. This is
    a real Chrome preference (applies to the whole browser process for
    every tab), not a per-tab CDP override — so it can't silently fail to
    rebind the way execute_cdp_cmd("Page.setDownloadBehavior") did.
    """
    os.makedirs(WMR_DL_DIR, exist_ok=True)

    opts = Options()
    opts.binary_location = chrome_bin
    opts.add_argument(f"--window-size={SCREEN_W},{SCREEN_H}")
    opts.add_argument("--start-maximized")
    opts.add_argument("--lang=en-US,en")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-renderer-backgrounding")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option("prefs", {
        "download.default_directory":   os.path.abspath(WMR_DL_DIR),
        "download.prompt_for_download": False,
        "download.directory_upgrade":   True,
        "safebrowsing.enabled":         True,
    })
    opts.page_load_strategy = "normal"

    svc = Service(ChromeDriverManager().install())
    d = webdriver.Chrome(service=svc, options=opts)
    d.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    d.set_page_load_timeout(60)
    d.set_script_timeout(60)
    d.implicitly_wait(3)

    # Belt-and-suspenders: also set it via CDP on the initial tab. This
    # alone was NOT reliable across tab switches (that was the bug), but
    # it doesn't hurt to have it set correctly for tab 1 from the start.
    try:
        d.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow", "downloadPath": os.path.abspath(WMR_DL_DIR)})
    except Exception:
        pass

    _wr_print(f"✅ WMR Chrome ready — downloads → {os.path.abspath(WMR_DL_DIR)}")
    return d


def safe_execute_script(drv, script, timeout=SCRIPT_TIMEOUT):
    try:
        drv.set_script_timeout(timeout)
        return drv.execute_script(script)
    except (TimeoutException, WebDriverException):
        return None
    except Exception:
        return None
    finally:
        try:
            drv.set_script_timeout(60)
        except Exception:
            pass


def _wr_switch(drv, handle):
    try:
        drv.switch_to.window(handle)
        time.sleep(0.1)
        return True
    except Exception:
        return False


def _wr_scroll_top(drv):
    try:
        drv.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.1)
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


def _wmr_check_status_native(drv):
    """Fallback when the JS check times out — plain WebDriver DOM query,
    doesn't compete for a turn on a busy page JS thread."""
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button.bg-success"):
            if btn.is_displayed() and btn.is_enabled():
                return "done"
    except Exception:
        pass
    try:
        body_text = drv.find_element(By.TAG_NAME, "body").text.lower()
        if "not detected" in body_text or "no watermark" in body_text:
            return "not_found"
        if "detecting" in body_text or "processing" in body_text:
            return "busy"
        if len(body_text) < 10:
            return "loading"
    except Exception:
        pass
    return "error"


def _wmr_check_status(drv, tab_key=None):
    """Returns: 'done' | 'busy' | 'loading' | 'not_found' | 'error'"""
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
    """, timeout=STATUS_SCRIPT_TIMEOUT)

    if result is not None:
        return result.lower()
    return _wmr_check_status_native(drv)


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


# ============================================================================
# SHARED DOWNLOAD FOLDER — the actual fix
# ============================================================================
def _wmr_clean_shared_dl_dir():
    """Empty the ONE shared WMR_DL_DIR right before a click, so whatever
    file appears next is unambiguously this job's download."""
    try:
        os.makedirs(WMR_DL_DIR, exist_ok=True)
        for f in os.listdir(WMR_DL_DIR):
            fp = os.path.join(WMR_DL_DIR, f)
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
    except Exception:
        pass


def _wmr_wait_download_shared(existing, timeout=None):
    """Wait for a new complete file to land in the single shared WMR_DL_DIR."""
    timeout = timeout or DOWNLOAD_TIMEOUT
    t0 = time.time()
    time.sleep(0.5)  # give Chrome a moment to actually start writing

    while time.time() - t0 < timeout:
        try:
            current = set(os.listdir(WMR_DL_DIR))
            new_files = current - existing
            complete = []
            for fn in new_files:
                if fn.endswith((".crdownload", ".tmp", ".part", ".download")):
                    continue
                if fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    fp = os.path.join(WMR_DL_DIR, fn)
                    if os.path.isfile(fp):
                        size = os.path.getsize(fp)
                        if size > 1000:
                            complete.append((fp, fn, size, os.path.getmtime(fp)))
            if complete:
                complete.sort(key=lambda x: x[3], reverse=True)
                return complete[0][0], complete[0][1]
        except Exception:
            pass
        time.sleep(0.3)

    _wr_print(f"    ❌ No download appeared in {WMR_DL_DIR} after {timeout}s. "
              f"Contents now: {os.listdir(WMR_DL_DIR) if os.path.exists(WMR_DL_DIR) else '(missing)'}")
    return None, None


# ============================================================================
# MAIN WMR PASS
# ============================================================================
def run_wmr_pass(drv, jobs, num_tabs=TOTAL_TABS):
    """
    drv MUST be a driver created with make_wmr_driver() (not the generic
    make_driver()) so download.default_directory is actually WMR_DL_DIR.
    """
    todo = [j for j in jobs
            if os.path.exists(j["image_path"])
            and not (os.path.exists(j["wr_path"]) and os.path.getsize(j["wr_path"]) > 1000)]
    if not todo:
        _wr_print("✅ Nothing to WR")
        return []

    tab_handles = setup_tabs(drv, WMR_URL, num_tabs)
    if not tab_handles:
        _wr_print("❌ No WMR tabs created")
        return todo

    _wmr_clean_shared_dl_dir()

    total = len(todo)
    queue = list(todo)
    retry_queue = []
    retry_counts = {}
    completed, failed = [], []

    tab_states, tab_jobs, tab_start, tab_num = {}, {}, {}, {}
    for i, h in enumerate(tab_handles, 1):
        tab_states[h] = "idle"
        tab_jobs[h] = None
        tab_start[h] = 0.0
        tab_num[h] = i

    def next_job():
        if retry_queue:
            return retry_queue.pop(0)
        if queue:
            return queue.pop(0)
        return None

    def assign(h):
        job = next_job()
        if job is None:
            tab_states[h] = "idle"
            tab_jobs[h] = None
            return False

        tnum = tab_num[h]
        rc = retry_counts.get(job["label"], 0)
        rtag = f" [retry {rc}/{MAX_WR_RETRIES}]" if rc > 0 else ""
        short_label = job['label'][:50] + ("…" if len(job['label']) > 50 else "")
        _wr_print(f"[Tab {tnum}] ▶ {short_label}{rtag}")

        tab_jobs[h] = job
        tab_states[h] = "uploading"
        tab_start[h] = time.time()

        try:
            _wr_switch(drv, h)
            drv.get(WMR_URL)
            time.sleep(1.5)
            _wr_scroll_top(drv)

            fi = _wmr_find_file_input(drv)
            if not fi:
                time.sleep(0.3)
                fi = _wmr_find_file_input(drv)
            if not fi:
                _wr_print(f"[Tab {tnum}] ⚠️ No file input: {job['label'][:40]}")
                tab_states[h] = "error"
                return True

            fi.send_keys(os.path.abspath(job["image_path"]))
            time.sleep(0.5)
            tab_states[h] = "processing"
            tab_start[h] = time.time()
        except Exception as e:
            _wr_print(f"[Tab {tnum}] ⚠️ Upload error: {str(e)[:60]}")
            tab_states[h] = "error"
        return True

    def handle_success(h, job):
        nonlocal completed
        tnum = tab_num[h]

        # CRITICAL: clean + snapshot the ONE shared folder immediately
        # before clicking — since the monitor loop is single-threaded,
        # only this tab's download can land here between now and pickup.
        _wmr_clean_shared_dl_dir()
        existing = set(os.listdir(WMR_DL_DIR))

        _wr_print(f"[Tab {tnum}] ✅ Processed — clicking Download...")
        if not _wmr_click_download(drv):
            handle_failure(h, job, "Cannot click Download button")
            return

        fp, fn = _wmr_wait_download_shared(existing, timeout=DOWNLOAD_TIMEOUT)
        if not fp:
            handle_failure(h, job, "Download timeout")
            return

        Path(job["wr_path"]).parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(fp, job["wr_path"])
        except Exception:
            try:
                shutil.copy2(fp, job["wr_path"])
                os.remove(fp)
            except Exception:
                pass

        if os.path.exists(job["wr_path"]) and os.path.getsize(job["wr_path"]) > 1000:
            completed.append(job)
            retry_counts.pop(job["label"], None)
            _wr_print(f"[Tab {tnum}] ✅ {fn} → {job['label'][:40]} "
                      f"({len(completed)}/{total})")
        else:
            handle_failure(h, job, "Output missing/too small")

    def handle_failure(h, job, reason):
        nonlocal failed
        tnum = tab_num[h]
        rc = retry_counts.get(job["label"], 0)
        if rc < MAX_WR_RETRIES:
            retry_counts[job["label"]] = rc + 1
            retry_queue.append(job)
            _wr_print(f"[Tab {tnum}] 🔄 RETRY ({rc+1}/{MAX_WR_RETRIES}) — {reason}")
        else:
            failed.append(job)
            _wr_print(f"[Tab {tnum}] ❌ FAILED — {reason}")
            retry_counts.pop(job["label"], None)

    def check_tab(h):
        state = tab_states.get(h, "idle")
        job = tab_jobs.get(h)
        elapsed = time.time() - tab_start.get(h, 0)
        tnum = tab_num.get(h, "?")

        if state == "idle":
            return False
        if state == "error":
            if job:
                handle_failure(h, job, "Error in processing")
            tab_states[h] = "idle"; tab_jobs[h] = None
            return True
        if state == "uploading":
            if elapsed > WMR_UPLOAD_WAIT:
                _wr_print(f"[Tab {tnum}] ⚠️ Upload timeout ({int(elapsed)}s)")
                tab_states[h] = "error"
            return False
        if state == "processing":
            if not _wr_switch(drv, h):
                tab_states[h] = "error"
                return False
            status = _wmr_check_status(drv, tab_key=h)

            if status == "done":
                handle_success(h, job)
                tab_states[h] = "idle"; tab_jobs[h] = None
                return True
            if status == "not_found":
                _wr_print(f"[Tab {tnum}] ⚠️ Not detected: {job['label'][:40]}")
                failed.append(job)
                tab_states[h] = "idle"; tab_jobs[h] = None
                return True
            if elapsed > WMR_PROCESS_WAIT:
                _wr_print(f"[Tab {tnum}] ⏳ Timeout ({int(elapsed)}s)")
                handle_failure(h, job, f"Processing timeout ({WMR_PROCESS_WAIT}s)")
                tab_states[h] = "idle"; tab_jobs[h] = None
                return True
            return False
        return False

    _wr_print(f"\n📤 Assigning first {min(num_tabs, total)} WR jobs "
              f"(shared download dir: {WMR_DL_DIR})...")
    for h in tab_handles:
        assign(h)
        time.sleep(0.3)

    last_status = last_progress = time.time()
    last_done = 0

    while True:
        active = sum(1 for s in tab_states.values() if s in ("uploading", "processing"))
        pending = len(queue) + len(retry_queue)
        done_count = len(completed) + len(failed)
        if pending == 0 and active == 0:
            break

        try:
            current_handles = set(drv.window_handles)
        except Exception:
            current_handles = set(tab_handles)

        for h in list(tab_states.keys()):
            if h not in current_handles:
                job = tab_jobs.get(h)
                if job and tab_states.get(h) in ("uploading", "processing"):
                    handle_failure(h, job, "Tab closed/crashed")
                for d in (tab_states, tab_jobs, tab_start, tab_num):
                    d.pop(h, None)
                if h in tab_handles:
                    tab_handles.remove(h)

        for h in list(tab_states.keys()):
            if check_tab(h):
                assign(h)

        now = time.time()
        if now - last_status >= 15:
            active = sum(1 for s in tab_states.values() if s in ("uploading", "processing"))
            _wr_print(f"    Active:{active}/{len(tab_handles)} | ✅{len(completed)} "
                      f"❌{len(failed)} | 🔄{len(retry_queue)} | "
                      f"{len(completed)+len(failed)}/{total}")
            last_status = now
            if done_count == last_done and now - last_progress > STALL_TIMEOUT:
                _wr_print("    ⚠️ STALL — resetting stuck tabs")
                for h in list(tab_states.keys()):
                    if tab_states[h] == "processing" and now - tab_start.get(h, now) > WMR_PROCESS_WAIT:
                        tab_states[h] = "error"

        if done_count > last_done:
            last_progress = time.time()
            last_done = done_count

        time.sleep(TAB_CHECK_INTERVAL)

    _wr_print(f"\n✅ WMR done: {len(completed)} ok, {len(failed)} failed (of {total})")
    return failed

# ============================================================================
# SECTION 20: TOP-LEVEL SCHEDULER
# ============================================================================
def run_scheduler(gen_drv, wmr_drv, ordered_jobs_by_order, total_jobs):
    ipy_display(HTML(f"""<div style='background:linear-gradient(
135deg,#0f2027,#203a43,#2c5364);padding:18px;border-radius:10px;
color:white;font-family:monospace;margin:10px 0;'>
<b style='font-size:18px;'>🚀 BY-COMBO PIPELINE (Flash + Fixed Prompt + WMR)</b><br>
<span style='font-size:13px;opacity:0.9;line-height:2;'>
Flow: + → Create image → + → Upload files (ALL refs) → xclip paste → verify → send<br>
Total: {total_jobs} | Gen Tabs: {TOTAL_TABS} | Model: Flash | WMR: {WMR_URL}<br>
Gen timeout: {GEN_TIMEOUT}s | DL timeout: {DOWNLOAD_TIMEOUT}s | Retry: {MAX_RETRY_ROUNDS}
</span></div>"""))

    main_queue = []
    for order_id, jobs in ordered_jobs_by_order:
        main_queue.extend(jobs)
    if not main_queue:
        print("✅ Nothing to process!")
        return

    # ── PHASE 1: GENERATION ─────────────────────────────────────────────
    print(f"\n{'='*60}\n▶ GEN PASS 1: {len(main_queue)} jobs\n{'='*60}")
    failed_after_main = run_gen_pass(gen_drv, main_queue, stats_label="Main")

    remaining_failed = failed_after_main
    for attempt in range(1, MAX_RETRY_ROUNDS + 1):
        if not remaining_failed:
            break
        ipy_display(HTML(
            f"<div style='background:linear-gradient(135deg,#6c5ce7,#a29bfe);"
            f"padding:14px;border-radius:8px;color:white;font-family:monospace;"
            f"font-weight:bold;'>🔄 GEN RETRY {attempt}/{MAX_RETRY_ROUNDS} — "
            f"{len(remaining_failed)} jobs</div>"))
        retry_queue = [dict(j) for j in remaining_failed]
        still_failed = run_gen_pass(gen_drv, retry_queue, stats_label=f"Retry{attempt}")
        remaining_failed = still_failed

    gen_done = total_jobs - len(remaining_failed)
    ipy_display(HTML(
        f"<div style='background:#1b4332;color:#b7e4c7;padding:12px;"
        f"border-radius:8px;font-family:monospace;font-weight:bold;'>"
        f"✅ Gen phase done | ✅ {gen_done}/{total_jobs} | "
        f"❌ {len(remaining_failed)} failed</div>"))

    # ── PHASE 2: WATERMARK REMOVAL ──────────────────────────────────────
    all_jobs = []
    for order_id, jobs in ordered_jobs_by_order:
        all_jobs.extend(jobs)
    # only jobs whose image now exists get WR'd
    wr_candidates = [j for j in all_jobs
                     if os.path.exists(j["image_path"])
                     and os.path.getsize(j["image_path"]) > 1000]

    if wr_candidates:
        print(f"\n{'='*60}\n▶ WMR PASS: {len(wr_candidates)} images\n{'='*60}")
        wr_failed = run_wmr_pass(wmr_drv, wr_candidates, num_tabs=TOTAL_TABS)
        for attempt in range(1, 3):
            if not wr_failed:
                break
            print(f"\n🔄 WMR RETRY {attempt}/2 — {len(wr_failed)} jobs")
            wr_failed = run_wmr_pass(wmr_drv, wr_failed, num_tabs=TOTAL_TABS)
    else:
        wr_failed = []

    total_done = sum(
        1 for j in all_jobs
        if os.path.exists(j["wr_path"]) and os.path.getsize(j["wr_path"]) > 1000
    )
    if remaining_failed or wr_failed:
        fl = "\n".join(f"  ❌ GEN: {j['label']}" for j in remaining_failed)
        fl += "\n" + "\n".join(f"  ❌ WR: {j['label']}" for j in wr_failed)
        ipy_display(HTML(
            f"<div style='background:#c0392b;color:white;padding:16px;"
            f"border-radius:10px;font-family:monospace;'>"
            f"<b>🛑 FINAL — ✅ {total_done}/{total_jobs} fully done</b>"
            f"<pre style='font-size:11px;margin-top:8px;opacity:0.9;'>"
            f"{fl}</pre></div>"))
    else:
        ipy_display(HTML(
            f"<div style='background:#34a853;color:white;padding:16px;"
            f"border-radius:10px;font-size:18px;font-weight:bold;'>"
            f"🎉 ALL {total_jobs} JOBS DONE (image + WR)!</div>"))
# ============================================================================
# SECTION 21: MAIN (IMPROVED)
# ============================================================================
def main():
    ipy_display(HTML(f"""<div style='background:linear-gradient(
135deg,#667eea,#764ba2);padding:22px;border-radius:12px;color:white;
text-align:center;font-size:22px;font-weight:bold;margin:20px 0;'>
🚀 BY-COMBO PIPELINE<br>
<span style='font-size:13px;opacity:0.9;'>
Flash Mode · Fixed Prompt · All Refs · Auto WMR<br>
6 Tabs · Retry {MAX_RETRY_ROUNDS}×
</span></div>"""))

    vnc_url = setup_novnc_ui()
    print(f"\n🖥️  VNC URL: {vnc_url}\n")

    if not os.path.isdir(BASE_ORDER):
        print(f"❌ Order folder not found: {BASE_ORDER}")
        return

    all_order_folders = sorted([
        d for d in os.listdir(BASE_ORDER)
        if (
            os.path.isdir(os.path.join(BASE_ORDER, d))
            and re.match(r'^[0-9a-f\-]{30,}$', d, re.IGNORECASE)
        )
    ])

    if not all_order_folders:
        print(f"❌ No order folders in {BASE_ORDER}")
        return

    # Pre-scan to filter out fully completed orders
    print("🔍 Scanning orders to filter out fully completed ones...")
    pending_orders = []
    for oid in all_order_folders:
        opath = os.path.join(BASE_ORDER, oid)
        jobs = scan_order_combo_jobs(oid, opath, verbose=False)
        if jobs:
            pending_orders.append((oid, opath, jobs))

    completed_count = len(all_order_folders) - len(pending_orders)

    if not pending_orders:
        print(f"\n✅ All {len(all_order_folders)} orders are fully completed! Nothing to process.")
        return

    print(f"\n{'='*70}")
    print(f"📂 FOUND {len(pending_orders)} PENDING ORDER(S) (Skipped {completed_count} fully completed)")
    print(f"{'='*70}")
    for i, (oid, _, jobs) in enumerate(pending_orders, 1):
        print(f"{i:>3}. {oid} ({len(jobs)} pending jobs)")
    print(f"{'='*70}")
    print("Enter range: 1,2 | 2-10 | all")

    ri = get_user_input("Range: ").strip().lower()
    if not ri:
        print("❌ No range entered.")
        return

    selected_indices = set()
    total_orders = len(pending_orders)
    if ri == "all":
        selected_indices = set(range(1, total_orders + 1))
    else:
        for part in ri.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    lo, hi = map(int, part.split("-", 1))
                    for x in range(lo, hi + 1):
                        if 1 <= x <= total_orders:
                            selected_indices.add(x)
                except Exception:
                    pass
            else:
                try:
                    x = int(part)
                    if 1 <= x <= total_orders:
                        selected_indices.add(x)
                except Exception:
                    pass

    if not selected_indices:
        print("❌ No valid orders selected.")
        return

    selected_orders = [
        (pending_orders[i - 1][0], pending_orders[i - 1][1])
        for i in sorted(selected_indices)
    ]

    # Reuse the scanned jobs instead of scanning again
    ordered_jobs = [(pending_orders[i - 1][0], pending_orders[i - 1][2]) for i in sorted(selected_indices)]
    total_jobs = sum(len(jobs) for _, jobs in ordered_jobs)

    print(f"\n✅ Selected {len(selected_orders)} order(s):")
    for oid, _ in selected_orders:
        print(f"   • {oid}")

    print(f"\n{'='*60}")
    print("📋 SUMMARY")
    for oid, jobs in ordered_jobs:
        if jobs:
            wr_only = sum(1 for j in jobs if j.get("wr_only"))
            print(f"   {oid[:24]}… → {len(jobs)} jobs (WR-only: {wr_only})")
    print(f"   {'─'*50}")
    print(f"   TOTAL JOBS: {total_jobs}")
    print(f"{'='*60}")

    print(f"\n{'='*60}")
    print("📋 SUMMARY")

    for oid, jobs in ordered_jobs:
        if jobs:
            wr_only = sum(1 for j in jobs if j.get("wr_only"))
            print(f"   {oid[:24]}… → {len(jobs)} jobs (WR-only: {wr_only})")

    print(f"   {'─'*50}")
    print(f"   TOTAL JOBS: {total_jobs}")
    print(f"{'='*60}")

    if get_user_input(f"\n▶ Process {total_jobs} jobs? (y/n): ").strip().lower() != "y":
        print("❌ Cancelled.")
        return

    gen_drv = None
    wmr_drv = None

    try:

        # ------------------------------------------------------------------
        # Gemini Driver
        # ------------------------------------------------------------------
        gen_drv = make_driver()

        if not gen_drv:
            print("❌ Failed to create Gemini driver.")
            return

        wait = WebDriverWait(gen_drv, TIMEOUT)

        if not handle_login(gen_drv, wait):

            ipy_display(HTML("""
<div style='background:#ea4335;
padding:20px;
border-radius:10px;
color:white;
text-align:center;
font-size:20px;
font-weight:bold;'>
❌ LOGIN FAILED
</div>
"""))
            return

        ipy_display(HTML("""
<div style='background:#34a853;
padding:16px;
border-radius:10px;
color:white;
text-align:center;
font-size:18px;
font-weight:bold;'>
✅ LOGIN SUCCESSFUL — STARTING PIPELINE
</div>
"""))

        # ------------------------------------------------------------------
        # WMR Driver
        #
        # IMPORTANT:
        # Uses make_wmr_driver() instead of make_driver().
        #
        # This browser is launched with:
        #
        #     download.default_directory = WMR_DL_DIR
        #
        # so every Download button writes into the shared WMR folder.
        #
        # No Page.setDownloadBehavior() tab switching required.
        # ------------------------------------------------------------------
        wmr_drv = make_wmr_driver()

        if not wmr_drv:
            print("❌ Failed to create WMR driver.")
            return

        run_scheduler(
            gen_drv,
            wmr_drv,
            ordered_jobs,
            total_jobs
        )

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user.")

    except Exception as e:
        print(f"\n❌ Pipeline error:\n{e}")

        import traceback
        traceback.print_exc()

    finally:

        for drv in (gen_drv, wmr_drv):
            if drv:
                try:
                    drv.quit()
                except Exception:
                    pass

        try:
            stop_novnc_ui()
        except Exception:
            pass

        print("\n✅ Pipeline finished.")


if __name__ == "__main__":
    main()





# @title 🔍 ECOM ORDER REVIEW
# ============================================================================
# 3-Column Viewer: Compare | Image (Generated) | WR (Clean)
# Actions: ✅ Right (save WR to Done/) | ❌ Wrong (delete WR + Image) | ⏭️ Skip
# ============================================================================

import os, re, shutil, base64
from io import BytesIO
from PIL import Image
from IPython.display import display, clear_output, HTML
import ipywidgets as widgets
from google.colab import drive

# Mount drive
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')
else:
    print("✅ Drive already mounted")

# ============================================================================
# CONFIG
# ============================================================================
BASE_ORDER = "/content/drive/MyDrive/Gemini/order"
IMG_EXTS = ('.jpg', '.jpeg', '.png', '.webp')

# ============================================================================
# IMAGE HELPER
# ============================================================================
def to_b64(path, max_size=600):
    try:
        with Image.open(path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                img = img.resize((int(img.size[0]*ratio), int(img.size[1]*ratio)), Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=90)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except:
        return None

# ============================================================================
# SCAN ORDER FOLDERS
# ============================================================================
def get_order_folders():
    if not os.path.isdir(BASE_ORDER):
        return []
    return sorted([
        d for d in os.listdir(BASE_ORDER)
        if os.path.isdir(os.path.join(BASE_ORDER, d))
        and re.match(r'^[0-9a-f\-]{30,}$', d, re.IGNORECASE)
    ])

def parse_selection(ri, n_total):
    selected = set()
    if ri == "all":
        return set(range(1, n_total + 1))
    for part in ri.split(","):
        part = part.strip()
        if "-" in part:
            try:
                lo, hi = part.split("-", 1)
                for x in range(int(lo.strip()), int(hi.strip()) + 1):
                    if 1 <= x <= n_total: selected.add(x)
            except: pass
        else:
            try:
                x = int(part)
                if 1 <= x <= n_total: selected.add(x)
            except: pass
    return selected

# ============================================================================
# SCAN REVIEW ITEMS FOR AN ORDER (BY-COMBO STRUCTURE)
# ============================================================================
def scan_review_items(order_id, order_path):
    """
    Scan BY-COMBO structure and build review items.
    Structure: order_path/by-combo/<combo_folder>/{ref, compare, image, WR, Done}/

    Shows: Compare (from compare/) | Image (Generated) | WR (Clean)
    """
    items = []
    by_combo_path = os.path.join(order_path, "by-combo")
    if not os.path.isdir(by_combo_path):
        return items

    try:
        combo_folders = sorted(os.listdir(by_combo_path))
    except:
        return items

    for combo_folder in combo_folders:
        combo_path = os.path.join(by_combo_path, combo_folder)
        if not os.path.isdir(combo_path):
            continue

        compare_dir = os.path.join(combo_path, "compare")
        image_dir = os.path.join(combo_path, "image")
        wr_dir = os.path.join(combo_path, "WR")
        done_dir = os.path.join(combo_path, "Done")

        # 1. Find WR image and extract number from filename
        wr_path = None
        wr_num = None
        if os.path.isdir(wr_dir):
            for fn in sorted(os.listdir(wr_dir)):
                if fn.lower().endswith(IMG_EXTS):
                    # Try to extract number from WR filename
                    m = re.match(r'^(\d+)', fn)
                    if m:
                        wr_num = m.group(1)
                    wr_path = os.path.join(wr_dir, fn)
                    break

        if not wr_path or not os.path.exists(wr_path) or os.path.getsize(wr_path) < 1000:
            continue

        # 2. Find Generated Image
        image_path = None
        if os.path.isdir(image_dir):
            for fn in sorted(os.listdir(image_dir)):
                if fn.lower().endswith(IMG_EXTS):
                    image_path = os.path.join(image_dir, fn)
                    break

        # 3. Find Compare image (from compare/ folder) - THIS IS THE "REF" COLUMN
        compare_path = None
        if os.path.isdir(compare_dir):
            for fn in sorted(os.listdir(compare_dir)):
                if fn.lower().endswith(IMG_EXTS):
                    # Prefer compare images that match the WR number
                    if wr_num:
                        m = re.match(r'^(\d+)', fn)
                        if m and m.group(1) == wr_num:
                            compare_path = os.path.join(compare_dir, fn)
                            break
                    # Fallback: just take the first compare image
                    if not compare_path:
                        compare_path = os.path.join(compare_dir, fn)

        # 4. Build Done path
        wr_base, wr_ext = os.path.splitext(os.path.basename(wr_path))
        done_fn = f"{combo_folder}.Done{wr_ext}"
        done_path = os.path.join(done_dir, done_fn)

        is_done = os.path.exists(done_path) and os.path.getsize(done_path) > 1000

        items.append({
            "order_id": order_id,
            "combo_folder": combo_folder,
            "compare_path": compare_path,
            "image_path": image_path,
            "wr_path": wr_path,
            "done_dir": done_dir,
            "done_path": done_path,
            "label": f"{order_id[:8]}…/{combo_folder[:45]}",
            "is_done": is_done,
        })

    return items

# ============================================================================
# ACTIONS
# ============================================================================
def action_right(item):
    """Mark as Right: copy WR to Done/ folder."""
    os.makedirs(item["done_dir"], exist_ok=True)
    try:
        shutil.copy2(item["wr_path"], item["done_path"])
        if os.path.exists(item["done_path"]):
            item["is_done"] = True
            return True
    except Exception as e:
        print(f"❌ Error saving to Done: {e}")
    return False

def action_wrong(item):
    """Delete WR and Generated Image files."""
    deleted = []
    # Delete WR
    if item["wr_path"] and os.path.exists(item["wr_path"]):
        try:
            os.remove(item["wr_path"])
            deleted.append("WR")
        except: pass
    # Delete Image
    if item["image_path"] and os.path.exists(item["image_path"]):
        try:
            os.remove(item["image_path"])
            deleted.append("Image")
        except: pass
    return deleted

# ============================================================================
# VIEWER CLASS
# ============================================================================
class OrderReviewViewer:
    def __init__(self, all_items, order_labels):
        self.all_items = all_items
        self.order_labels = order_labels
        self.index = 0
        self.skip_done = True

        self._advance_to_next_pending()

        # UI Elements
        self.main_out = widgets.Output()
        self.status_html = widgets.HTML()
        self.msg_html = widgets.HTML()

        self.btn_right = widgets.Button(description="✅ Right", button_style="success",
                                         layout=widgets.Layout(width='150px', height='40px'))
        self.btn_wrong = widgets.Button(description="❌ Wrong", button_style="danger",
                                         layout=widgets.Layout(width='150px', height='40px'))
        self.btn_skip = widgets.Button(description="⏭️ Skip", button_style="warning",
                                        layout=widgets.Layout(width='150px', height='40px'))
        self.btn_prev = widgets.Button(description="⬅️ Prev",
                                        layout=widgets.Layout(width='100px', height='40px'))
        self.btn_next = widgets.Button(description="➡️ Next",
                                        layout=widgets.Layout(width='100px', height='40px'))

        self.btn_right.on_click(self._on_right)
        self.btn_wrong.on_click(self._on_wrong)
        self.btn_skip.on_click(self._on_skip)
        self.btn_prev.on_click(self._on_prev)
        self.btn_next.on_click(self._on_next)

    def _advance_to_next_pending(self):
        if not self.skip_done: return
        while self.index < len(self.all_items):
            if not self.all_items[self.index]["is_done"]:
                return
            self.index += 1
        if self.index >= len(self.all_items):
            self.index = len(self.all_items)

    def _on_right(self, b):
        if self.index >= len(self.all_items): return
        item = self.all_items[self.index]
        ok = action_right(item)
        if ok:
            self.msg_html.value = f"<div style='color:#2ecc71;font-weight:bold;padding:8px;'>✅ Saved to Done: {os.path.basename(item['done_path'])}</div>"
        else:
            self.msg_html.value = "<div style='color:red;padding:8px;'>❌ Failed to save</div>"
        self.index += 1
        self._advance_to_next_pending()
        self.render()

    def _on_wrong(self, b):
        if self.index >= len(self.all_items): return
        item = self.all_items[self.index]
        deleted = action_wrong(item)
        self.msg_html.value = f"<div style='color:#e74c3c;font-weight:bold;padding:8px;'>🗑️ Deleted: {', '.join(deleted)}</div>"
        self.all_items.pop(self.index)
        if self.index >= len(self.all_items):
            self.index = max(0, len(self.all_items) - 1)
        self._advance_to_next_pending()
        self.render()

    def _on_skip(self, b):
        if self.index >= len(self.all_items): return
        self.msg_html.value = "<div style='color:#f39c12;padding:8px;'>⏭️ Skipped</div>"
        self.index += 1
        self._advance_to_next_pending()
        self.render()

    def _on_prev(self, b):
        if self.index > 0:
            self.index -= 1
            self.msg_html.value = ""
            self.render()

    def _on_next(self, b):
        if self.index < len(self.all_items) - 1:
            self.index += 1
            self.msg_html.value = ""
            self.render()

    def render(self):
        total = len(self.all_items)
        done_count = sum(1 for it in self.all_items if it["is_done"])
        pending = total - done_count

        self.status_html.value = (
            f"<div style='background:#1a1a2e;color:#a8dadc;padding:10px;border-radius:8px;"
            f"font-family:monospace;font-size:13px;margin:5px 0;'>"
            f"📋 Item {self.index+1}/{total} | ✅ Done: {done_count} | ⏳ Pending: {pending}"
            f"</div>"
        )

        self.btn_prev.disabled = self.index <= 0
        self.btn_next.disabled = self.index >= total - 1

        self.main_out.clear_output(wait=True)
        with self.main_out:
            if self.index >= total:
                display(HTML(
                    "<div style='background:#2ecc71;color:white;padding:30px;border-radius:12px;"
                    "text-align:center;font-size:22px;font-weight:bold;margin:20px;'>"
                    "🎉 ALL ITEMS REVIEWED!</div>"
                ))
                return

            item = self.all_items[self.index]

            # Header
            done_badge = ""
            if item["is_done"]:
                done_badge = "<span style='background:#2ecc71;color:white;padding:3px 10px;border-radius:12px;font-size:12px;margin-left:10px;'>✅ ALREADY DONE</span>"

            header_html = (
                f"<div style='background:linear-gradient(135deg,#667eea,#764ba2);color:white;"
                f"padding:12px 18px;border-radius:10px;font-weight:bold;font-size:15px;margin-bottom:10px;'>"
                f"📸 {item['label']}{done_badge}</div>"
            )

            # Col 1: COMPARE (from compare/ folder)
            if item["compare_path"] and os.path.exists(item["compare_path"]):
                src_cmp = to_b64(item["compare_path"])
                col1 = f"<div style='text-align:center;'><div style='font-weight:bold;color:#9b59b6;margin-bottom:8px;'>📐 COMPARE</div><img src='{src_cmp}' style='max-width:100%;max-height:500px;object-fit:contain;border:3px solid #9b59b6;border-radius:8px;'></div>"
            else:
                col1 = "<div style='text-align:center;padding:40px;color:#999;'>No compare image</div>"

            # Col 2: IMAGE (Generated)
            if item["image_path"] and os.path.exists(item["image_path"]):
                src_img = to_b64(item["image_path"])
                col2 = f"<div style='text-align:center;'><div style='font-weight:bold;color:#3498db;margin-bottom:8px;'>📐 IMAGE (Generated)</div><img src='{src_img}' style='max-width:100%;max-height:500px;object-fit:contain;border:3px solid #3498db;border-radius:8px;'></div>"
            else:
                col2 = "<div style='text-align:center;padding:40px;color:#999;'>No generated image</div>"

            # Col 3: WR (Clean)
            if item["wr_path"] and os.path.exists(item["wr_path"]):
                src_wr = to_b64(item["wr_path"])
                col3 = f"<div style='text-align:center;'><div style='font-weight:bold;color:#2ecc71;margin-bottom:8px;'>🖼️ WR (Clean)</div><img src='{src_wr}' style='max-width:100%;max-height:500px;object-fit:contain;border:3px solid #2ecc71;border-radius:8px;'></div>"
            else:
                col3 = "<div style='text-align:center;padding:40px;color:#999;'>WR image missing</div>"

            grid_html = f"""
            {header_html}
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin:10px 0;">
                <div style="background:#f8f9fa;border-radius:10px;padding:10px;">{col1}</div>
                <div style="background:#f8f9fa;border-radius:10px;padding:10px;">{col2}</div>
                <div style="background:#f8f9fa;border-radius:10px;padding:10px;">{col3}</div>
            </div>
            <div style="color:#888;font-size:11px;font-family:monospace;margin-top:5px; word-break:break-all;">
                <b>Compare:</b> {os.path.basename(item['compare_path']) if item['compare_path'] else 'N/A'} |
                <b>Image:</b> {os.path.basename(item['image_path']) if item['image_path'] else 'N/A'} |
                <b>WR:</b> {os.path.basename(item['wr_path']) if item['wr_path'] else 'N/A'}
            </div>
            """
            display(HTML(grid_html))

    def build_ui(self):
        action_bar = widgets.HBox(
            [self.btn_right, self.btn_wrong, self.btn_skip],
            layout=widgets.Layout(justify_content='center', margin='10px 0')
        )
        nav_bar = widgets.HBox(
            [self.btn_prev, self.btn_next],
            layout=widgets.Layout(justify_content='center', margin='5px 0')
        )
        return widgets.VBox([
            widgets.HTML("<h2 style='text-align:center;color:#2c3e50;'>🔍 BY-COMBO Order Review Viewer</h2>"),
            self.status_html,
            self.msg_html,
            action_bar,
            nav_bar,
            self.main_out
        ], layout=widgets.Layout(max_width='1600px', margin='0 auto'))

# ============================================================================
# MAIN
# ============================================================================
def main():
    clear_output()

    all_order_folders = get_order_folders()
    if not all_order_folders:
        print(f"❌ No order folders found in {BASE_ORDER}")
        return

    # Pre-scan to filter out fully completed orders
    print("🔍 Scanning orders to filter out fully completed ones...")
    pending_orders = []
    for oid in all_order_folders:
        opath = os.path.join(BASE_ORDER, oid)
        items = scan_review_items(oid, opath)
        pending_count = sum(1 for it in items if not it["is_done"])
        if pending_count > 0:
            pending_orders.append((oid, opath, pending_count))

    completed_count = len(all_order_folders) - len(pending_orders)

    if not pending_orders:
        print(f"\n✅ All {len(all_order_folders)} orders are fully reviewed! Nothing to process.")
        return

    print(f"\n{'='*70}")
    print(f"📂 FOUND {len(pending_orders)} PENDING ORDER(S) (Skipped {completed_count} fully completed)")
    print(f"{'='*70}")
    for i, (oid, _, pending_count) in enumerate(pending_orders, 1):
        print(f"    {i}. {oid} ({pending_count} pending)")
    print(f"{'='*70}")
    print(f"Enter range: 1,2 | 2-10 | all")

    ri = input("Range: ").strip().lower()
    if not ri:
        print("❌ No range entered")
        return

    selected = parse_selection(ri, len(pending_orders))
    if not selected:
        print("❌ No valid orders selected")
        return

    selected_orders = [(pending_orders[i-1][0], pending_orders[i-1][1])
                       for i in sorted(selected)]

    print(f"\n✅ Selected {len(selected_orders)} order(s)")
    print(f"📊 Scanning BY-COMBO jobs for selected orders...")

    all_items = []
    order_labels = []
    for order_id, order_path in selected_orders:
        items = scan_review_items(order_id, order_path)
        done_c = sum(1 for it in items if it["is_done"])
        print(f"   📋 {order_id[:24]}… → {len(items)} WR images ({done_c} already done)")
        all_items.extend(items)
        order_labels.append(order_id)

    if not all_items:
        print("\n❌ No WR images found to review!")
        return

    total_done = sum(1 for it in all_items if it["is_done"])
    print(f"\n   ✅ Total: {len(all_items)} items ({total_done} done, {len(all_items)-total_done} pending)")

    confirm = input(f"\n▶ Start reviewing {len(all_items)} items? (y/n): ").strip().lower()
    if confirm != "y":
        print("❌ Cancelled")
        return

    clear_output()
    viewer = OrderReviewViewer(all_items, order_labels)
    display(viewer.build_ui())
    viewer.render()

main()

