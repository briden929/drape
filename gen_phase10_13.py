import os

base = r'C:\Users\PC\.gemini\antigravity\scratch\Reddis'

def write_report(filepath, content):
    full_path = os.path.join(base, filepath)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written: {filepath}")

# ============ 10. DOWNLOAD_OWNERSHIP_ANALYSIS.md ============
download_ownership = """# Download Ownership Analysis

## Problem: What NOT to do

The following approaches are INCORRECT for download correlation:

1. **Newest file** - Race conditions when multiple downloads happen simultaneously
2. **Filename only** - Multiple jobs can produce files with same name
3. **Extension only** - All PNG downloads look the same
4. **Directory scan** - Scanning can pick up stale files from other jobs
5. **Timestamp** - Clock skew, multiple files at same time

## Correct Approach: Chrome Download GUID

The CORRECT correlation model uses Chrome's CDP download GUID:

```
Browser.downloadWillBegin -> {guid, suggestedFilename}
Browser.downloadProgress -> {guid, state: "inProgress" | "completed"}
Browser.setDownloadBehavior -> {behavior: "allowAndName", downloadPath}
```

## DownloadRegistry Architecture

```python
class DownloadRegistry:
    def __init__(self):
        self.lock = threading.Lock()
        self.active_downloads = {} # guid -> {job_id, resource_id, status, path}
    
    def register_guid(self, guid, job_id, resource_id, expected_dir):
        # Called when Browser.downloadWillBegin fires
        with self.lock:
            self.active_downloads[guid] = {
                "job_id": job_id,
                "resource_id": resource_id,
                "expected_dir": expected_dir,
                "status": "in_progress",
                "start": time.time()
            }
    
    def update_progress(self, guid, state):
        # Called when Browser.downloadProgress fires
        with self.lock:
            if guid in self.active_downloads:
                self.active_downloads[guid]["status"] = state
```

## Ownership Verification

```python
def verify_download_owner(guid, expected_job_id):
    """Verify that the download belongs to the expected job."""
    with registry.lock:
        if guid not in registry.active_downloads:
            return False
        return registry.active_downloads[guid]["job_id"] == expected_job_id
```

## Directory Structure

```
/content/downloads/
    chrome_staging/
        T0/
            JOB_ID/
                incoming/     # Raw downloads land here
        T1/
        T2/
        T3/
    chrome/
        T0/
            JOB_ID/
                incoming/
    wmr_staging/
        W0/
            T0/
                JOB_ID/
                    incoming/  # WMR PNG downloads land here
    final_output/
        T0/
            JOB_ID/
                raw.png
                clean.png
                image.webp
```

## Historical Bug: Filename-Based Matching

**Versions affected:** V9-V13
**Problem:** Used `glob.glob()` to find newest file in download directory
**Symptom:** Multiple jobs interfering with each other's downloads
**Fix:** V14 N2N - CDP GUID-based tracking via DownloadRegistry

## Historical Bug: No GUID Tracking

**Versions affected:** V9-V13
**Problem:** No `Browser.downloadWillBegin` event listener
**Symptom:** Cannot correlate downloads to specific jobs
**Fix:** V14 N2N - DownloadRegistry class + CDP events

## Complete Download Flow

```
Gemini generation -> downloadWillBegin -> register GUID in registry
  -> T resource released immediately -> raw download continues
  -> downloadProgress(completed) -> file stability check
  -> PIL validation -> WMR admission
  -> WMR upload -> WMR processing -> Download PNG click
  -> downloadWillBegin -> register WMR GUID
  -> WMR resource released immediately
  -> clean download continues -> WebP -> R2 -> DB -> Credits -> COMPLETED
```
"""
write_report("DOWNLOAD_OWNERSHIP_ANALYSIS.md", download_ownership)

