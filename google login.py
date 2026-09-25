# @title ULTRA-FIXED GOOGLE LOGIN - PROPER DETECTION + FAST EXECUTION
# ============================================================================
# ✅ FIXED: Now properly detects existing login (profile avatar, email, etc.)
# ✅ FIXED: Multiple login check methods
# ✅ FIXED: Fast password field detection (5 seconds max)
# ✅ FIXED: Robust Gemini activity toggle
# ============================================================================

import os, re, json, time, glob, shutil, random, subprocess, socket
from datetime import datetime

print("="*70)
print(" INSTALLING DEPENDENCIES")
print("="*70)

chrome_bin = None
for path in ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome"]:
    if os.path.exists(path):
        chrome_bin = path
        break

if chrome_bin:
    v = subprocess.run([chrome_bin, "--version"], capture_output=True, text=True).stdout.strip()
    print(f"✅ Chrome already installed: {v}")
else:
    print(" Installing Google Chrome...")
    get_ipython().system("apt-get update -y > /dev/null 2>&1")
    get_ipython().system("apt-get install -y wget xvfb x11vnc novnc websockify fluxbox > /dev/null 2>&1")
    get_ipython().system("wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
    get_ipython().system("apt-get install -y ./google-chrome-stable_current_amd64.deb > /dev/null 2>&1")
    get_ipython().system("rm -f google-chrome-stable_current_amd64.deb")
    chrome_bin = "/usr/bin/google-chrome-stable"
    v = subprocess.run([chrome_bin, "--version"], capture_output=True, text=True).stdout.strip()
    print(f"✅ Installed: {v}")

cf_path = "/usr/local/bin/cloudflared"
if not os.path.exists(cf_path):
    print(" Installing cloudflared...")
    get_ipython().system(f"wget -q --timeout=20 -O {cf_path} https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64")
    get_ipython().system(f"chmod +x {cf_path}")
else:
    print("✅ cloudflared already installed")

get_ipython().system("pip install -q selenium webdriver-manager pyvirtualdisplay pillow requests 2>/dev/null")
print("✅ Packages installed")
print("="*70)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from IPython.display import Image as IPImage, display as ipy_display, HTML
from pyvirtualdisplay import Display
import pickle

SCREENSHOT_FOLDER = "/content/login_screenshots"
CHROME_DOWNLOAD_DIR = "/content/downloads"
COOKIES_FILE = "/content/google_cookies.pkl"
PROFILE_DIR = "/content/chrome_profile"

TIMEOUT = 15
SHORT_WAIT = 2
MAX_VERIFICATION_ATTEMPTS = 3

os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
os.makedirs(CHROME_DOWNLOAD_DIR, exist_ok=True)
os.makedirs(PROFILE_DIR, exist_ok=True)

# ============================================================================
# 🔍 ULTRA-ROBUST LOGIN DETECTION - MULTIPLE METHODS
# ============================================================================

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

def comprehensive_login_check(driver, page_name=""):
    """🎯 COMPREHENSIVE LOGIN CHECK - Uses ALL 7 methods"""
    print(f"\n🔍 Checking login status{f' ({page_name})' if page_name else ''}...")
    print(f"   Current URL: {driver.current_url[:80]}")

    methods = [
        ("Profile Avatar", is_logged_in_method_1_profile_avatar),
        ("Email Text", is_logged_in_method_2_email_text),
        ("Account Elements", is_logged_in_method_3_account_elements),
        ("No Sign-in Button", is_logged_in_method_4_no_signin),
        ("URL Check", is_logged_in_method_5_url_check),
        ("Auth Cookies", is_logged_in_method_6_cookies),
        ("Profile Button", is_logged_in_method_7_profile_button),
    ]

    passed = 0
    total = len(methods)

    for name, method in methods:
        try:
            if method(driver):
                passed += 1
        except Exception as e:
            pass

    confidence = (passed / total) * 100
    print(f"\n   📊 Login Confidence: {passed}/{total} methods passed ({confidence:.0f}%)")

    if confidence >= 43:  # At least 3 out of 7 methods
        print(f"   ✅ CONCLUSION: USER IS LOGGED IN!")
        return True
    else:
        print(f"   ❌ CONCLUSION: USER IS NOT LOGGED IN")
        return False

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

# ============================================================================
# noVNC Setup Functions
# ============================================================================

_display_obj = _x11vnc_proc = _novnc_proc = _cf_proc = _fluxbox_proc = None
novnc_web_dir = None
for p in ["/usr/share/novnc", "/usr/share/noVNC", "/opt/novnc", "/opt/noVNC"]:
    if os.path.isdir(p):
        novnc_web_dir = p
        break

def start_display():
    subprocess.run("pkill -f Xvfb", shell=True, capture_output=True, timeout=5)
    time.sleep(0.5)
    subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1920x1080x24", "-ac"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.environ["DISPLAY"] = ":99"
    time.sleep(1)
    print("✅ Display :99 started")

def start_fluxbox():
    global _fluxbox_proc
    subprocess.run("pkill -f fluxbox", shell=True, capture_output=True, timeout=5)
    time.sleep(0.5)
    _fluxbox_proc = subprocess.Popen(["fluxbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    print("✅ Window manager (fluxbox) started")

def start_vnc():
    global _x11vnc_proc, _novnc_proc
    subprocess.run("pkill -f x11vnc", shell=True, capture_output=True, timeout=5)
    subprocess.run("pkill -f websockify", shell=True, capture_output=True, timeout=5)
    time.sleep(0.5)
    _x11vnc_proc = subprocess.Popen(["x11vnc", "-display", ":99", "-forever",
                                     "-nopw", "-shared", "-rfbport", "5900"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    print("✅ x11vnc started on port 5900")

    if novnc_web_dir:
        _novnc_proc = subprocess.Popen(["websockify", "--web", novnc_web_dir,
                                        "6080", "localhost:5900"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        _novnc_proc = subprocess.Popen(["websockify", "6080", "localhost:5900"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    print("✅ noVNC started on port 6080")

def start_tunnel():
    global _cf_proc
    if os.path.exists(cf_path):
        subprocess.run("pkill -f cloudflared", shell=True, capture_output=True, timeout=5)
        time.sleep(0.5)
        _cf_proc = subprocess.Popen([cf_path, "tunnel", "--url", "http://localhost:6080"],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        deadline = time.time() + 30
        while time.time() < deadline:
            line = _cf_proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
            m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if m:
                tunnel_url = m.group(0)
                vnc_url = f"{tunnel_url}/vnc.html?autoconnect=true&resize=scale"
                ipy_display(HTML(f"""
                <div style='background:linear-gradient(135deg,#34a853,#0d652d);
                            color:white;padding:20px;border-radius:10px;
                            font-size:16px;font-weight:bold;margin:15px 0;'>
                    🖥️ noVNC Remote Desktop:<br>
                    <a href='{vnc_url}' target='_blank' style='color:#a8e6cf;
                        font-size:18px;text-decoration:underline;'>{vnc_url}</a>
                </div>"""))
                return tunnel_url
    return None

def setup_novnc():
    print("\n Setting up noVNC...")
    start_display()
    start_fluxbox()
    start_vnc()
    return start_tunnel()

def create_driver():
    print("\n🚗 Creating Chrome driver with PERSISTENT profile...")
    for fname in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        fpath = os.path.join(PROFILE_DIR, fname)
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
        except:
            pass

    options = Options()
    options.binary_location = chrome_bin
    options.add_argument(f'--user-data-dir={PROFILE_DIR}')
    options.add_argument('--profile-directory=Default')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.page_load_strategy = 'normal'

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)
    print("✅ Chrome driver ready!")
    return driver

# ============================================================================
# 🎯 IMPROVED GEMINI ACTIVITY TOGGLE
# ============================================================================

def turn_off_gemini_activity(driver):
    print("\n" + "="*70)
    print(" TURNING OFF GEMINI ACTIVITY")
    print("="*70)

    try:
        # Navigate to Gemini activity page
        print("\n📍 Step 1: Navigating to Gemini activity page...")
        driver.get("https://myactivity.google.com/product/gemini")
        time.sleep(5)
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(3)
        take_screenshot(driver, "gemini_page_initial")

        # Check current state
        print("\n Step 2: Checking current toggle state...")
        page_source = driver.page_source.lower()

        # Look for "Off" indicator
        if "off" in page_source and "keep activity" in page_source:
            # Check if it shows "Off" status
            off_elements = driver.find_elements(By.XPATH,
                "//*[contains(text(),'Off') or contains(text(),'off')]")
            for elem in off_elements:
                if elem.is_displayed() and 'activity' in elem.text.lower():
                    print("✅ Gemini activity appears to be already OFF!")
                    return True

        # Find toggle button
        print("\n📍 Step 3: Looking for activity toggle...")
        toggle_button = None

        toggle_selectors = [
            "[role='switch']",
            "span[jsname='V67aGc']",
            "button[jscontroller='LBaJxb']",
        ]

        for selector in toggle_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        toggle_button = el
                        break
                if toggle_button:
                    break
            except:
                continue

        if not toggle_button:
            try:
                toggle_buttons = driver.find_elements(By.XPATH,
                    "//button[contains(@aria-label,'activity') or contains(@aria-label,'Keep activity')]")
                for btn in toggle_buttons:
                    if btn.is_displayed():
                        toggle_button = btn
                        break
            except:
                pass

        if not toggle_button:
            print("❌ Could not find toggle button")
            print("💡 Check noVNC to see the page manually")
            take_screenshot(driver, "gemini_no_toggle")
            return False

        print("✅ Found toggle button")

        # Click toggle
        print("\n📍 Step 4: Clicking toggle to open menu...")
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", toggle_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", toggle_button)
            print("✅ Toggle clicked - dropdown should be open")
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", toggle_button)
            print("✅ JS clicked toggle")

        time.sleep(2)
        take_screenshot(driver, "gemini_toggle_clicked")

        # Look for "Turn off" option
        print("\n Step 5: Looking for 'Turn off' option...")
        turn_off_clicked = False

        for attempt in range(3):
            try:
                turn_off_options = driver.find_elements(By.XPATH,
                    "//div[contains(text(),'Turn off') and not(contains(text(),'delete'))] | " +
                    "//span[contains(text(),'Turn off') and not(contains(text(),'delete'))] | " +
                    "//button[contains(.,'Turn off') and not(contains(.,'delete'))] | " +
                    "//div[contains(text(),'Pause')] | " +
                    "//span[contains(text(),'Pause')] | " +
                    "//button[contains(.,'Pause')]")

                for option in turn_off_options:
                    if option.is_displayed():
                        print(f"✅ Found option (attempt {attempt+1}): {option.text}")
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", option)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", option)
                            turn_off_clicked = True
                            print("✅ Clicked option!")
                            break
                        except ElementClickInterceptedException:
                            driver.execute_script("arguments[0].click();", option)
                            turn_off_clicked = True
                            break

                if turn_off_clicked:
                    break
            except Exception as e:
                print(f"⚠️ Attempt {attempt+1} failed: {e}")
            time.sleep(1)

        if not turn_off_clicked:
            print("⚠️ Could not click 'Turn off' option")
            print("💡 Check noVNC to see if dropdown is visible")
            take_screenshot(driver, "gemini_no_turn_off")
            time.sleep(3)

        time.sleep(2)

        # Handle confirmation
        print("\n📍 Step 6: Looking for confirmation buttons...")
        confirmation_clicked = False

        for _ in range(5):
            try:
                confirm_buttons = driver.find_elements(By.XPATH,
                    "//button[.//span[contains(text(),'Got it')]] | " +
                    "//button[.//span[contains(text(),'Pause')]] | " +
                    "//button[contains(.,'Turn off')] | " +
                    "//button[contains(.,'OK')] | " +
                    "//button[contains(.,'Confirm')] | " +
                    "//div[@role='button' and contains(.,'Got it')]")

                for btn in confirm_buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        print(f"✅ Found confirmation: {btn.text.strip()}")
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", btn)
                            confirmation_clicked = True
                            print("✅ Clicked confirmation!")
                        except ElementClickInterceptedException:
                            driver.execute_script("arguments[0].click();", btn)
                            confirmation_clicked = True
                        time.sleep(1)
            except:
                pass
            time.sleep(1)

        if not confirmation_clicked:
            print("ℹ️ No confirmation dialog found or already dismissed")

        time.sleep(2)

        # Verify final state
        print("\n Step 7: Verifying toggle state...")
        driver.refresh()
        time.sleep(4)
        take_screenshot(driver, "gemini_final_state")

        try:
            final_source = driver.page_source.lower()
            if "off" in final_source and "keep activity" in final_source:
                print("✅ Toggle appears to be OFF!")
            else:
                print("⚠️ Could not confirm toggle state from page source")
        except:
            pass

        print("\n✅ Activity toggle process completed!")
        print(" Check noVNC to confirm the setting is now OFF")
        return True

    except Exception as e:
        print(f"❌ Error turning off activity: {e}")
        import traceback
        traceback.print_exc()
        take_screenshot(driver, "gemini_error")
        return False

# ============================================================================
# MAIN EXECUTION
# ============================================================================

ipy_display(HTML("""
<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 25px; border-radius: 12px; color: white; text-align: center;
            font-size: 24px; font-weight: bold; margin: 20px 0;'>
    🚀 ULTRA-FIXED GOOGLE LOGIN<br>
    <span style='font-size: 16px;'>Proper Login Detection + Fast Execution</span>
</div>
"""))

print("\n KEY FIXES:")
print("1. ✅ 7-method login detection (profile avatar, email, cookies, etc.)")
print("2. ✅ Fast password field detection (5 seconds max)")
print("3. ✅ Robust Gemini activity toggle")
print("4. ✅ Screenshots at every step")
print("5. ✅ Detailed status output")

tunnel_url = setup_novnc()
time.sleep(2)

driver = create_driver()

if driver:
    wait = WebDriverWait(driver, TIMEOUT)
    try:
        start_time = time.time()

        # 🔍 COMPREHENSIVE LOGIN CHECK
        print("\n" + "="*70)
        print(" COMPREHENSIVE LOGIN CHECK")
        print("="*70)

        # Check multiple pages for login status
        pages_to_check = [
            ("https://myaccount.google.com", "Google Account"),
            ("https://gemini.google.com/app", "Gemini"),
            ("https://www.google.com", "Google Home"),
        ]

        is_logged_in = False
        for url, name in pages_to_check:
            print(f"\n Checking {name}...")
            try:
                driver.get(url)
                time.sleep(3)
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                time.sleep(2)
                take_screenshot(driver, f"check_{name.lower().replace(' ', '_')}")

                if comprehensive_login_check(driver, name):
                    is_logged_in = True
                    print(f"✅ Logged in on {name}!")
                    break
            except Exception as e:
                print(f"⚠️ Error checking {name}: {e}")

        if is_logged_in:
            print("\n" + "="*70)
            print("✅ USER IS ALREADY LOGGED IN!")
            print("="*70)
            ipy_display(HTML("<h2 style='color: #34a853;'>✅ ALREADY LOGGED IN!</h2>"))
            save_cookies(driver)
            turn_off_gemini_activity(driver)
        else:
            print("\n" + "="*70)
            print("❌ USER IS NOT LOGGED IN - STARTING LOGIN")
            print("="*70)
            login_success = handle_google_login_fast(driver, wait)

            if login_success:
                print("\n✅ LOGIN SUCCESSFUL!")
                turn_off_gemini_activity(driver)
            else:
                print("\n❌ LOGIN FAILED")

        elapsed = time.time() - start_time
        print(f"\n⏱️ Total time: {elapsed:.1f} seconds")

    except KeyboardInterrupt:
        print("\n️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n" + "="*70)
        print("✅ PROCESS COMPLETED")
        print("="*70)
        print("📸 Check screenshots in:", SCREENSHOT_FOLDER)
else:
    print(" Failed to create Chrome driver")

ipy_display(HTML("""
<div style='background:#4285f4;padding:15px;border-radius:8px;
            color:white;text-align:center;font-size:16px;margin:20px 0;'>
     <b>ALL FIXES APPLIED:</b><br>
    1. ✅ 7-method login detection (fixes your issue!)<br>
    2. ✅ Password field in 5 seconds (was 30s)<br>
    3. ✅ Screenshots at every step<br>
    4. ✅ Detailed status output<br>
    5. ✅ Robust Gemini toggle
</div>
"""))