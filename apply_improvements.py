# apply_improvements.py
import re
from pathlib import Path

build_script_path = Path(r"C:\Users\PC\.gemini\antigravity\scratch\build_script.py")

with open(build_script_path, "r", encoding="utf-8") as f:
    text = f.read()

# Define section boundaries
def get_section_span(start_marker, end_marker):
    start = text.find(start_marker)
    if start == -1:
        raise ValueError(f"Marker not found: {start_marker}")
    end = text.find(end_marker, start)
    if end == -1:
        raise ValueError(f"Marker not found: {end_marker}")
    return start, end

# 1. Update imports
old_imp = """import urllib.request
import uuid
from pathlib import Path"""
new_imp = """import urllib.request
import uuid
import math
from collections import defaultdict
from pathlib import Path
from PIL import Image
from IPython.display import display as ipy_display, HTML"""
assert old_imp in text, "old_imp not found"
text = text.replace(old_imp, new_imp, 1)

# 2. Update Step 1 configuration
old_cfg = """for _d in (BASE_DIR, STATE_DIR, CHROME_PROFILE_DIR, EDGE_PROFILE_DIR, REFS_CACHE_DIR,
           JOBS_DOWNLOAD_BASE, WMR_DL_DIR, FINAL_OUTPUT_BASE):
    _d.mkdir(parents=True, exist_ok=True)"""

new_cfg = """SCREEN_W, SCREEN_H = 1920, 1080
VNC_PORT = 5900
NOVNC_PORT = 6080
CHROME_DL_BASE = Path('/content/downloads')

for _d in (BASE_DIR, STATE_DIR, CHROME_PROFILE_DIR, EDGE_PROFILE_DIR, REFS_CACHE_DIR,
           JOBS_DOWNLOAD_BASE, WMR_DL_DIR, FINAL_OUTPUT_BASE, CHROME_DL_BASE):
    _d.mkdir(parents=True, exist_ok=True)

def tab_dl_dir(tid):
    d = Path(f"/content/downloads/tab_{tid}")
    d.mkdir(parents=True, exist_ok=True)
    return d

for tid in range(MAX_CONCURRENT_TABS):
    tab_dl_dir(tid)"""
assert old_cfg in text, "old_cfg not found"
text = text.replace(old_cfg, new_cfg, 1)

# 3. Update Step 2: Install dependencies
s2_start, s3_start = get_section_span("# --- STEP 2: INSTALL DEPENDENCIES ---", "# --- STEP 3: REGISTER BACKEND MODULES ---")
new_s2 = '''# --- STEP 2: INSTALL DEPENDENCIES ---
sections.append("""# ============================================================================
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
    print(f"  ✅ Microsoft Edge ready at: {edge_path}\\n")
else:
    print("  ⚠️ Edge binary not found in PATH, using fallback.\\n")
""")

'''
text = text[:s2_start] + new_s2 + text[s3_start:]

# 4. Update Step 5: Virtual Display & noVNC
s5_start, s6_start = get_section_span("# --- STEP 5: VIRTUAL DISPLAY & NOVNC ---", "# --- STEP 6: DRIVERS ---")
new_s5 = '''# --- STEP 5: VIRTUAL DISPLAY & NOVNC ---
sections.append("""# ============================================================================
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
                        ipy_display(HTML(f\"\"\"
                        <div style='background:linear-gradient(135deg,#1b5e20,#2e7d32);color:white;
                        padding:16px;border-radius:10px;font-size:15px;font-weight:bold;margin:10px 0;box-shadow:0 4px 6px rgba(0,0,0,0.3);'>
                        🖥️ <b>noVNC Remote Desktop Stream:</b><br><br>
                        🌐 <a href='{vnc_url_1}' target='_blank' style='color:#a7ffeb;text-decoration:underline;'>Open Live UI ({vnc_url_1})</a><br>
                        </div>\"\"\"))
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
""")

'''
text = text[:s5_start] + new_s5 + text[s6_start:]

# 5. In Step 6: Define set_tab_download_dir
old_s6_head = """from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

def create_chrome_driver():"""

new_s6_head = """from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

def set_tab_download_dir(drv, path):
    ap = os.path.abspath(str(path))
    os.makedirs(ap, exist_ok=True)
    try: drv.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": ap})
    except Exception: pass
    try: drv.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": ap, "eventsEnabled": False})
    except Exception: pass

def create_chrome_driver():"""
assert old_s6_head in text, "old_s6_head not found"
text = text.replace(old_s6_head, new_s6_head, 1)