# ============ 11. LOGIN_FORENSICS.md ============
login_forensics = """# Login Forensics

## Source Files Analyzed

1. `google_login_raw.py` (1109 lines) - Most mature
2. `new_login.py` (25418 lines) - Comprehensive
3. `ultra_login_block.py` (24419 lines) - Extended login
4. `ecom_source.py` (4237 lines) - ECOM login flow
5. `apply_login.py` (4566 lines) - Login patch
6. `dump_ecom_login.py` / `dump_ecom_login2.py` / `dump_ecom_login3.py` - Login extractors
7. `check_v14_login.py` - Login checker
8. `read_login.py` / `read_login2.py` / `read_login_ref.py` - Login readers

## Login Detection Methods (google_login_raw.py)

The `comprehensive_login_check()` function uses 7 methods:

1. **Profile Avatar** - `//div[@aria-label='Google Account']//img`
2. **Email Text** - Regex pattern matching on page text
3. **Account Elements** - XPath for Google Account elements
4. **No Sign-in Button** - Verify absence of Sign in button
5. **URL Check** - `myaccount.google.com`, `accounts.google.com/b/0/`
6. **Auth Cookies** - SID, HSID, SSID, APISID, SAPISID, LOGIN_INFO
7. **Profile Button** - `[data-is-profile-button='true']`

**Confidence threshold:** >=43% (3 out of 7 methods)

## Login Flow

```
1. Check if already logged in (comprehensive_login_check)
2. If not logged in:
   a. Navigate to Google sign-in page
   b. Enter email -> passwordNext click
   c. Enter password -> signIn click
   d. Handle verification (2FA) if prompted
3. Verify login (comprehensive_login_check again)
4. Navigate to Gemini app (https://gemini.google.com/app)
5. Verify Gemini session is active
```

## Cookie Persistence

```python
COOKIES_FILE = "/content/google_cookies.pkl"
# Save: pickle.dump(driver.get_cookies(), f)
# Load: driver.add_cookie(c) for c in pickle.load(f)
```

## Login Recovery

```python
def recover_login(driver, profile_dir):
    """If login session expired during job:"""
    # 1. Detect logout (comprehensive_login_check returns False)
    # 2. Navigate to Google sign-in
    # 3. Enter credentials from saved profile
    # 4. Verify login
    # 5. Navigate back to Gemini
    # 6. Resume job
```

## Proven Browser Logic

The `google_login_raw.py` contains the most proven login logic because:
1. It has been runtime-tested in Colab
2. It uses multiple detection methods for reliability
3. It handles 2FA verification
4. It has cookie persistence
5. It includes comprehensive error handling

## ECOM Login (ecom_source.py)

The ECOM `handle_login(drv, wait)` function:
- Uses `driver.find_element(By.ID, "passwordNext").click()`
- Handles email/password entry
- Has session validation
- Uses Google cookies (`COOKIES_FILE = "/content/drive/MyDrive/google_cookies.pkl"`)

## Key Finding

The login detection from `google_login_raw.py` is the strongest because:
- It was PROVEN in actual Colab runtime
- It uses 7 independent methods
- It has confidence scoring
- It handles all edge cases (2FA, expired sessions, redirects)

## What Must Be Preserved

1. `comprehensive_login_check()` - 7-method detection
2. `is_logged_in_method_1_profile_avatar()` through method 7
3. `verify_google_account_auth()` - Google auth verification
4. Cookie persistence logic
5. 2FA verification handling
"""
write_report("LOGIN_FORENSICS.md", login_forensics)

# ============ 12. WMR_FORENSICS.md ============
wmr_forensics = """# WMR Forensics

## Source Files Analyzed

1. `FULL_QUEUE_WORKER_V14_N2N_FINAL.py` - Best WMR implementation
2. `FULL_QUEUE_WORKER_V14_FINAL.py` - V14 WMR
3. `ecom_source.py` - ECOM WMR operations
4. `FULL_QUEUE_WORKER_V13_FINAL.py` - V13 WMR
5. `add_wmr_logic.py` - WMR logic additions
6. `build_v14.py` - V14 builder with WMR
7. `build_v14_part1.py` - V14 part1 with WMR
8. `v11_raw.py`, `v12_work.py`, `v13_work.py` - Historical WMR

## WMR Architecture

### Profile Structure
```
W0 (profile: wmr_chrome_profiles/W0)
  ├── W0-T0 (tab 0)
  └── W0-T1 (tab 1)
W1 (profile: wmr_chrome_profiles/W1)
  ├── W1-T0 (tab 0)
  └── W1-T1 (tab 1)
W2 (profile: wmr_chrome_profiles/W2)
  ├── W2-T0 (tab 0)
  └── W2-T1 (tab 1)
W3 (profile: wmr_chrome_profiles/W3)
  ├── W3-T0 (tab 0)
  └── W3-T1 (tab 1)
```

### Configuration
```python
WMR_PROFILES = 4
WMR_TABS_PER_PROFILE = 2
# Total: 8 logical WMR resources (W0-T0 through W3-T1)
```

### WMR Driver Creation
```python
def create_wmr_chrome_driver(worker_id: int) -> webdriver.Chrome:
    """Chrome-only, isolated profiles, Chrome-only runtime."""
    staging_dir = get_wmr_staging_dir(worker_id)  # wmr_staging/W{worker_id}
    profile_dir = WMR_PROFILES_BASE / f'W{worker_id}'
    # Profile cloning, SingletonLock removal
    # ChromeOptions with --user-data-dir
    # Download directory prefs
    # NO Microsoft Edge
```

## WMR Workflow

```
1. Acquire WMR resource (wmr_broker.acquire()) -> "W0-T0"
2. Upload raw PNG to WMR site
3. Wait for processing
4. Click exact "Download PNG" button
5. downloadWillBegin fires -> register GUID
6. WMR resource released immediately (wmr_broker.release())
7. Clean PNG download continues independently
8. Validate clean PNG -> WebP -> R2 -> DB -> Credits
```

## WMR "Download PNG" Strategy

The WMR site uses `https://www.pixelcut.ai/watermark-remover` or `https://logo-remover-fawn.vercel.app/gemini`.

The exact "Download PNG" button is identified by:
```javascript
if ((spans[i].textContent || '').trim() === 'Download PNG') {
    // Click this button
}
```

## WMR Resource Release

**CRITICAL:** WMR resource is released when "Download PNG" START is confirmed (downloadWillBegin fires), NOT when:
- WMR processing begins
- PNG download finishes
- Clean file is fully written
- WebP is created
- R2 upload completes

## Historical Bugs

### Bug 1: WMR Global Queue
**Versions affected:** V9-V13
**Problem:** Single `WMR_GLOBAL_Q = queue.Queue()` caused all WMR tasks to compete for one queue
**Fix:** V14 N2N - separate FirstFreeBroker per WMR resource

### Bug 2: Edge Contamination
**Versions affected:** V12/V13, apply_improvements.py
**Problem:** Some versions used `EdgeOptions` and `webdriver.Edge` for WMR
**Fix:** V14 N2N - Strictly Chrome only

### Bug 3: No Tab Isolation
**Versions affected:** V9-V12
**Problem:** Multiple jobs using same WMR tab caused race conditions
**Fix:** V14 N2N - Per-tab resource tracking (W0-T0, W0-T1, etc.)

### Bug 4: Filename-Based WMR Download Detection
**Versions affected:** V9-V13
**Problem:** Used filename to find WMR download completion
**Fix:** V14 N2N - CDP GUID-based tracking

## WMR Failure Isolation

- W0 failure MUST NOT kill W1, W2, W3
- WMR crash affecting entire worker must be prevented
- Single job WMR failure must NOT affect other jobs
- WMR resource released on failure

## What Must Be Preserved

1. `create_wmr_chrome_driver()` - Chrome-only driver creation
2. `get_wmr_staging_dir()` - Per-profile staging
3. `get_wmr_job_dir()` - Per-job directory
4. WMR "Download PNG" click logic
5. WMR resource release at download START
6. WMR FirstFreeBroker scheduling
"""
write_report("WMR_FORENSICS.md", wmr_forensics)

