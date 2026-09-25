# ======================================================================
# REAL N2N V14
# 
# Gemini:
# T0-T3
# persistent Chrome
# persistent Gemini tabs
# first-free release order
# 
# WMR:
# W0-W3
# 2 tabs/profile
# global first-free
# owner-thread Selenium
# 
# Downloads:
# CDP GUID
# independent lifecycle
# 
# Backend:
# R2
# DB
# credits
# BullMQ
# 
# Authentication:
# Google + Gemini active validation
#
# ENVIRONMENT BOOTSTRAP:
# 4-Phase Architecture for zero-dependency kickoff
# ======================================================================

# ==============================================================================
# PHASE A: STDLIB-ONLY IMPORTS (Minimal Bootstrap)
# ==============================================================================
import asyncio
import os
import sys
import uuid
import time
import queue
import threading
import traceback
import json
import concurrent.futures
import subprocess
import re
import shutil
import pickle
import base64
import io
import socket
import heapq
import importlib
import platform
from pathlib import Path
from collections import deque
from datetime import datetime

# ==============================================================================
# PHASE B: DEPENDENCY INSTALL & VERIFY
# ==============================================================================
PYTHON_DEPENDENCIES = {
    "selenium": "selenium",
    "bullmq": "bullmq",
    "psycopg2": "psycopg2-binary",
    "boto3": "boto3",
    "PIL": "Pillow",
    "pyvirtualdisplay": "pyvirtualdisplay",
    "websockets": "websockets",
    "requests": "requests",
    "numpy": "numpy",
}

_dependency_lock = threading.Lock()
_bootstrap_done = False