# 6. Update Step 10: Complete DOM routines
s10_start, s11_start = get_section_span("# --- STEP 10: DOM & DOWNLOAD ENGINE ---", "# --- STEP 11: DB HELPERS ---")
new_s10 = '''# --- STEP 10: DOM & DOWNLOAD ENGINE ---
sections.append("""# ============================================================================
# STEP 10: PROVEN GEMINI DOM ROUTINES (FLASH, CREATE IMAGE, XCLIP UPLOAD, DIRECT FETCH)
# ============================================================================

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
        except Exception: continue
    try:
        drv.get(GEMINI_APP_URL)
        time.sleep(1.2)
        return True
    except Exception: return False

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
                    if txt: return txt
        except Exception: continue
    try:
        txt = drv.execute_script(
            "var el=document.querySelector("
            "  'div[data-test-id=\\"logo-pill-label-container\\"] span.picker-primary-text,"
            "   div[data-test-id=\\"logo-pill-label-container\\"] span.gds-body-m');"
            "return el ? el.textContent.trim() : '';"
        )
        return (txt or "").strip()
    except Exception: return ""

def _open_model_picker(drv):
    try:
        btn = drv.find_element(By.CSS_SELECTOR, "button[data-test-id='bard-mode-menu-button']")
        if btn and btn.is_displayed():
            drv.execute_script("arguments[0].click();", btn)
            time.sleep(0.45)
            return True
    except Exception: pass
    try:
        el = drv.find_element(By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container']")
        if el and el.is_displayed():
            drv.execute_script("arguments[0].click();", el)
            time.sleep(0.45)
            return True
    except Exception: pass
    try:
        icon = drv.find_element(By.CSS_SELECTOR,
            "div[data-test-id='logo-pill-label-container'] mat-icon[fonticon='keyboard_arrow_down'],"
            "div[data-test-id='logo-pill-label-container'] mat-icon[data-mat-icon-name='keyboard_arrow_down']")
        if icon and icon.is_displayed():
            drv.execute_script("arguments[0].click();", icon)
            time.sleep(0.45)
            return True
    except Exception: pass
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[aria-label]"):
            lbl = (btn.get_attribute("aria-label") or "").lower()
            if ("mode picker" in lbl or "open mode" in lbl or "flash" in lbl or "pro" in lbl):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.45)
                    return True
    except Exception: pass
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
    except Exception: pass
    return False

def _click_flash_in_picker(drv):
    def _is_valid_flash_option(el):
        try:
            txt = (el.text or "").strip().lower()
            return "flash" in txt and "lite" not in txt
        except Exception: return False

    for tid in ["bard-mode-option-flash", "mode-option-flash", "flash-option", "model-flash"]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, f"[data-test-id='{tid}']"):
                if el.is_displayed():
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    return True
        except Exception: continue

    for sel in ["mat-option", "[role='option']", "[role='menuitem']", "[role='menuitemradio']", "button[class*='mode-option']", "button[class*='picker']"]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed() and _is_valid_flash_option(el):
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    return True
        except Exception: continue

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
        except Exception: continue

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
    except ModelLimitReached: raise
    except Exception: pass
    return False

def _verify_flash_selected(drv, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            txt = _get_current_model_text(drv)
            if txt and "flash" in txt.lower() and "lite" not in txt.lower():
                return True
        except Exception: pass
        time.sleep(0.15)
    return False

def switch_to_flash(drv):
    current = _get_current_model_text(drv)
    if current and "flash" in current.lower() and "lite" not in current.lower():
        return True
    for attempt in range(1, 4):
        if not _open_model_picker(drv):
            time.sleep(0.4); continue
        time.sleep(0.3)
        try:
            clicked = _click_flash_in_picker(drv)
        except ModelLimitReached:
            try: drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception: pass
            raise
        if clicked and _verify_flash_selected(drv, timeout=2.5):
            return True
        try: drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception: pass
        time.sleep(0.3)
    return False

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
            time.sleep(0.3); return True
    except Exception: pass
    for sel in ['button[aria-label="Upload and tools"]', 'button[jslog*="300142"]', 'button[aria-haspopup="menu"][aria-label*="Upload"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3); return True
        except Exception: continue
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
                    time.sleep(0.2); return True
        except Exception: continue
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
            time.sleep(0.2); return True
    except Exception: pass
    return False

def find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs: return inputs[0]
    try:
        drv.execute_script("""
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                el.removeAttribute('hidden'); el.removeAttribute('disabled');
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
            for sel in ['button[aria-label="close attachment"]', "gem-media-attachment", "uploader-file-preview", ".attachment-preview-wrapper"]:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed(): return True
        except Exception: pass
        time.sleep(0.15)
    return False

def _activate_image_mode_and_upload(drv, abs_paths):
    try:
        ta = drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder='Describe your image']")
        if not ta:
            if click_plus_button(drv):
                time.sleep(0.2)
                try:
                    btns = drv.find_elements(By.CSS_SELECTOR, "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button")
                    for btn in btns:
                        if btn.is_displayed() and "Create image" in btn.text:
                            drv.execute_script("arguments[0].click();", btn)
                            time.sleep(0.25); break
                    else:
                        for icon in drv.find_elements(By.CSS_SELECTOR, "mat-icon[data-mat-icon-name='image_create'], mat-icon[fonticon='image_create']"):
                            if icon.is_displayed():
                                btn = drv.execute_script("var e=arguments[0];while(e&&e.tagName!=='BUTTON')e=e.parentElement;return e;", icon)
                                if btn and btn.is_displayed():
                                    drv.execute_script("arguments[0].click();", btn)
                                    time.sleep(0.25); break
                except Exception: pass
    except Exception: pass

    if not click_plus_button(drv): return False
    time.sleep(0.2)
    if not click_upload_files_in_drawer(drv):
        try:
            drv.execute_script("var b=document.querySelector('button.hidden-local-file-image-selector-button, button[xapfileselectortrigger]'); if(b) b.click();")
            time.sleep(0.1)
        except Exception: pass

    fi = find_file_input(drv)
    if not fi: return False

    try:
        if isinstance(abs_paths, list):
            fi.send_keys("\\n".join(abs_paths))
        else:
            fi.send_keys(abs_paths)
    except Exception as e:
        return False

    return wait_for_attachment_chip(drv, timeout=8.0)

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
    except Exception: return False

def get_quill_editor(drv):
    for sel in [
        "div.ql-editor[data-placeholder='Describe your image']",
        "div.ql-editor[contenteditable='true']",
        "rich-textarea div[contenteditable='true']",
        "div[contenteditable='true']",
    ]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed(): return el
        except Exception: pass
    return None

def _verify_editor_content(drv, editor, expected_text, timeout=3.0):
    min_len = max(10, int(len(expected_text) * 0.75))
    first30 = expected_text[:30].strip()
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            c = (editor.text or "").strip()
            if not c:
                c = drv.execute_script("return (arguments[0].textContent || '').trim();", editor) or ""
            if len(c) >= min_len and first30 in c: return True
        except Exception: pass
        time.sleep(0.1)
    return False

def _inject_prompt_fast(drv, text):
    editor = get_quill_editor(drv)
    if not editor: return False
    try:
        drv.execute_script("arguments[0].focus();", editor)
        ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        editor.send_keys(Keys.DELETE)
    except Exception: pass

    if _set_clipboard_xclip(text):
        try:
            drv.execute_script("arguments[0].focus();", editor)
            ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
            time.sleep(0.2)
            if _verify_editor_content(drv, editor, text, timeout=2.5): return True
        except Exception: pass

    try:
        drv.execute_script("arguments[0].focus();", editor)
        drv.execute_script("document.execCommand('selectAll',false,null); document.execCommand('delete',false,null); document.execCommand('insertText',false,arguments[0]);", text)
        time.sleep(0.2)
        if _verify_editor_content(drv, editor, text, timeout=2.5): return True
    except Exception: pass

    try:
        drv.execute_script("arguments[0].focus();", editor)
        chunk = 500
        for i in range(0, len(text), chunk):
            editor.send_keys(text[i:i + chunk])
            time.sleep(0.02)
        time.sleep(0.2)
        if _verify_editor_content(drv, editor, text, timeout=3.0): return True
    except Exception: pass
    return False

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
        if res == 'OK': return True
    except Exception: pass
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
        except Exception: continue
    return False

def snapshot_urls(drv):
    try:
        return set(drv.execute_script(
            "return Array.from(document.querySelectorAll('img[src^=\"blob:\"],img[src*=\"googleusercontent\"]')).map(i=>i.src).filter(s=>s&&s.length>10);"
        ) or [])
    except Exception: return set()

def _thumb_up_visible(drv):
    try:
        return drv.execute_script("""
            var icons = document.querySelectorAll('mat-icon[data-mat-icon-name="thumb_up"], mat-icon[fonticon="thumb_up"]');
            for (var i = 0; i < icons.length; i++) {
                if (icons[i].offsetParent !== null) return true;
            } return false;
        """)
    except Exception: return False

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
    except Exception: return False

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
        if stop: return True
        loading = drv.execute_script("""
            var el = document.querySelector('image-loading-overlay [data-test-id="image-loading-overlay"]');
            if (el && el.offsetParent !== null) {
                return !el.classList.contains('done-generating');
            } return false;
        """)
        return bool(loading)
    except Exception: return False

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
            if src not in urls_before: return src
    except Exception: pass

    for sel in ["generated-image img", "single-image img", "img[src*='googleusercontent']", "model-response img"]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                if not img.is_displayed(): continue
                src = img.get_attribute("src") or ""
                tid = img.get_attribute("data-test-id") or ""
                if len(src) < 10 or "uploaded-img" in tid or tid == "image-preview": continue
                if src in urls_before: continue
                if src.startswith("blob:https://gemini.google.com") or "googleusercontent" in src:
                    return src
        except Exception: continue
    return None

def check_gemini_error(drv):
    try:
        b = drv.find_element(By.TAG_NAME, "body").text.lower()
        u = drv.current_url.lower()
        if any(w in b for w in ["encountered an error", "something went wrong", "unable to complete your request"]):
            return "error"
        if any(w in u for w in ["google.com/sorry", "recaptcha"]):
            return "sorry"
    except Exception: pass
    return None

def check_text_error(drv):
    try:
        b = drv.find_element(By.TAG_NAME, "body").text.lower()
        if any(w in b for w in ["cannot create images of", "can't create images of", "unable to create that image"]):
            return "refusal"
        if any(w in b for w in ["image-generation limit", "daily limit", "rate limit", "too many requests"]):
            return "limit"
    except Exception: pass
    return None

def nb_check_image(drv, urls_before, chat_urls):
    rc = check_text_error(drv)
    if rc: return ("REFUSED" if rc == "refusal" else "LIMIT"), None
    ge = check_gemini_error(drv)
    if ge: return "ERROR", None

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
    except Exception: pass
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
        except Exception: pass
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
        except Exception: continue

    for img in reversed(candidates):
        try:
            if img.is_displayed() and _try_hover(img): return True
        except Exception: continue

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
        if clicked: return True
    except Exception: pass
    return False
""")

'''
text = text[:s10_start] + new_s10 + text[s11_start:]