# ============ 13. GEMINI_FORENSICS.md ============
gemini_forensics = """# Gemini Forensics

## Source Files Analyzed

1. `FULL_QUEUE_WORKER_V14_N2N_FINAL.py` - Best Gemini implementation
2. `FULL_QUEUE_WORKER_V14_FINAL.py` - V14 Gemini
3. `ecom_source.py` - ECOM Gemini operations
4. `google_login_raw.py` - Google/Gemini login
5. `build_v14_part1.py` - V14 part1 builder
6. `v11_raw.py` - V11 raw implementation
7. `gen_v14_clean_2/3/4.py` - Clean generators

## Gemini T Resource Model

```
T0, T1, T2, T3 = 4 persistent Chrome profiles
Each has:
  - Independent --user-data-dir (chrome_profile_T0, T1, T2, T3)
  - Master profile cloning
  - SingletonLock cleanup
  - Separate download directories
```

## Gemini Workflow

```
1. Acquire T resource (gemini_broker.acquire()) -> "T0"
2. Launch Chrome with T0 profile
3. Navigate to https://gemini.google.com/app
4. Verify Gemini session is active
5. Open new chat
6. Navigate to Flash mode -> Create Image
7. Upload reference images
8. Inject prompt via clipboard
9. Click Send
10. Wait for generation detection
11. Click download
12. downloadWillBegin fires -> register GUID
13. T resource released immediately
14. Raw download continues independently
```

## Flash/Create Image Navigation

The Gemini app uses a mode picker. The exact DOM strategy:
```python
# Look for mode picker elements
if ("mode picker" in lbl or "open mode" in lbl or "flash" in lbl or "pro" in lbl):
    # Select Flash mode
    
# Click plus button to create image
# Open file input drawer
# Upload reference images
# Verify attachment count
```

## Generation Detection

```python
def _is_gemini_processing(drv):
    """Check if Gemini is still generating."""
    # Check for processing indicators
    
def _has_generated_image(drv):
    """Check if generated image appeared."""
    # Look for image elements
```

## Chrome Profile Management

```python
def create_gemini_driver(tid: int):
    master_profile = Path(CHROME_PROFILE_DIR)
    worker_profile = Path(str(CHROME_PROFILE_DIR) + f'_T{tid}')
    
    # Clone master profile if it exists
    if not worker_profile.exists():
        shutil.copytree(master_profile, worker_profile)
    
    # Remove SingletonLock files (prevents conflicts)
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = worker_profile / fname
        if fpath.exists():
            fpath.unlink()
    
    # Configure ChromeOptions
    opts = ChromeOptions()
    opts.add_argument(f'--user-data-dir={worker_profile}')
    opts.add_argument('--profile-directory=Default')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    # ... more options
```

## What Must Be Preserved

1. Profile cloning and SingletonLock management
2. Flash/Create Image navigation DOM strategies
3. Generation detection logic
4. `resolve_future_once()` for thread-safe futures
5. `_click_flash_in_picker()`, `_verify_flash_selected()`
6. `_click_send_button()`, `_is_gemini_processing()`
7. `_has_generated_image()` for image detection
"""
write_report("GEMINI_FORENSICS.md", gemini_forensics)
print("Gemini forensics done")