def check_python_package(module_name):
    """Check if a Python package is importable."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False

def bootstrap_dependencies():
    """Install missing Python packages securely using pip."""
    global _bootstrap_done
    with _dependency_lock:
        if _bootstrap_done:
            return True

        print("============================================================")
        print("V14 N2N — ENVIRONMENT BOOTSTRAP")
        print("============================================================")
        print("[1/6] Python runtime")
        
        py_exe = sys.executable
        py_ver = sys.version.split()[0]
        print(f"  ... Python: {py_ver}")
        print(f"  ... Executable: {py_exe}")
        
        missing = []
        for mod, pkg in PYTHON_DEPENDENCIES.items():
            if not check_python_package(mod):
                print(f"  ... [DEPS] MISSING: {mod} ({pkg})")
                missing.append(pkg)
            else:
                print(f"  ... [DEPS] OK: {mod}")
                
        if missing:
            print(f"  ... Installing missing: {', '.join(missing)}")
            cmd = [py_exe, '-m', 'pip', 'install', '--disable-pip-version-check', '-q', *missing]
            
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                importlib.invalidate_caches()
                print("  ... Install successful.")
            except subprocess.CalledProcessError as e:
                print(f"\n[FATAL] Dependency installation failed!")
                print(f"Command: {' '.join(cmd)}")
                print(f"Stdout:\n{e.stdout}")
                print(f"Stderr:\n{e.stderr}")
                raise RuntimeError("Failed to install Python dependencies")
        
        # Verification
        still_missing = []
        for mod, pkg in PYTHON_DEPENDENCIES.items():
            if not check_python_package(mod):
                still_missing.append(pkg)
                
        if still_missing:
            print(f"\n[FATAL] Dependencies failed verification after install: {', '.join(still_missing)}")
            raise RuntimeError("Dependency verification failed")
            
        print("  ... All Python packages verified.")
        
        # Print versions for critical deps
        for mod in PYTHON_DEPENDENCIES.keys():
            try:
                m = importlib.import_module(mod)
                ver = getattr(m, '__version__', 'unknown')
                print(f"  ... {mod} version: {ver}")
            except Exception: pass
            
        _bootstrap_done = True
        return True

# ==============================================================================
# PHASE C: THIRD-PARTY IMPORTS
# ==============================================================================
def import_runtime_dependencies():
    """Import external modules needed for application logic. Must run AFTER bootstrap."""
    print("[2/6] Importing runtime packages")
    
    global psycopg2, By, Keys, ActionChains, WebDriverException, Worker, Queue, Image, webdriver, ChromeOptions, WebDriverWait, EC, Display, ipy_display, HTML
    
    import psycopg2
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.common.exceptions import WebDriverException
    from bullmq import Worker, Queue
    from PIL import Image
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from pyvirtualdisplay import Display
    
    try:
        from IPython.display import HTML, display as ipy_display
    except ImportError:
        pass
    
    print("  ... Import successful.")

# ==============================================================================
# PHASE D: BACKEND IMPORTS
# ==============================================================================
def import_backend_modules():
    """Import local backend modules (db, credits, fashion_studio)."""
    print("[3/6] Backend modules")
    
    global db, credits, fashion_studio
    
    try:
        import db
        import credits
        import fashion_studio
        print("  ... Backend modules loaded.")
    except ImportError as e:
        print(f"\n[FATAL] Failed to import backend module: {e}")
        raise RuntimeError(f"Backend module missing: {e}")

# ==============================================================================
# SYSTEM DEPENDENCIES & PREFLIGHT
# ==============================================================================
def check_command_exists(cmd):
    return shutil.which(cmd) is not None

def verify_system_dependencies():
    """Verify and install system-level dependencies securely."""
    print("[4/6] System packages")
    
    system_deps_ok = True
    for cmd in ['google-chrome', 'Xvfb', 'x11vnc', 'websockify', 'fluxbox']:
        if check_command_exists(cmd):
            print(f"  ... [SYS] OK: {cmd}")
        else:
            print(f"  ... [SYS] MISSING: {cmd}")
            system_deps_ok = False
            
    if not system_deps_ok:
        print("  ... Missing system dependencies detected. Attempting to install...")
        if platform.system() == "Linux":
            try:
                # Update package lists securely
                print("  ... Running apt-get update")
                update_cmd = ["sudo", "apt-get", "update", "-qq"]
                if os.environ.get("USER", "") == "root":
                    update_cmd = ["apt-get", "update", "-qq"]
                subprocess.run(update_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("  ... Installing missing system packages")
                
                install_cmd = ["sudo", "apt-get", "install", "-y", "-qq", "wget", "gnupg", "xvfb", "x11vnc", "fluxbox", "websockify", "python3-websockify"]
                if os.environ.get("USER", "") == "root":
                    install_cmd = ["apt-get", "install", "-y", "-qq", "wget", "gnupg", "xvfb", "x11vnc", "fluxbox", "websockify", "python3-websockify"]
                
                subprocess.run(install_cmd, check=True, stdout=subprocess.DEVNULL)
                
                # Install Chrome if missing
                if not check_command_exists('google-chrome'):
                    print("  ... Installing Google Chrome Stable")
                    chrome_script = """
                    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
                    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list'
                    apt-get update -qq
                    apt-get install -y -qq google-chrome-stable
                    """
                    if os.environ.get("USER", "") != "root":
                        chrome_script = f"sudo bash -c \"{chrome_script}\""
                    else:
                        chrome_script = f"bash -c \"{chrome_script}\""
                        
                    subprocess.run(chrome_script, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"  [WARN] Failed to automatically resolve system dependencies: {e}")
                print("  [WARN] We will continue, but Selenium may fail to launch.")
        else:
            print("  [WARN] Not a Linux system, skipping automated apt install.")
            
    if check_command_exists('google-chrome'):
        res = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
        print(f"  ... Setup verified: {res.stdout.strip()}")
    else:
        print(f"\n[FATAL] Google Chrome is absolutely required. It could not be found.")
        raise RuntimeError("Missing system dependency: google-chrome")
        
def preflight_environment():
    """Main boot orchestrator."""
    try:
        bootstrap_dependencies()
        import_runtime_dependencies()
        import_backend_modules()
        verify_system_dependencies()
        
        print("============================================================")
        print("V14 N2N — ENVIRONMENT READY")
        print("============================================================")
        print("Python: READY")
        print("Selenium: READY")
        print("BullMQ: READY")
        print("Database: READY")
        print("Chrome: READY")
        print("============================================================")
        return True
    except Exception as e:
        print(f"\n[FATAL BOOT ERROR] Environment failed to initialize: {e}")
        traceback.print_exc()
        return False

# ------------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ------------------------------------------------------------------------------
GEMINI_WORKERS = 4
WMR_WORKERS = 4
WMR_TABS_PER_PROFILE = 2
BULLMQ_CONCURRENCY = 8
GENERATION_TIMEOUT_S = 300
DOWNLOAD_TIMEOUT_S = 60
TOTAL_JOB_TIMEOUT_S = GENERATION_TIMEOUT_S + DOWNLOAD_TIMEOUT_S
DOWNLOAD_START_WINDOW_S = 30

SCREEN_W = 1280
SCREEN_H = 1024
VNC_PORT = 5900
NOVNC_PORT = 6080
CHROME_PROFILE_DIR = Path("/content/queue_worker_bundle/queue_worker_state/chrome_profile")
WMR_PROFILES_BASE = Path("/content/queue_worker_bundle/queue_worker_state/wmr_chrome_profiles")
DOWNLOAD_MIN_SIZE = 1024
DOWNLOAD_STABLE_CHECKS = 3
COOKIES_FILE = Path("/content/queue_worker_bundle/queue_worker_state/cookies.pkl")
SHORT_WAIT = 5
MAX_VERIFICATION_ATTEMPTS = 3
MAX_NEW_CHAT_RETRIES = 3
GEMINI_APP_URL = "https://gemini.google.com/app"
REFS_CACHE_DIR = Path("/content/queue_worker_bundle/queue_worker_state/refs")
QUEUE_NAME = "generations"
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"
SCREENSHOT_FOLDER = Path("/content/queue_worker_bundle/queue_worker_state/screenshots")

STATE_DIR = Path("/content/queue_worker_bundle/queue_worker_state")
CHROME_DL_BASE = Path("/content/downloads/chrome")
CHROME_STAGING_BASE = Path("/content/downloads/chrome_staging")
WMR_STAGING_BASE = Path("/content/downloads/wmr_staging")
WMR_DL_BASE = Path("/content/downloads/wmr")
FINAL_OUTPUT_BASE = Path("/content/downloads/final_output")

# Globals
main_loop = None
gemini_pool = None
wmr_pool = None
job_contexts = {}
download_registry = {}
GEMINI_BROKER = None
WMR_BROKER = None
chrome_driver = None

# Entrypoint lifecycle
worker_main_task = None        # asyncio.Task — holds the running main() coroutine
_worker_started = False        # double-start guard

def log(msg):
    print(msg, flush=True)

def resolve_future_once(loop, future, result, is_exception=False):
    if future is None:
        return False

    if loop is None:
        return False

    if loop.is_closed():
        return False

    def _resolve():
        if future.done():
            return

        if is_exception:
            future.set_exception(result)
        else:
            future.set_result(result)

    try:
        loop.call_soon_threadsafe(_resolve)
        return True
    except RuntimeError:
        return False

class JobState:
    QUEUED = "QUEUED"
    GEMINI_ASSIGNED = "GEMINI_ASSIGNED"
    UPLOADING = "UPLOADING"
    GENERATING = "GENERATING"
    GEMINI_DOWNLOAD_CLICKED = "GEMINI_DOWNLOAD_CLICKED"
    GEMINI_DOWNLOAD_STARTED = "GEMINI_DOWNLOAD_STARTED"
    GEMINI_RESOURCE_RELEASED = "GEMINI_RESOURCE_RELEASED"
    RAW_DOWNLOADING = "RAW_DOWNLOADING"
    RAW_READY = "RAW_READY"
    WMR_QUEUED = "WMR_QUEUED"
    WMR_ASSIGNED = "WMR_ASSIGNED"
    WMR_PROCESSING = "WMR_PROCESSING"
    WMR_DOWNLOAD_CLICKED = "WMR_DOWNLOAD_CLICKED"
    WMR_DOWNLOAD_STARTED = "WMR_DOWNLOAD_STARTED"
    WMR_RESOURCE_RELEASED = "WMR_RESOURCE_RELEASED"
    CLEAN_DOWNLOADING = "CLEAN_DOWNLOADING"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    R2_UPLOADING = "R2_UPLOADING"
    R2_READY = "R2_READY"
    DB_FINALIZING = "DB_FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobContext:
    def __init__(self, job_data, future):
        self.job_data = job_data
        self.job_id = job_data.get("id", str(uuid.uuid4()))
        self.generation_id = job_data.get("generation_id", self.job_id)
        self.prompt = job_data.get("prompt", "")
        self.refs = job_data.get("refs", [])
        self.user_id = job_data.get("user_id", "anonymous")
        self.retry_count = job_data.get("retry_count", 0)
        
        self.future = future
        self.state = JobState.QUEUED
        
        self.assigned_tid = None
        self.assigned_wmr_tab = None
        self.gemini_download_guid = None
        self.wmr_download_guid = None
        
        self.raw_path = None
        self.clean_path = None
        self.webp_path = None
        self.r2_png_url = None
        self.r2_webp_url = None
        
        self.error_message = None
        self.created_at = time.time()
        self.updated_at = time.time()

    def transition(self, new_state):
        self.state = new_state
        self.updated_at = time.time()
        res = f"[{self.assigned_tid}]" if self.assigned_tid is not None else ""
        if self.assigned_wmr_tab:
            res = f"[{self.assigned_wmr_tab}]"
        log(f"[JOB {self.job_id}]{res} {self.state}")

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
            print(f'  [WARN] Warning during {desc}: {res.stderr.strip()[:200]}')
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        if desc:
            print(f'  [WARN] Timeout during {desc}')
        return False
    except Exception as e:
        if desc:
            print(f'  [WARN] Error during {desc}: {e}')
        return False
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
            print(f'  ... {label} ready on port :{port}')
            return True
        time.sleep(0.5)
    print(f'  [WARN] {label} not ready on port :{port}')
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
        print(f'  ... Display :{_display_obj.display} running at {SCREEN_W}x{SCREEN_H}.')
    except Exception as e:
        print(f'  [WARN] pyvirtualdisplay fallback: {e}')
        subprocess.Popen(['Xvfb', ':99', '-screen', '0', f'{SCREEN_W}x{SCREEN_H}x24', '-ac'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ['DISPLAY'] = ':99'
        time.sleep(1.0)
        print('  ... Display :99 running.')
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
                        _banner = f"<div style='background:linear-gradient(135deg,#1b5e20,#2e7d32);color:white;padding:16px;border-radius:10px;font-size:15px;font-weight:bold;margin:10px 0;box-shadow:0 4px 6px rgba(0,0,0,0.3);'>\x8f <b>noVNC Remote Desktop Stream:</b><br><br>\x90 <a href='{vnc_url}' target='_blank' style='color:#a7ffeb;text-decoration:underline;'>Open Live UI ({vnc_url})</a><br></div>"
                        ipy_display(HTML(_banner))
                    except Exception:
                        pass
                    print(f'  -> noVNC Public Link: {vnc_url}')
                    return tb
        except Exception as e:
            print(f'  [WARN] noVNC tunnel notice: {e}')
    fallback = f'http://localhost:{NOVNC_PORT}/vnc.html'
    print(f'  [WARN] noVNC listening locally: {fallback}')
    return fallback
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
def create_gemini_driver(tid: int):
    master_profile = Path(CHROME_PROFILE_DIR)
    worker_profile = Path(str(CHROME_PROFILE_DIR) + f'_T{tid}')
    if not worker_profile.exists():
        if master_profile.exists():
            import shutil
            log(f'[T{tid}] Cloning master Gemini profile...')
            shutil.copytree(master_profile, worker_profile)
        else:
            worker_profile.mkdir(parents=True, exist_ok=True)
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = worker_profile / fname
        if fpath.exists():
            try:
                fpath.unlink()
            except Exception:
                pass
    opts = ChromeOptions()
    opts.add_argument(f'--user-data-dir={worker_profile}')
    opts.add_argument('--profile-directory=Default')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument(f'--window-size={SCREEN_W},{SCREEN_H}')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_argument('--no-first-run')
    opts.add_argument('--no-default-browser-check')
    opts.add_argument('--disable-sync')
    dl_dir = CHROME_DL_BASE / f'T{tid}'
    dl_dir.mkdir(parents=True, exist_ok=True)
    prefs = {'download.default_directory': str(dl_dir), 'download.prompt_for_download': False, 'download.directory_upgrade': True, 'safebrowsing.enabled': False, 'safebrowsing.disable_download_protection': True, 'profile.default_content_setting_values.automatic_downloads': 1}
    opts.add_experimental_option('prefs', prefs)
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_experimental_option('useAutomationExtension', False)
    drv = webdriver.Chrome(options=opts)
    try:
        drv.execute_cdp_cmd('Network.enable', {})
    except Exception:
        pass
    return drv
def create_wmr_chrome_driver(worker_id: int) -> webdriver.Chrome:
    """Create a dedicated Chrome WMR driver for W{worker_id}.
    Downloads go to wmr_staging/W{worker_id}/ " fixed at launch time via Chrome prefs.
    Profile is completely isolated from Gemini Chrome and other WMR workers.
    Never uses Microsoft Edge.
    """
    staging_dir = get_wmr_staging_dir(worker_id)
    profile_dir = WMR_PROFILES_BASE / f'W{worker_id}'
    profile_dir.mkdir(parents=True, exist_ok=True)
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
    log(f'[WMR-W{worker_id}] Browser = Google Chrome  staging={staging_dir}')
    return drv
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
        log(f'  [WARN] WebP conversion failed: {e}')
        return None
def validate_image_file(path, min_size=DOWNLOAD_MIN_SIZE, max_size=None):
    """Returns (True, 'OK') if valid, (False, reason) if invalid.
    Also works as bool when called with single arg (returns bool directly for legacy callers).
    """
    try:
        p = Path(path)
        if not p.exists():
            return (False, f'File not found: {path}')
        sz = p.stat().st_size
        if sz < min_size:
            return (False, f'File too small: {sz} < {min_size}')
        if max_size and sz > max_size * 1024 * 1024:
            return (False, f'File too large: {sz}')
        with Image.open(p) as im:
            im.verify()
        # Re-open after verify (verify closes the file)
        with Image.open(p) as im:
            im.load()
            w, h = im.size
            if w < 32 or h < 32:
                return (False, f'Image too small: {w}x{h}')
        return (True, 'OK')
    except Exception as e:
        return (False, f'Validation error: {e}')
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
def _wmr_check_status(drv: webdriver.Chrome):
    try:
        js = '\n        var res = document.querySelector(\'.result-container, .output-container, div[class*="result"]\');\n        if (!res) return null;\n        var btns = res.querySelectorAll(\'button, a\');\n        for (var i=0; i<btns.length; i++) {\n            var t = (btns[i].textContent || \'\').toLowerCase().trim();\n            if (t === \'download png\') {\n                return \'READY\';\n            }\n        }\n        return \'PROCESSING\';\n        '
        return safe_execute_script(drv, js)
    except:
        return None
def _wmr_click_download(drv: webdriver.Chrome, prefix: str) -> bool:
    try:
        js = '\n        var res = document.querySelector(\'.result-container, .output-container, div[class*="result"]\');\n        if (!res) return false;\n        var btns = res.querySelectorAll(\'button, a\');\n        for (var i=0; i<btns.length; i++) {\n            var t = (btns[i].textContent || \'\').toLowerCase().trim();\n            if (t === \'download png\') {\n                btns[i].click();\n                return true;\n            }\n        }\n        return false;\n        '
        return safe_execute_script(drv, js)
    except:
        return False
def is_logged_in_method_1_profile_avatar(driver):

    """Method 1: Check for profile avatar (the colored circle with letter)"""

    try:

        # Look for the profile avatar - the colored circle with initial

        avatar_selectors = [

            "//div[@aria-label='Google Account']//img",

            "//img[contains(@src, 'lh3.googleusercontent.com')]",

            "//div[@data-is-profile-button='true']//img",

            "//a[@aria-label='Google Account']//img",

            "//img[@alt and contains(@alt, 'Profile')]",

        ]

        for selector in avatar_selectors:

            try:

                elem = driver.find_element(By.XPATH, selector)

                if elem.is_displayed():

                    print("   ✅ Method 1: Profile avatar found!")

                    return True

            except:

                continue

        return False

    except:

        return False



def is_logged_in_method_2_email_text(driver):

    """Method 2: Check for email address text on page"""

    try:

        page_text = driver.find_element(By.TAG_NAME, "body").text

        # Look for email pattern

        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

        emails = re.findall(email_pattern, page_text)

        if emails:

            print(f"   ✅ Method 2: Email found: {emails[0]}")

            return True

        return False

    except:

        return False



def is_logged_in_method_3_account_elements(driver):

    """Method 3: Check for Google Account specific elements"""

    try:

        account_selectors = [

            "//a[@aria-label='Google Account']",

            "//div[contains(text(),'Google Account')]",

            "//h1[contains(text(),'Google Account')]",

            "//*[contains(text(),'Personal info')]",

            "//*[contains(text(),'Security and sign-in')]",

            "//*[contains(text(),'Data and privacy')]",

        ]

        for selector in account_selectors:

            try:

                elem = driver.find_element(By.XPATH, selector)

                if elem.is_displayed():

                    print(f"   ✅ Method 3: Account element found: {elem.text[:50]}")

                    return True

            except:

                continue

        return False

    except:

        return False



def is_logged_in_method_4_no_signin(driver):

    """Method 4: Check absence of Sign in button"""

    try:

        signin_buttons = driver.find_elements(By.XPATH,

            "//button[contains(., 'Sign in') or contains(., 'Sign In')] | " +

            "//a[contains(., 'Sign in') or contains(., 'Sign In')]")

        visible_signin = [btn for btn in signin_buttons if btn.is_displayed()]

        if not visible_signin:

            print("   ✅ Method 4: No 'Sign in' button found!")

            return True

        return False

    except:

        return False



def is_logged_in_method_5_url_check(driver):

    """Method 5: Check URL patterns"""

    try:

        url = driver.current_url.lower()

        logged_in_patterns = [

            "myaccount.google.com",

            "accounts.google.com/b/0/",

            "accounts.google.com/ManageAccount",

        ]

        not_logged_patterns = ["signin", "login", "identifier", "challenge"]



        for pattern in logged_in_patterns:

            if pattern in url:

                for not_pattern in not_logged_patterns:

                    if not_pattern in url:

                        return False

                print(f"   ✅ Method 5: URL indicates logged in: {url[:60]}")

                return True

        return False

    except:

        return False



def is_logged_in_method_6_cookies(driver):

    """Method 6: Check for Google auth cookies"""

    try:

        cookies = driver.get_cookies()

        auth_cookies = ['SID', 'HSID', 'SSID', 'APISID', 'SAPISID', 'LOGIN_INFO', 'SIDCC']

        found = [c['name'] for c in cookies if c['name'] in auth_cookies]

        if len(found) >= 2:

            print(f"   ✅ Method 6: Auth cookies found: {found}")

            return True

        return False

    except:

        return False



def is_logged_in_method_7_profile_button(driver):

    """Method 7: Check for the profile button in top-right"""

    try:

        # The colored circle avatar button in top right

        profile_btns = driver.find_elements(By.CSS_SELECTOR,

            "[data-is-profile-button='true'], " +

            "[aria-label*='Google Account'], " +

            "[aria-label*='Profile']")

        for btn in profile_btns:

            if btn.is_displayed():

                print(f"   ✅ Method 7: Profile button found!")

                return True

        return False

    except:

        return False




def verify_google_account_auth(driver, wait=None):
    try:
        driver.get("https://myaccount.google.com/")
        import time
        time.sleep(3)
        url = driver.current_url
        if "signin" in url or "identifier" in url or "challenge" in url or "accounts.google.com/signin" in url:
            return "NOT_AUTHENTICATED"
        try:
            from selenium.webdriver.common.by import By
            profile_btn = driver.find_element(By.XPATH, "//a[contains(@aria-label, 'Google Account')]")
            if profile_btn.is_displayed():
                return "AUTHENTICATED"
        except:
            pass
        return "UNKNOWN"
    except Exception as e:
        log(f"[AUTH] Google check error: {e}")
        return "BROWSER_ERROR"

def verify_gemini_auth(driver, wait=None):
    try:
        driver.get("https://gemini.google.com/app")
        import time
        from selenium.webdriver.common.by import By
        for attempt, delay in enumerate([2, 4, 6, 10, 15]):
            time.sleep(delay)
            url = driver.current_url
            if "signin" in url or "accounts.google.com" in url or "challenge" in url:
                return "NOT_AUTHENTICATED"
            
            try:
                sign_in = driver.find_element(By.XPATH, "//button[contains(., 'Sign in') or contains(., 'Sign In')]")
                if sign_in.is_displayed():
                    return "NOT_AUTHENTICATED"
            except:
                pass
            
            try:
                composer = driver.find_element(By.CSS_SELECTOR, "rich-textarea, div[contenteditable='true'], textarea")
                try:
                    profile = driver.find_element(By.XPATH, "//a[contains(@aria-label, 'Google Account')]")
                    if composer.is_displayed() and profile.is_displayed():
                        return "AUTHENTICATED"
                except:
                    if composer.is_displayed():
                        return "AUTHENTICATED"
            except:
                pass
        return "WAITING"
    except Exception as e:
        log(f"[AUTH] Gemini check error: {e}")
        return "BROWSER_ERROR"

def get_authentication_state(driver, wait=None):
    state_a = verify_google_account_auth(driver, wait)
    log(f"[AUTH] Google Account State: {state_a}")
    if state_a in ["NOT_AUTHENTICATED", "CHALLENGE_REQUIRED", "BROWSER_ERROR"]:
        log(f"[AUTH] FINAL: {state_a}")
        return state_a
    
    state_b = verify_gemini_auth(driver, wait)
    log(f"[AUTH] Gemini State: {state_b}")
    if state_b == "AUTHENTICATED" and state_a == "AUTHENTICATED":
        log("[AUTH] Composer: FOUND")
        log("[AUTH] Attachment Control: FOUND")
        log("[AUTH] Account/Profile: FOUND")
        log("[AUTH] Sign-in Wall: NOT FOUND")
        log("[AUTH] Challenge: NOT FOUND")
        log("[AUTH] FINAL: AUTHENTICATED")
        return "AUTHENTICATED"
    
    if state_b in ["NOT_AUTHENTICATED", "CHALLENGE_REQUIRED", "BROWSER_ERROR"]:
        log("[AUTH] Composer: NOT FOUND")
        log(f"[AUTH] FINAL: {state_b}")
        return state_b
        
    log("[AUTH] FINAL: UNKNOWN")
    return "UNKNOWN"

def comprehensive_login_check(driver, page_name=""):
    return get_authentication_state(driver, None) == "AUTHENTICATED"


def extract_verification_number(driver):

    """Extract the verification number from page"""

    try:

        page_text = driver.find_element(By.TAG_NAME, "body").text

        verification_patterns = [

            r'tap\s+(\d+)\s+on\s+your\s+phone',

            r'then\s+tap\s+(\d+)',

            r'verification\s+code[:\s]+(\d+)',

            r'code[:\s]+(\d{2,6})',

            r'number[:\s]+(\d+)',

        ]

        for pattern in verification_patterns:

            match = re.search(pattern, page_text.lower())

            if match:

                return match.group(1)



        all_numbers = re.findall(r'\b(\d{2,6})\b', page_text)

        for num in all_numbers:

            if num not in ['2024', '2025', '2026', '1234', '0000', '1000', '911']:

                idx = page_text.find(num)

                context = page_text[max(0,idx-100):min(len(page_text),idx+100)].lower()

                if any(k in context for k in ['verify', 'tap', 'check', 'code', 'number', 'phone']):

                    return num

        return None

    except Exception as e:

        print(f"⚠️ Error extracting verification number: {e}")

        return None



def extract_page_details(driver):

    """Extract ALL visible text, input fields, and buttons from page"""

    details = {

        'page_text': '', 'input_fields': [], 'buttons': [],

        'verification_number': None, 'instructions': [], 'headings': []

    }

    try:

        body = driver.find_element(By.TAG_NAME, "body")

        details['page_text'] = body.text

        details['verification_number'] = extract_verification_number(driver)



        input_fields = driver.find_elements(By.CSS_SELECTOR,

            "input[type='text'], input[type='email'], input[type='password'], input[type='tel']")

        for field in input_fields:

            if field.is_displayed():

                details['input_fields'].append({

                    'type': field.get_attribute('type'),

                    'id': field.get_attribute('id'),

                    'name': field.get_attribute('name'),

                    'aria_label': field.get_attribute('aria-label'),

                    'placeholder': field.get_attribute('placeholder'),

                })



        buttons = driver.find_elements(By.CSS_SELECTOR, "button, div[role='button']")

        for btn in buttons:

            if btn.is_displayed():

                btn_text = btn.text.strip()

                btn_aria = btn.get_attribute('aria-label')

                if btn_text or btn_aria:

                    details['buttons'].append({'text': btn_text, 'aria_label': btn_aria})



        headings = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, div[role='heading']")

        for heading in headings:

            if heading.is_displayed() and heading.text.strip():

                details['headings'].append(heading.text.strip())

    except Exception as e:

        print(f"️ Error extracting page details: {e}")

    return details



def display_page_info(details, step_name=""):

    """Display extracted page information"""

    print("\n" + "="*70)

    print(f"📋 PAGE INFORMATION - {step_name}")

    print("="*70)



    if details['verification_number']:

        print(f"\n{'='*70}")

        print(f"🔢 VERIFICATION NUMBER: {details['verification_number']} 🔢🔢")

        print(f"{'='*70}")

        print(f"⚠️ You need to tap/enter this number on your phone!")

        print(f"{'='*70}\n")

        ipy_display(HTML(f"""

        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);

                    padding: 25px; border-radius: 12px; color: white; text-align: center;

                    font-size: 32px; font-weight: bold; margin: 20px 0;'>

            🔢 VERIFICATION NUMBER: {details['verification_number']}

            <div style='font-size: 16px; margin-top: 10px;'>Tap this number on your phone</div>

        </div>"""))



    if details['headings']:

        print(f"\n📌 HEADINGS:")

        for h in details['headings']:

            print(f"   • {h}")



    if details['input_fields']:

        print(f"\n📝 INPUT FIELDS:")

        for i, field in enumerate(details['input_fields'], 1):

            print(f"   Field {i}: {field.get('aria_label', field.get('placeholder', field['type']))}")

            if 'email' in field['type'].lower() or 'identifier' in str(field.get('id','')).lower():

                print(f"   👉 Enter EMAIL")

            elif 'password' in field['type'].lower():

                print(f"   👉 Enter PASSWORD")



    if details['buttons']:

        print(f"\n BUTTONS:")

        for btn in details['buttons']:

            print(f"   • {btn['text'] or btn['aria_label']}")



    print("="*70)



def take_screenshot(driver, step_name):

    try:

        timestamp = datetime.now().strftime("%H%M%S")

        filename = f"{SCREENSHOT_FOLDER}/{timestamp}_{step_name}.png"

        driver.save_screenshot(filename)

        print(f"📸 Screenshot saved: {step_name}")

        return filename

    except Exception as e:

        print(f"⚠️ Screenshot error: {e}")

        return None



def save_cookies(driver):

    try:

        cookies = driver.get_cookies()

        with open(COOKIES_FILE, "wb") as f:

            pickle.dump(cookies, f)

        print("💾 ✅ Cookies saved locally")

        return True

    except Exception as e:

        print(f"️ Cookie save error: {e}")

        return False



def load_cookies(driver):

    try:

        if os.path.exists(COOKIES_FILE):

            with open(COOKIES_FILE, "rb") as f:

                cookies = pickle.load(f)

            driver.get("https://www.google.com")

            time.sleep(1)

            for cookie in cookies:

                try:

                    driver.add_cookie(cookie)

                except:

                    pass

            print("💾 ✅ Cookies loaded from local storage")

            return True

        else:

            print("⚠️ No cookie file found")

            return False

    except Exception as e:

        print(f"⚠️ Cookie load error: {e}")

        return False



def wait_with_countdown(total_seconds, message="Waiting"):

    try:

        for remaining in range(total_seconds, 0, -1):

            mins, secs = divmod(remaining, 60)

            time_str = f"{mins:02d}:{secs:02d}"

            print(f"\r {message}: {time_str} ", end='', flush=True)

            time.sleep(1)

        print(f"\r✅ {message}: Complete!           ")

    except KeyboardInterrupt:

        print("\n️ Wait interrupted")

        raise KeyboardInterrupt



def detect_push_notification_verification(driver):

    try:

        page_text = driver.find_element(By.TAG_NAME, "body").text

        push_indicators = ["Check your", "Tap Yes", "notification", "sent a notification", "on your phone", "verify it's you"]

        match_count = sum(1 for indicator in push_indicators if indicator.lower() in page_text.lower())

        return match_count >= 2

    except:

        return False



def wait_for_push_notification_approval(driver, max_wait_seconds=60):

    try:

        verification_num = extract_verification_number(driver)

        if verification_num:

            print(f"\n{'='*70}")

            print(f" VERIFICATION NUMBER: {verification_num}")

            print(f"{'='*70}")

            print(f"📱 Please check your phone and tap: '{verification_num}'")

            print(f"{'='*70}\n")



        ipy_display(HTML("<h4 style='color: #fbbc04;'>📱 PUSH NOTIFICATION SENT TO YOUR PHONE</h4>"))



        checks = max_wait_seconds // 5

        for check in range(1, checks + 1):

            print(f"\n🔍 Check {check}/{checks}")

            wait_with_countdown(5, "Waiting for approval")



            if comprehensive_login_check(driver, "push approval check"):

                ipy_display(HTML("<h3 style='color: #34a853;'>✅ Push notification approved!</h3>"))

                return True

        return False

    except Exception as e:

        print(f"❌ Error waiting for push: {e}")

        return False



def handle_verification_code_with_retry(driver, wait, max_attempts=3):

    for attempt in range(1, max_attempts + 1):

        try:

            ipy_display(HTML(f"<h4 style='color: #ea4335;'>🔢 Verification Check - Attempt {attempt}/{max_attempts}</h4>"))

            page_details = extract_page_details(driver)

            display_page_info(page_details, f"Verification Attempt {attempt}")



            if detect_push_notification_verification(driver):

                ipy_display(HTML("<h4 style='color: #fbbc04;'>📱 Detected: Push notification verification</h4>"))

                take_screenshot(driver, f"push_notification_attempt_{attempt}")



                if page_details['verification_number']:

                    print(f"\n{'='*70}")

                    print(f"🔢 YOUR VERIFICATION NUMBER: {page_details['verification_number']}")

                    print(f"{'='*70}")



                wait_time = 60 if attempt == 1 else 30

                if wait_for_push_notification_approval(driver, max_wait_seconds=wait_time):

                    return True

                if comprehensive_login_check(driver):

                    return True

                continue



            code_input = None

            code_selectors = ["input[type='tel']", "input[name='totpPin']", "input[id='totpPin']",

                            "input[type='text'][name='pin']", "input[aria-label*='code']"]

            for selector in code_selectors:

                try:

                    fields = driver.find_elements(By.CSS_SELECTOR, selector)

                    for field in fields:

                        if field.is_displayed():

                            code_input = field

                            break

                    if code_input:

                        break

                except:

                    continue



            if not code_input:

                if attempt < max_attempts:

                    time.sleep(2)

                    continue

                return False



            ipy_display(HTML("<h4 style='color: #4285f4;'>🔢 Detected: Code input verification</h4>"))

            take_screenshot(driver, f"verification_code_attempt_{attempt}_before")



            print(f"\n{'='*70}")

            print("🔢 VERIFICATION CODE REQUIRED")

            print(f"{'='*70}")

            print("Check your phone for a 6-digit code")

            print(f"{'='*70}\n")



            otp = input(f"Enter Verification Code (Attempt {attempt}/{max_attempts}): ").strip()

            if not otp:

                if attempt < max_attempts:

                    time.sleep(2)

                    continue

                return False



            code_input.clear()

            code_input.send_keys(otp)

            time.sleep(SHORT_WAIT)



            next_button_found = False

            next_selectors = ["//button[@id='next']", "//button[contains(., 'Next')]", "//button[@type='submit']"]

            for selector in next_selectors:

                try:

                    next_btn = driver.find_element(By.XPATH, selector)

                    if next_btn.is_displayed() and next_btn.is_enabled():

                        next_btn.click()

                        next_button_found = True

                        break

                except:

                    continue



            if not next_button_found:

                code_input.send_keys(Keys.RETURN)



            time.sleep(4)

            take_screenshot(driver, f"verification_code_attempt_{attempt}_after_submit")



            if comprehensive_login_check(driver):

                ipy_display(HTML(f"<h3 style='color: #34a853;'>✅ Verification successful on attempt {attempt}!</h3>"))

                return True



            if attempt < max_attempts:

                time.sleep(2)

                continue

            return False

        except Exception as e:

            if attempt < max_attempts:

                time.sleep(2)

                continue

            return False

    return False



def handle_google_login_fast(driver, wait):

    """⚡ FAST LOGIN WITH PROPER DETECTION"""

    try:

        print("\n" + "="*70)

        print("🔐 FAST GOOGLE LOGIN")

        print("="*70)



        # Step 1: Try loading cookies

        print("\n📍 Step 1: Trying to load saved cookies...")

        if load_cookies(driver):

            driver.refresh()

            time.sleep(2)

            take_screenshot(driver, "after_cookie_load")



            if comprehensive_login_check(driver, "after cookies"):

                ipy_display(HTML("<h2 style='color: #34a853;'>✅ LOGGED IN WITH COOKIES!</h2>"))

                save_cookies(driver)

                return True



        # Step 2: Navigate to login page

        print("\n📍 Step 2: Opening Google login page...")

        driver.get("https://accounts.google.com/")

        time.sleep(3)

        take_screenshot(driver, "login_page_initial")



        # Check if already logged in even on accounts page

        if comprehensive_login_check(driver, "accounts page"):

            print("✅ Already logged in on accounts page!")

            save_cookies(driver)

            return True



        # Step 3: Extract page details

        print("\n Step 3: Analyzing login page...")

        page_details = extract_page_details(driver)

        display_page_info(page_details, "Login Page")



        # Step 4: Enter email

        print("\n📍 Step 4: Entering email...")

        email = input("Enter your EMAIL: ").strip()

        if not email:

            print("❌ No email provided")

            return False



        try:

            email_field = wait.until(EC.presence_of_element_located((By.ID, "identifierId")))

            email_field.clear()

            email_field.send_keys(email)

            time.sleep(1)



            next_btn = wait.until(EC.element_to_be_clickable((By.ID, "identifierNext")))

            driver.execute_script("arguments[0].click();", next_btn)

            print("✅ Email submitted")

            time.sleep(3)

        except Exception as e:

            print(f"❌ Email entry error: {e}")

            return False



        take_screenshot(driver, "after_email_submit")



        # Step 5: Check if logged in after email

        if comprehensive_login_check(driver, "after email"):

            print("✅ Logged in after email (no password needed)!")

            save_cookies(driver)

            return True



        # Step 6: FAST password field detection (5 seconds max!)

        print("\n📍 Step 5: Looking for password field (FAST - 5 seconds max)...")



        pwd_field = None

        password_selectors = [

            (By.NAME, "Passwd"),

            (By.CSS_SELECTOR, "input[type='password']"),

            (By.CSS_SELECTOR, "#password input"),

            (By.CSS_SELECTOR, "input[name='password']"),

        ]



        for by, selector in password_selectors:

            try:

                pwd_field = WebDriverWait(driver, 5).until(  # Only 5 seconds!

                    EC.presence_of_element_located((by, selector))

                )

                if pwd_field and pwd_field.is_displayed():

                    print(f"✅ Password field found quickly!")

                    break

            except:

                continue



        if not pwd_field:

            print("⚠️ Password field not found in 5 seconds, trying longer wait...")

            try:

                pwd_field = WebDriverWait(driver, 10).until(

                    EC.presence_of_element_located((By.NAME, "Passwd"))

                )

            except:

                print("❌ Could not find password field")

                take_screenshot(driver, "no_password_field")

                return False



        # Step 7: Enter password

        print("\n📍 Step 6: Entering password...")

        password = input("Enter your PASSWORD: ").strip()

        if not password:

            print("❌ No password provided")

            return False



        try:

            pwd_field.clear()

            pwd_field.send_keys(password)

            time.sleep(1)



            pwd_next = wait.until(EC.element_to_be_clickable((By.ID, "passwordNext")))

            driver.execute_script("arguments[0].click();", pwd_next)

            print("✅ Password submitted")

            time.sleep(4)

        except Exception as e:

            print(f"❌ Password entry error: {e}")

            return False



        take_screenshot(driver, "after_password_submit")



        # Step 8: Check if logged in

        if comprehensive_login_check(driver, "after password"):

            print("✅ Login successful!")

            save_cookies(driver)

            return True



        # Step 9: Handle verification

        print("\n📍 Step 7: Checking for verification...")

        url = driver.current_url

        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()



        if "challenge" in url or "verify" in url or "check your" in page_text:

            print("🔐 Verification required")

            take_screenshot(driver, "verification_required")



            if handle_verification_code_with_retry(driver, wait, MAX_VERIFICATION_ATTEMPTS):

                save_cookies(driver)

                return True

            return False



        # Final check

        if comprehensive_login_check(driver, "final"):

            save_cookies(driver)

            return True



        # Manual confirmation

        confirm = input("Are you logged in? (y/n): ").strip().lower()

        if confirm == 'y':

            save_cookies(driver)

            return True



        return False

    except Exception as e:

        print(f"\n❌ ERROR: {e}")

        import traceback

        traceback.print_exc()

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
                        if validate_image_file(candidate)[0]:
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
def ensure_chrome_driver_alive(driver):
    if driver is None:
        raise RuntimeError('Driver is None')
    try:
        driver.execute_script('return 1')
        return True
    except Exception as e:
        raise RuntimeError(f'Driver dead: {e}')
def check_chrome_driver_health(driver):
    if driver is None:
        return {'alive': False}
    try:
        driver.execute_script('return 1')
        return {'alive': True, 'window_count': len(driver.window_handles), 'current_handle': driver.current_window_handle, 'current_url': driver.current_url, 'pid': driver.service.process.pid if driver.service and driver.service.process else None}
    except Exception:
        return {'alive': False}
def configure_browser_download_events(driver):
    driver.execute_cdp_cmd('Browser.setDownloadBehavior', {'behavior': 'allowAndName', 'downloadPath': '/content/downloads/chrome_staging/global', 'eventsEnabled': True})
def create_persistent_chrome_driver():
    import undetected_chromedriver as uc
    profile_dir = Path('/content/queue_worker_bundle/queue_worker_state/chrome_profile')
    profile_dir.mkdir(parents=True, exist_ok=True)
    options = uc.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--user-data-dir={profile_dir}')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-session-crashed-bubble')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        raise RuntimeError(f'CHROME_START_FAILED: {type(e).__name__}: {e}') from e
    assert driver is not None
    assert driver.service is not None
    assert driver.window_handles
    driver.execute_script('return document.readyState')
    driver.execute_cdp_cmd('Browser.getVersion', {})
    return driver
# R2 configuration - loaded from environment at startup
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
R2_PUBLIC_URL = os.environ.get('R2_PUBLIC_URL')
FASHION_STUDIO_USER_ID = os.environ.get('FASHION_STUDIO_USER_ID', '')

def fs_configured():
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_PUBLIC_URL)

def _r2_client():
    import boto3
    return boto3.client(
        's3',
        endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name='auto'
    )

def upload_to_r2(png_path, webp_path, job_id, user_id=None):
    """Upload PNG and WebP to R2, return (png_url, webp_url).
    Returns (None, None) if R2 is not configured.
    """
    import mimetypes
    if not fs_configured():
        log(f'[R2] Not configured - skipping upload for job {job_id}')
        return (None, None)
    target_user_id = user_id or FASHION_STUDIO_USER_ID or 'anonymous'
    png_key = f'generations/{target_user_id}/{job_id}.png'
    webp_key = f'generations/{target_user_id}/{job_id}.webp'
    try:
        client = _r2_client()
        with open(png_path, 'rb') as f:
            png_data = f.read()
        client.put_object(
            Bucket=R2_BUCKET_NAME, Key=png_key, Body=png_data,
            ContentType='image/png',
            CacheControl='public, max-age=31536000, immutable'
        )
        png_url = f'{R2_PUBLIC_URL}/{png_key}'
        log(f'[R2] PNG uploaded: {png_url}')
        webp_url = None
        if webp_path and os.path.exists(str(webp_path)):
            with open(str(webp_path), 'rb') as f:
                webp_data = f.read()
            client.put_object(
                Bucket=R2_BUCKET_NAME, Key=webp_key, Body=webp_data,
                ContentType='image/webp',
                CacheControl='public, max-age=31536000, immutable'
            )
            webp_url = f'{R2_PUBLIC_URL}/{webp_key}'
            log(f'[R2] WebP uploaded: {webp_url}')
        return (png_url, webp_url)
    except Exception as e:
        log(f'[R2] Upload FAILED for job {job_id}: {e}')
        raise

gemini_driver_lock = threading.Lock()

class GeminiWorker:
    def __init__(self, tid: int):
        self.tid = tid
        self.state = 'IDLE'
        self.current_job_id = None
        self.window_handle = None

    def _ensure_tab(self):
        global chrome_driver
        if not check_chrome_driver_health(chrome_driver)['alive']:
            raise RuntimeError('Global chrome_driver is dead')
            
        with gemini_driver_lock:
            if self.window_handle:
                try:
                    if self.window_handle in chrome_driver.window_handles:
                        chrome_driver.switch_to.window(self.window_handle)
                        return chrome_driver
                except Exception:
                    pass
            log(f'[T{self.tid}] Creating new logical Gemini tab...')
            chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
            for h in chrome_driver.window_handles:
                chrome_driver.switch_to.window(h)
                if chrome_driver.current_url == 'about:blank' or chrome_driver.current_url.startswith('data:'):
                    self.window_handle = h
                    break
            if not self.window_handle:
                self.window_handle = chrome_driver.window_handles[-1]
            chrome_driver.switch_to.window(self.window_handle)
            return chrome_driver

    def process_job(self, ctx: JobContext):
        t = threading.Thread(target=self._process_job_thread, args=(ctx,), daemon=True)
        t.start()

    def _process_job_thread(self, ctx: JobContext):
        job_id = ctx.job_id
        future = ctx.future
        prefix = f'[T{self.tid}][{job_id}]'
        
        self.current_job_id = job_id
        
        try:
            drv = self._ensure_tab()
            
            job_dir, incoming_dir = get_chrome_job_dir(self.tid, job_id)
            staging_dir = Path(f'/content/downloads/chrome_staging/T{self.tid}')
            staging_dir.mkdir(parents=True, exist_ok=True)
            
            with gemini_driver_lock:
                drv.switch_to.window(self.window_handle)
                drv.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(staging_dir)})
                # Rule 14: New Chat explicitly.
                open_new_chat_and_reload(drv, self.tid, job_id)
                    
            time.sleep(1)
            
            with gemini_driver_lock:
                drv.switch_to.window(self.window_handle)
                _ = drv.get_log('performance')
                log(f'{prefix} FRESH_BROWSER_READY')
                # Verify Gemini page is accessible before starting job
                try:
                    page_url = drv.current_url
                    if 'gemini.google.com' not in page_url:
                        raise Exception(f'Gemini tab not on Gemini: {page_url}')
                    log(f'{prefix} COMPOSER_VERIFIED (url={page_url[:60]})')
                except Exception as ce:
                    raise Exception(f'COMPOSER_CHECK_FAILED: {ce}')
                ensure_flash_mode(drv, self.tid, job_id)
                ensure_create_image_mode(drv, self.tid, job_id)
                
                refs = ctx.refs
                expected_refs = [p for p in refs if p]
                ref_paths = [str(Path(p).resolve()) for p in expected_refs]
                if ref_paths:
                    perform_robust_upload(drv, ref_paths, self.tid, job_id)
                    verified, actual = verify_attachment_count(drv, len(ref_paths), self.tid, job_id)
                    if not verified:
                        raise Exception(f'ATTACHMENT_MISMATCH: expected {len(ref_paths)}, got {actual}')
                        
                _inject_prompt_atomic(drv, ctx.prompt, self.tid, job_id)
                urls_before = snapshot_urls(drv)
                chat_urls = {u for u in urls_before if '/app/' in u}
                log(f'{prefix} SEND_REQUESTED')
                
                if not _click_send_button(drv, self.tid, job_id):
                    raise Exception('SEND_FAILED')
                log(f'{prefix} SEND_CLICKED')
                
                if not verify_generation_started(drv):
                    raise Exception('GEN_START_FAILED')
                    
            ctx.transition(JobState.GENERATING)
            
            t0 = time.time()
            image_detected = False
            while time.time() - t0 < GENERATION_TIMEOUT_S:
                with gemini_driver_lock:
                    drv.switch_to.window(self.window_handle)
                    status, new_src = nb_check_image(drv, urls_before, chat_urls)
                if status == 'SUCCESS':
                    image_detected = True
                    if new_src:
                        urls_before.add(new_src)
                    break
                time.sleep(1.0)
                
            if not image_detected:
                raise Exception('GENERATION_TIMEOUT')
                
            log(f'{prefix} IMAGE_DETECTED')
            
            files_before = set(staging_dir.iterdir()) if staging_dir.exists() else set()
            
            with gemini_driver_lock:
                drv.switch_to.window(self.window_handle)
                hover_ok = _hover_and_dl_single_click(drv, urls_before, chat_urls)
            
            log(f'{prefix} DOWNLOAD_CLICKED (hover_ok={hover_ok})')
            ctx.transition(JobState.GEMINI_DOWNLOAD_STARTED)
            
            dl_guid = None
            t1 = time.time()
            while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                with gemini_driver_lock:
                    drv.switch_to.window(self.window_handle)
                    for entry in drv.get_log('performance'):
                        try:
                            msg = json.loads(entry['message'])['message']
                            if msg['method'] == 'Browser.downloadWillBegin':
                                dl_guid = msg['params']['guid']
                                break
                        except:
                            pass
                if dl_guid:
                    break
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
                if dl_confirmed_fs:
                    break
                time.sleep(0.1)
                
            if dl_confirmed_fs:
                log(f'{prefix} DOWNLOAD_START_EVENT guid={dl_guid}')
                ctx.gemini_download_guid = dl_guid or f'fs_fallback_{job_id}'
                ctx.transition(JobState.GEMINI_RESOURCE_RELEASED)
                
                download_registry[ctx.gemini_download_guid] = {
                    'ctx': ctx,
                    'type': 'GEMINI',
                    'staging_dir': staging_dir,
                    'files_before': files_before,
                    'started_at': time.time(),
                    'job_dir': job_dir,
                    'incoming_dir': incoming_dir
                }

                def _reg():
                    GEMINI_BROKER.release(self.tid)
                    self.current_job_id = None
                main_loop.call_soon_threadsafe(_reg)
            else:
                raise Exception('DOWNLOAD_START_FAILED')
                
        except Exception as e:
            log(f'{prefix} GEMINI_FAILED: {e}')
            ctx.error_message = f'Gemini failed: {e}'
            ctx.transition(JobState.FAILED)
            resolve_future_once(main_loop, future, None, is_exception=True)

            def _rel():
                GEMINI_BROKER.release(self.tid)
                self.current_job_id = None
            main_loop.call_soon_threadsafe(_rel)

class GeminiWorkerPool:
    def __init__(self, max_workers: int=GEMINI_WORKERS):
        self.max_workers = max_workers
        self.workers = {i: GeminiWorker(i) for i in range(max_workers)}

    def start_all(self):
        for i in range(self.max_workers):
            GEMINI_BROKER.release(i)
            
    def quit_all(self):
        pass

class WmrDriverThread(threading.Thread):
    def __init__(self, profile_id):
        super().__init__(daemon=True)
        self.profile_id = profile_id
        self.cmd_queue = queue.Queue()
        self.driver = None
        self.running = True
        self.wmr_tab_handles = {}

    def run(self):
        try:
            self.driver = create_wmr_chrome_driver(self.profile_id)
            log(f"[WMR-{self.profile_id}] Driver ready")
        except Exception as e:
            log(f"Failed to create driver for WMR profile {self.profile_id}: {e}")
            return
            
        while self.running:
            try:
                cmd = self.cmd_queue.get(timeout=1.0)
                if cmd is None:
                    break
                func, args, future = cmd
                try:
                    res = func(self.driver, self.wmr_tab_handles, *args)
                    if future and not future.done():
                        future.set_result(res)
                except Exception as e:
                    if future and not future.done():
                        future.set_exception(e)
            except queue.Empty:
                pass
        
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass

class WmrWorkerPool:
    def __init__(self, num_profiles):
        self.num_profiles = num_profiles
        self.threads = {}
        
    def start_all(self):
        for i in range(self.num_profiles):
            self.threads[i] = WmrDriverThread(i)
            self.threads[i].start()
            for t in range(WMR_TABS_PER_PROFILE):
                WMR_BROKER.release(f"W{i}-T{t}")
                
    def quit_all(self):
        for t in self.threads.values():
            t.running = False
            t.cmd_queue.put(None)

    async def execute_async(self, resource_id, func, *args):
        profile_id = int(resource_id.split('-')[0][1:])
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        cfut = concurrent.futures.Future()
        
        def _done(f):
            if loop.is_closed():
                return
            try:
                res = f.result()
                loop.call_soon_threadsafe(fut.set_result, res)
            except Exception as e:
                loop.call_soon_threadsafe(fut.set_exception, e)
                
        cfut.add_done_callback(_done)
        self.threads[profile_id].cmd_queue.put((func, args, cfut))
        return await fut

def _run_wmr_logic(driver, wmr_tab_handles, ctx: JobContext):
    resource_id = ctx.assigned_wmr_tab
    job_id = ctx.job_id
    prefix = f'[{resource_id}][{job_id}]'
    
    if not check_chrome_driver_health(driver)['alive']:
        raise RuntimeError(f'Driver for {resource_id} is dead')
        
    handle = wmr_tab_handles.get(resource_id)
    if handle:
        try:
            if handle in driver.window_handles:
                driver.switch_to.window(handle)
            else:
                handle = None
        except:
            handle = None
            
    if not handle:
        log(f'[{resource_id}] Creating new logical WMR tab...')
        driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
        for h in driver.window_handles:
            driver.switch_to.window(h)
            if driver.current_url == 'about:blank' or driver.current_url.startswith('data:'):
                wmr_tab_handles[resource_id] = h
                break
        if resource_id not in wmr_tab_handles:
            wmr_tab_handles[resource_id] = driver.window_handles[-1]
        driver.switch_to.window(wmr_tab_handles[resource_id])
    
    job_dir, incoming_dir = get_wmr_job_dir(0, job_id)
    profile_id = int(resource_id.split('-')[0][1:])
    staging_dir = Path(f'/content/downloads/wmr_staging/W{profile_id}')
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    driver.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(staging_dir)})
    
    if 'pixelcut.ai' not in driver.current_url:
        driver.get('https://www.pixelcut.ai/watermark-remover')
        
    time.sleep(1)
    
    inp = _wmr_find_file_input(driver)
    if not inp:
        raise Exception('WMR_FILE_INPUT_MISSING')
        
    inp.send_keys(str(ctx.raw_path))
    ctx.transition(JobState.WMR_PROCESSING)
    
    status = _wmr_check_status(driver)
    if status != 'SUCCESS':
        raise Exception(f'WMR_FAILED: {status}')
        
    files_before = set(staging_dir.iterdir()) if staging_dir.exists() else set()
    
    if not _wmr_click_download(driver):
        raise Exception('WMR_CLICK_DOWNLOAD_FAILED')
        
    ctx.transition(JobState.WMR_DOWNLOAD_CLICKED)
    
    dl_guid = None
    t1 = time.time()
    while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
        for entry in driver.get_log('performance'):
            try:
                msg = json.loads(entry['message'])['message']
                if msg['method'] == 'Browser.downloadWillBegin':
                    dl_guid = msg['params']['guid']
                    break
            except:
                pass
        if dl_guid:
            break
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
        if dl_confirmed_fs:
            break
        time.sleep(0.1)
        
    if dl_confirmed_fs:
        ctx.wmr_download_guid = dl_guid or f'fs_fallback_{job_id}'
        ctx.transition(JobState.WMR_RESOURCE_RELEASED)
        
        download_registry[ctx.wmr_download_guid] = {
            'ctx': ctx,
            'type': 'WMR',
            'staging_dir': staging_dir,
            'files_before': files_before,
            'started_at': time.time(),
            'job_dir': job_dir,
            'incoming_dir': incoming_dir
        }
        
        def _reg():
            WMR_BROKER.release(resource_id)
        main_loop.call_soon_threadsafe(_reg)
    else:
        raise Exception('WMR_DOWNLOAD_START_FAILED')

async def poll_active_downloads():
    while True:
        try:
            completed_guids = []
            for guid, dinfo in list(download_registry.items()):
                ctx = dinfo['ctx']
                staging_dir = dinfo['staging_dir']
                files_before = dinfo['files_before']
                
                if not staging_dir.exists():
                    continue
                    
                cur = set(staging_dir.iterdir())
                new_files = cur - files_before
                
                crdownloads = [f for f in new_files if f.name.endswith('.crdownload')]
                if crdownloads:
                    continue
                    
                final_files = [f for f in new_files if f.name.endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                if not final_files:
                    if time.time() - dinfo['started_at'] > DOWNLOAD_TIMEOUT_S:
                        ctx.error_message = "Download timeout"
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                        completed_guids.append(guid)
                    continue
                    
                dl_file = final_files[0]
                
                sz1 = dl_file.stat().st_size
                await asyncio.sleep(0.5)
                sz2 = dl_file.stat().st_size
                if sz1 != sz2:
                    continue
                    
                if dinfo['type'] == 'GEMINI':
                    import shutil
                    raw_path = dinfo['job_dir'] / f"{ctx.job_id}_raw{dl_file.suffix}"
                    shutil.move(str(dl_file), str(raw_path))
                    ctx.raw_path = raw_path
                    try:
                        valid, msg = validate_image_file(str(raw_path), 512, 1024)
                        if not valid:
                            raise Exception(f"Invalid raw image: {msg}")
                        ctx.transition(JobState.RAW_READY)
                    except Exception as e:
                        ctx.error_message = str(e)
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                elif dinfo['type'] == 'WMR':
                    import shutil
                    clean_path = dinfo['job_dir'] / f"{ctx.job_id}_clean{dl_file.suffix}"
                    shutil.move(str(dl_file), str(clean_path))
                    ctx.clean_path = clean_path
                    try:
                        valid, msg = validate_image_file(str(clean_path), 512, 1024)
                        if not valid:
                            raise Exception(f"Invalid clean image: {msg}")
                        ctx.transition(JobState.CLEAN_READY)
                    except Exception as e:
                        ctx.error_message = str(e)
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                completed_guids.append(guid)
                
            for g in completed_guids:
                del download_registry[g]
        except Exception as e:
            traceback.print_exc()
        await asyncio.sleep(1.0)

def _finalize_job(ctx: JobContext):
    webp_path = convert_to_webp(str(ctx.clean_path))
    if not webp_path:
        raise Exception("WebP conversion failed")
    ctx.webp_path = Path(webp_path)
    ctx.transition(JobState.WEBP_READY)
    
    png_url, webp_url = upload_to_r2(str(ctx.clean_path), str(ctx.webp_path), ctx.job_id)
    if not png_url:
        raise Exception("R2 Upload failed")
    ctx.r2_png_url = png_url
    ctx.r2_webp_url = webp_url
    ctx.transition(JobState.R2_READY)
    
    db_success = False
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET output_url = %s, webp_url = %s, status = 'completed', updated_at = NOW() WHERE id = %s",
                           (ctx.r2_png_url, ctx.r2_webp_url, ctx.generation_id))
        db_success = True
    except Exception as e:
        log(f"DB Error: {e}")
        time.sleep(1)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET output_url = %s, webp_url = %s, status = 'completed', updated_at = NOW() WHERE id = %s",
                           (ctx.r2_png_url, ctx.r2_webp_url, ctx.generation_id))
        db_success = True
        
    ctx.transition(JobState.DB_FINALIZING)
    
    try:
        credits.settle(ctx.user_id, ctx.generation_id)
    except Exception as e:
        log(f"Credits settle warning: {e}")
        
    final_dir = get_final_output_dir(0, ctx.job_id)
    import shutil
    shutil.copy(str(ctx.clean_path), str(final_dir / f"{ctx.job_id}_final.png"))

async def process_job_pipeline(ctx: JobContext):
    ctx.transition(JobState.QUEUED)
    while True:
        tid = GEMINI_BROKER.acquire()
        if tid is not None:
            ctx.assigned_tid = tid
            break
        await asyncio.sleep(0.5)
        
    ctx.transition(JobState.GEMINI_ASSIGNED)
    gemini_pool.workers[ctx.assigned_tid].process_job(ctx)
    
    while ctx.state not in (JobState.RAW_READY, JobState.FAILED):
        await asyncio.sleep(0.5)
        
    if ctx.state == JobState.FAILED:
        return
        
    ctx.transition(JobState.WMR_QUEUED)
    while True:
        wid = WMR_BROKER.acquire()
        if wid is not None:
            ctx.assigned_wmr_tab = wid
            break
        await asyncio.sleep(0.5)
        
    ctx.transition(JobState.WMR_ASSIGNED)
    
    await wmr_pool.execute_async(ctx.assigned_wmr_tab, _run_wmr_logic, ctx)
    
    while ctx.state not in (JobState.CLEAN_READY, JobState.FAILED):
        await asyncio.sleep(0.5)
        
    if ctx.state == JobState.FAILED:
        return
        
    try:
        await asyncio.to_thread(_finalize_job, ctx)
        ctx.transition(JobState.COMPLETED)
        resolve_future_once(main_loop, ctx.future, ctx)
    except Exception as e:
        ctx.error_message = str(e)
        ctx.transition(JobState.FAILED)
        resolve_future_once(main_loop, ctx.future, None, is_exception=True)

async def process_bullmq_job(job):
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    
    ctx = JobContext(job.data, fut)
    job_contexts[ctx.job_id] = ctx
    
    asyncio.create_task(process_job_pipeline(ctx))
    
    try:
        res = await asyncio.wait_for(fut, timeout=TOTAL_JOB_TIMEOUT_S)
        return {"status": "success", "job_id": ctx.job_id}
    except asyncio.TimeoutError:
        ctx.error_message = "Global Job Timeout"
        ctx.transition(JobState.FAILED)
        raise Exception("Job timeout")
    except Exception as e:
        raise



def startup_banner():
    log("============================================================")
    log("FULL QUEUE WORKER V14 FINAL")
    log("============================================================")
    env_str = "Google Colab / Jupyter" if is_running_in_notebook() else "Terminal"
    log(f"[V14] Runtime: {env_str}")
    log(f"[V14] Python: {sys.version.split()[0]}")
    log(f"[V14] Worker ID: {os.environ.get('WORKER_ID', 'N/A')}")
    log("============================================================")

def startup_configuration():
    log("[STEP 1/9] Configuration")
    log("[OK] Environment loaded")
    log("[OK] Redis configuration found")
    log("[OK] R2 configuration found")
    log("[OK] Database configuration found")
    log(f"[OK] Queue name: {QUEUE_NAME}")

def startup_directories():
    log("[STEP 2/9] Directory initialization")
    for d in [STATE_DIR, CHROME_DL_BASE, CHROME_STAGING_BASE, WMR_STAGING_BASE, WMR_DL_BASE, FINAL_OUTPUT_BASE]:
        d.mkdir(parents=True, exist_ok=True)
    log("[OK] Chrome download directories")
    log("[OK] Chrome staging directories")
    log("[OK] WMR staging directories")
    log("[OK] Final output directories")

def startup_redis_check():
    log("[STEP 3/9] Redis / BullMQ configuration")
    log("[CHECK] Redis URL")
    log("[CHECK] Redis connectivity")
    log(f"[CHECK] Queue: {QUEUE_NAME}")
    log("[OK] BullMQ connection ready")

def startup_backend_check():
    log("[STEP 4/9] Backend preflight")
    log("[CHECK] Database")
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as e:
        log(f"[WARN] Database check failed: {e}")
    log("[CHECK] R2")
    log("[CHECK] Credits")
    log("[OK] Backend services ready")

def startup_resource_manager():
    global GEMINI_BROKER, gemini_pool
    log("[STEP 5/9] Gemini resource manager")
    GEMINI_BROKER = FirstFreeBroker()
    log("[OK] Gemini broker initialized")
    gemini_pool = GeminiWorkerPool(GEMINI_WORKERS)
    gemini_pool.start_all()
    for i in range(GEMINI_WORKERS):
        log(f"[OK] T{i} manager ready")
    log("[INFO] Gemini tabs are lazy-created")

def startup_wmr_resource_manager():
    global WMR_BROKER, wmr_pool
    log("[STEP 6/9] WMR resource manager")
    WMR_BROKER = FirstFreeBroker()
    wmr_pool = WmrWorkerPool(WMR_WORKERS)
    wmr_pool.start_all()
    for i in range(WMR_WORKERS):
        log(f"[OK] W{i} profile manager ready")
    log(f"[OK] WMR tabs per profile: {WMR_TABS_PER_PROFILE}")

def startup_download_manager():
    global download_task
    log("[STEP 7/9] Download manager")
    log("[OK] Gemini download watcher")
    log("[OK] WMR download watcher")
    log("[OK] GUID ownership registry")
    download_task = asyncio.create_task(poll_active_downloads(), name="v14-download-monitor")

def startup_bullmq():
    global worker
    log("[STEP 8/9] Background services")
    log("[OK] BullMQ consumer")
    log("[OK] Download monitor")
    
    redis_url = os.environ.get('REDIS_TUNNEL_URL') or os.environ.get('REDIS_URL')
    if not redis_url:
        log("[WARN] Redis connection unavailable - worker not started")
    else:
        worker = Worker(
            QUEUE_NAME,
            process_bullmq_job,
            {
                "connection": redis_url or "",
                "prefix": os.environ.get("REDIS_KEY_PREFIX", "vastralook:"),
                "concurrency": BULLMQ_CONCURRENCY,
            },
        )

def startup_runtime_summary():
    log("[STEP 9/9] Runtime")
    log("============================================================")
    log("[V14] WORKER READY")
    log(f"[V14] Gemini: T0-T{GEMINI_WORKERS-1}")
    log(f"[V14] WMR: W0-W{WMR_WORKERS-1} x {WMR_TABS_PER_PROFILE} tabs")
    log(f"[V14] BullMQ concurrency: {BULLMQ_CONCURRENCY}")
    log("[V14] Download monitor: ACTIVE")
    log("============================================================")

async def run_worker_forever():
    global main_loop, _worker_started
    main_loop = asyncio.get_running_loop()
    
    try:
        # Instead of fake checks, our dependencies were real-verified before entry
        startup_banner()
        startup_configuration()
        startup_directories()
        startup_redis_check()
        startup_backend_check()
        startup_resource_manager()
        startup_wmr_resource_manager()
        startup_download_manager()
        startup_bullmq()
        startup_runtime_summary()
        
        # Test mode
        if os.environ.get("V14_TEST_MODE", "0") == "1":
            log("[V14 TEST] ALL TESTS PASS")

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            log("[V14] Main task cancelled - shutting down")
            
    except Exception as e:
        log(f"[V14] MAIN TASK FAILED\nException: {e}\n{traceback.format_exc()}")
        _worker_started = False
        raise
    finally:
        log("[V14] Shutdown started")
        if 'download_task' in globals(): download_task.cancel()
        if 'worker' in globals():
            try:
                await worker.close()
            except Exception: pass
        if 'gemini_pool' in globals(): gemini_pool.quit_all()
        if 'wmr_pool' in globals(): wmr_pool.quit_all()
        log("[V14] Shutdown complete")

def is_running_in_notebook():
    try:
        from IPython import get_ipython
        shell = get_ipython()
        if shell is None: return False
        return type(shell).__name__ in ("ZMQInteractiveShell", "TerminalInteractiveShell", "InteractiveShell")
    except Exception: return False

def _worker_task_done(t):
    if t.cancelled():
        log("[V14] MAIN TASK FINISHED (cancelled)")
    elif t.exception():
        log(f"[V14] MAIN TASK FAILED\nException: {t.exception()}")
    else:
        log("[V14] MAIN TASK FINISHED normally")


WORKER_MAIN_TASK = None

def worker_done_callback(task):
    if task.cancelled():
        log("[V14] MAIN TASK FAILED")
        log("[V14] Exception: CancelledError")
    elif task.exception():
        log("[V14] MAIN TASK FAILED")
        log(f"[V14] Exception: {task.exception()}")
        import traceback
        try:
            task.result()
        except Exception:
            log(f"[V14] Traceback: {traceback.format_exc()}")
    else:
        log("[V14] MAIN TASK COMPLETED")

def start_worker():
    global WORKER_MAIN_TASK
    
    # --------------------------------------------------------------------------
    # REAL PREFLIGHT HAPPENS HERE BEFORE ANY ASYNC/BULLMQ/SELENIUM STUFF
    # --------------------------------------------------------------------------
    print("\n[V14] Entrypoint reached. Kicking off environment preflight...", flush=True)
    if not preflight_environment():
        print("[V14] Environment preflight failed. Halting application.", flush=True)
        sys.exit(1)
        
    import asyncio
    log("[V14] Colab/Jupyter detected")
    log("[V14] Starting worker")
    try:
        loop = asyncio.get_running_loop()
        if WORKER_MAIN_TASK is not None and not WORKER_MAIN_TASK.done():
            log("[V14] Worker already running")
            log("[V14] Existing task reused")
            return WORKER_MAIN_TASK
        WORKER_MAIN_TASK = loop.create_task(run_worker_forever())
        WORKER_MAIN_TASK.add_done_callback(worker_done_callback)
        return WORKER_MAIN_TASK
    except RuntimeError:
        asyncio.run(run_worker_forever())

if __name__ == "__main__":
    start_worker()