# 7. Update Step 12: Scheduler & Pipeline Controller
s12_start, s13_start = get_section_span("# --- STEP 12: SCHEDULER ---", "# --- STEP 13: BULLMQ & MAIN ---")
new_s12 = '''# --- STEP 12: SCHEDULER ---
sections.append("""# ============================================================================
# STEP 12: CENTRAL ASYNC SCHEDULER & PIPELINE COORDINATOR
# ============================================================================

job_queue = asyncio.Queue()
active_downloads = {}
counters = {"completed": 0, "failed": 0}
last_status_print = 0.0

def get_next_idle_tab():
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

async def check_active_downloads():
    now = time.time()
    for job_id, dinfo in list(active_downloads.items()):
        if dinfo["state"] != S_DOWNLOAD_WAITING:
            continue
        
        raw_path = dinfo["raw_download_path"]
        tdir = dinfo["tab_dl_dir"]
        
        # 1. Direct file already saved and verified
        if raw_path.exists() and raw_path.stat().st_size > 5000:
            dinfo["state"] = S_FINALIZING
            log(f"[{job_id}] DOWNLOAD CONFIRMED ({raw_path.stat().st_size // 1024} KB) -> Immediate handoff to Edge WMR.")
            asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
            continue
            
        # 2. Check tab dedicated download directory + candidate fallback dirs
        candidate_dirs = [tdir, JOBS_DOWNLOAD_BASE / job_id, JOBS_DOWNLOAD_BASE, Path('/content/downloads'), Path('/root/Downloads')]
        files_before = dinfo.get("files_before", set())
        found_file = None
        for cd in candidate_dirs:
            if not cd.exists(): continue
            for fn in os.listdir(cd):
                if fn.endswith(('.crdownload', '.tmp', '.part', '.download')): continue
                if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')): continue
                fp = cd / fn
                try:
                    if str(fp) in files_before: continue
                    sz = fp.stat().st_size
                    if sz > 5000 and (now - fp.stat().st_mtime) < 180:
                        found_file = fp; break
                except Exception: pass
            if found_file: break

        if found_file:
            cur_sz = found_file.stat().st_size
            if cur_sz == dinfo.get("last_size", -1):
                dinfo["stable_checks"] = dinfo.get("stable_checks", 0) + 1
                if dinfo["stable_checks"] >= 1:
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    if str(found_file) != str(raw_path):
                        try: shutil.move(str(found_file), str(raw_path))
                        except Exception:
                            shutil.copy2(str(found_file), str(raw_path))
                            try: os.remove(str(found_file))
                            except Exception: pass
                    dinfo["state"] = S_FINALIZING
                    log(f"[{job_id}] DOWNLOAD DETECTED & RENAMED to {raw_path.name} ({raw_path.stat().st_size // 1024} KB) -> Enqueuing for Edge WMR.")
                    asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
            else:
                dinfo["last_size"] = cur_sz
                dinfo["stable_checks"] = 0
                
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
    job_id = dinfo["job_id"]
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
        if tid is None: break
        
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
            
            # 1. Switch to Flash mode using verified ECOM 2 picker
            switch_to_flash(chrome_driver)
            
            # 2. Activate Create image mode & Upload reference images
            ref_paths = [str(Path(p).resolve()) for p in info["refs"] if p and os.path.exists(p)]
            if not _activate_image_mode_and_upload(chrome_driver, ref_paths):
                log(f"[T{tid}][{job_id}] ⚠️ Attachment notice, continuing...")
            
            # 3. Inject prompt fast via clipboard
            _inject_prompt_fast(chrome_driver, info["prompt"])
            
            info["urls_before"] = snapshot_urls(chrome_driver)
            info["chat_urls"] = set()
            
            # 4. Click Send button
            if not _click_send_button(chrome_driver):
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
            
            if now - info["start_time"] > GENERATION_TIMEOUT_S:
                log(f"[T{tid}][{info['job_id']}] HARD TIMEOUT after {GENERATION_TIMEOUT_S}s! Refreshing tab.")
                _recover_stuck_tab(tid, "Generation timed out")
                continue
                
            status, new_src = nb_check_image(chrome_driver, info["urls_before"], info["chat_urls"])
            
            if status == 'SUCCESS':
                job_id = info["job_id"]
                log(f"[T{tid}][{job_id}] IMAGE DETECTED! Initiating immediate capture...")
                
                job_dir = JOBS_DOWNLOAD_BASE / job_id
                job_dir.mkdir(parents=True, exist_ok=True)
                raw_path = job_dir / f"{job_id}_raw.png"
                
                # A: Instant direct memory / canvas capture (<150ms)
                if _direct_fetch_cdp(chrome_driver, str(raw_path), info["urls_before"]):
                    info["urls_before"].add(new_src)
                    log(f"[T{tid}][{job_id}] INSTANT DIRECT CAPTURE ({raw_path.stat().st_size // 1024} KB) -> Immediate handoff to Edge WMR.")
                    dinfo = {
                        "job_id": job_id, "tab_id": tid, "job": info["job"], "gen": info["gen"],
                        "prompt": info["prompt"], "tab_dl_dir": tab_dl_dir(tid), "raw_download_path": raw_path,
                        "started_at": time.time(), "state": S_FINALIZING, "future": info.get("future")
                    }
                    _free_tab(tid, job_id)
                    asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
                else:
                    # B: Single-click hover download into dedicated tab directory
                    set_tab_download_dir(chrome_driver, tab_dl_dir(tid))
                    files_before = set(os.listdir(tab_dl_dir(tid))) if tab_dl_dir(tid).exists() else set()
                    hover_ok = _hover_and_dl_single_click(chrome_driver, info["urls_before"], info["chat_urls"])
                    info["urls_before"].add(new_src)
                    log(f"[T{tid}][{job_id}] DOWNLOAD CLICKED (success={hover_ok}) -> Handing off to disk watcher.")
                    active_downloads[job_id] = {
                        "job_id": job_id, "tab_id": tid, "job": info["job"], "gen": info["gen"],
                        "prompt": info["prompt"], "tab_dl_dir": tab_dl_dir(tid), "raw_download_path": raw_path,
                        "files_before": files_before, "started_at": time.time(), "last_size": -1, "stable_checks": 0,
                        "state": S_DOWNLOAD_WAITING, "future": info.get("future")
                    }
                    _free_tab(tid, job_id)
                
                # Immediate next job pickup if waiting in queue
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
                
            else: # WAITING
                if _send_btn_enabled(chrome_driver) and not _is_gemini_processing(chrome_driver):
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
    
    try: chrome_driver.get(GEMINI_APP_URL)
    except Exception: pass
    
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
            log(f"Scheduler loop error: {e}", file=sys.stderr)
        await asyncio.sleep(0.4)
""")

'''
text = text[:s12_start] + new_s12 + text[s13_start:]

with open(build_script_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Applied all improvements to build_script.py successfully!")
