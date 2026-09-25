import re

with open('FULL_QUEUE_WORKER_V4_ONE_CELL.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to find STEP 7 block and replace it.
# It starts at:
# # ============================================================================
# # STEP 7: GOOGLE ACCOUNT & GEMINI LOGIN VERIFICATION
# and ends right before:
# # ============================================================================
# # STEP 8: EDGE WATERMARK REMOVER POOL (4 INDEPENDENT WORKERS)

pattern = r"# ============================================================================\n# STEP 7: GOOGLE ACCOUNT & GEMINI LOGIN VERIFICATION\n# ============================================================================.*?# ============================================================================\n# STEP 8: EDGE WATERMARK REMOVER POOL \(4 INDEPENDENT WORKERS\)"

replacement = """# ============================================================================
# STEP 7: ULTRA-FIXED GOOGLE LOGIN - PROPER DETECTION + FAST EXECUTION
# ============================================================================
print("=" * 80)
print("🔐 STEP 7: VERIFYING GOOGLE / GEMINI LOGIN STATE")
print("=" * 80)

SCREENSHOT_FOLDER = "/content/login_screenshots"
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
MAX_VERIFICATION_ATTEMPTS = 3
SHORT_WAIT = 2

def is_logged_in_method_1_profile_avatar(driver):
    try:
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
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, page_text)
        if emails:
            print(f"   ✅ Method 2: Email found: {emails[0]}")
            return True
        return False
    except:
        return False

def is_logged_in_method_3_account_elements(driver):
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
    try:
        url = driver.current_url.lower()
        logged_in_patterns = ["myaccount.google.com", "accounts.google.com/b/0/", "accounts.google.com/ManageAccount"]
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
    try:
        profile_btns = driver.find_elements(By.CSS_SELECTOR, 
            "[data-is-profile-button='true'], [aria-label*='Google Account'], [aria-label*='Profile']")
        for btn in profile_btns:
            if btn.is_displayed():
                print(f"   ✅ Method 7: Profile button found!")
                return True
        return False
    except:
        return False

def comprehensive_login_check(driver, page_name=""):
    print(f"\\n🔍 Checking login status{f' ({page_name})' if page_name else ''}...")
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
    for name, method in methods:
        try:
            if method(driver): passed += 1
        except: pass
    confidence = (passed / len(methods)) * 100
    print(f"\\n   📊 Login Confidence: {passed}/{len(methods)} methods passed ({confidence:.0f}%)")
    if confidence >= 43:
        print("   ✅ CONCLUSION: USER IS LOGGED IN!")
        return True
    print("   ❌ CONCLUSION: USER IS NOT LOGGED IN")
    return False

def extract_verification_number(driver):
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        for pattern in [r'tap\\s+(\\d+)\\s+on\\s+your\\s+phone', r'then\\s+tap\\s+(\\d+)', r'verification\\s+code[:\\s]+(\\d+)', r'code[:\\s]+(\\d{2,6})', r'number[:\\s]+(\\d+)']:
            match = re.search(pattern, page_text.lower())
            if match: return match.group(1)
        return None
    except: return None

def extract_page_details(driver):
    details = {'page_text': '', 'input_fields': [], 'buttons': [], 'verification_number': None, 'headings': []}
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        details['page_text'] = body.text
        details['verification_number'] = extract_verification_number(driver)
        for field in driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[type='password'], input[type='tel']"):
            if field.is_displayed():
                details['input_fields'].append({'type': field.get_attribute('type'), 'id': field.get_attribute('id'), 'aria_label': field.get_attribute('aria-label'), 'placeholder': field.get_attribute('placeholder')})
        for btn in driver.find_elements(By.CSS_SELECTOR, "button, div[role='button']"):
            if btn.is_displayed() and (btn.text.strip() or btn.get_attribute('aria-label')):
                details['buttons'].append({'text': btn.text.strip(), 'aria_label': btn.get_attribute('aria-label')})
        for heading in driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, div[role='heading']"):
            if heading.is_displayed() and heading.text.strip(): details['headings'].append(heading.text.strip())
    except: pass
    return details

def display_page_info(details, step_name=""):
    print("\\n" + "="*70)
    print(f"📋 PAGE INFORMATION - {step_name}")
    if details['verification_number']: print(f"🔢 VERIFICATION NUMBER: {details['verification_number']} 🔢🔢")
    print("="*70)

def take_screenshot(driver, step_name):
    try:
        filename = f"{SCREENSHOT_FOLDER}/{time.strftime('%H%M%S')}_{step_name}.png"
        driver.save_screenshot(filename)
        return filename
    except: return None

def save_cookies(driver):
    try:
        with open(COOKIES_FILE, "wb") as f: pickle.dump(driver.get_cookies(), f)
        print("💾 ✅ Cookies saved locally")
        return True
    except: return False

def load_cookies(driver):
    try:
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, "rb") as f: cookies = pickle.load(f)
            driver.get("https://www.google.com")
            time.sleep(1)
            for c in cookies:
                try: driver.add_cookie(c)
                except: pass
            print("💾 ✅ Cookies loaded from local storage")
            return True
        return False
    except: return False

def detect_push_notification_verification(driver):
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        return sum(1 for ind in ["check your", "tap yes", "notification", "sent a notification", "on your phone", "verify it's you"] if ind in page_text) >= 2
    except: return False

def wait_for_push_notification_approval(driver, max_wait_seconds=60):
    checks = max_wait_seconds // 5
    for check in range(1, checks + 1):
        print(f"\\n🔍 Check {check}/{checks}")
        for remaining in range(5, 0, -1):
            print(f"\\r Waiting for approval: {remaining}s ", end='', flush=True)
            time.sleep(1)
        if comprehensive_login_check(driver, "push approval check"):
            print("\\n✅ Push notification approved!")
            return True
    return False

def handle_verification_code_with_retry(driver, wait, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            page_details = extract_page_details(driver)
            display_page_info(page_details, f"Verification Attempt {attempt}")
            if detect_push_notification_verification(driver):
                take_screenshot(driver, f"push_notification_attempt_{attempt}")
                if wait_for_push_notification_approval(driver, max_wait_seconds=60 if attempt == 1 else 30): return True
                if comprehensive_login_check(driver): return True
                continue
            
            code_input = None
            for selector in ["input[type='tel']", "input[name='totpPin']", "input[id='totpPin']", "input[type='text'][name='pin']", "input[aria-label*='code']"]:
                try:
                    for field in driver.find_elements(By.CSS_SELECTOR, selector):
                        if field.is_displayed():
                            code_input = field
                            break
                    if code_input: break
                except: continue
            if not code_input:
                time.sleep(2)
                continue
            
            take_screenshot(driver, f"verification_code_attempt_{attempt}_before")
            otp = input(f"Enter Verification Code (Attempt {attempt}/{max_attempts}): ").strip()
            if not otp: continue
            code_input.clear()
            code_input.send_keys(otp)
            time.sleep(SHORT_WAIT)
            
            next_found = False
            for selector in ["//button[@id='next']", "//button[contains(., 'Next')]", "//button[@type='submit']"]:
                try:
                    btn = driver.find_element(By.XPATH, selector)
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        next_found = True
                        break
                except: continue
            if not next_found: code_input.send_keys(Keys.RETURN)
            
            time.sleep(4)
            take_screenshot(driver, f"verification_code_attempt_{attempt}_after_submit")
            if comprehensive_login_check(driver): return True
            time.sleep(2)
        except: time.sleep(2)
    return False

def handle_google_login_fast(driver, wait):
    try:
        print("\\n" + "="*70)
        print("🔐 FAST GOOGLE LOGIN")
        print("="*70)
        if load_cookies(driver):
            driver.refresh()
            time.sleep(2)
            if comprehensive_login_check(driver, "after cookies"):
                save_cookies(driver)
                return True
                
        driver.get("https://accounts.google.com/")
        time.sleep(3)
        if comprehensive_login_check(driver, "accounts page"):
            save_cookies(driver)
            return True
            
        email = input("Enter your EMAIL: ").strip()
        if not email: return False
        
        email_field = wait.until(EC.presence_of_element_located((By.ID, "identifierId")))
        email_field.clear()
        email_field.send_keys(email)
        time.sleep(1)
        next_btn = wait.until(EC.element_to_be_clickable((By.ID, "identifierNext")))
        driver.execute_script("arguments[0].click();", next_btn)
        time.sleep(3)
        
        if comprehensive_login_check(driver, "after email"):
            save_cookies(driver)
            return True
            
        pwd_field = None
        for by, selector in [(By.NAME, "Passwd"), (By.CSS_SELECTOR, "input[type='password']"), (By.CSS_SELECTOR, "#password input")]:
            try:
                pwd_field = WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, selector)))
                if pwd_field and pwd_field.is_displayed(): break
            except: continue
        
        if not pwd_field:
            try: pwd_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "Passwd")))
            except: return False
            
        password = input("Enter your PASSWORD: ").strip()
        if not password: return False
        
        pwd_field.clear()
        pwd_field.send_keys(password)
        time.sleep(1)
        pwd_next = wait.until(EC.element_to_be_clickable((By.ID, "passwordNext")))
        driver.execute_script("arguments[0].click();", pwd_next)
        time.sleep(4)
        
        if comprehensive_login_check(driver, "after password"):
            save_cookies(driver)
            return True
            
        url = driver.current_url
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "challenge" in url or "verify" in url or "check your" in page_text:
            if handle_verification_code_with_retry(driver, wait, MAX_VERIFICATION_ATTEMPTS):
                save_cookies(driver)
                return True
            return False
            
        if comprehensive_login_check(driver, "final"):
            save_cookies(driver)
            return True
            
        if input("Are you logged in? (y/n): ").strip().lower() == 'y':
            save_cookies(driver)
            return True
        return False
    except Exception as e:
        print(f"\\n❌ ERROR: {e}")
        return False

def turn_off_gemini_activity(driver):
    print("\\n" + "="*70)
    print(" TURNING OFF GEMINI ACTIVITY")
    print("="*70)
    try:
        driver.get("https://myactivity.google.com/product/gemini")
        time.sleep(5)
        WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(3)
        page_source = driver.page_source.lower()
        if "off" in page_source and "keep activity" in page_source:
            for elem in driver.find_elements(By.XPATH, "//*[contains(text(),'Off') or contains(text(),'off')]"):
                if elem.is_displayed() and 'activity' in elem.text.lower():
                    print("✅ Gemini activity appears to be already OFF!")
                    return True
                    
        toggle_button = None
        for selector in ["[role='switch']", "span[jsname='V67aGc']", "button[jscontroller='LBaJxb']"]:
            try:
                for el in driver.find_elements(By.CSS_SELECTOR, selector):
                    if el.is_displayed():
                        toggle_button = el
                        break
                if toggle_button: break
            except: continue
            
        if not toggle_button:
            for btn in driver.find_elements(By.XPATH, "//button[contains(@aria-label,'activity') or contains(@aria-label,'Keep activity')]"):
                if btn.is_displayed():
                    toggle_button = btn
                    break
                    
        if not toggle_button: return False
        
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", toggle_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", toggle_button)
        except: driver.execute_script("arguments[0].click();", toggle_button)
        
        time.sleep(2)
        turn_off_clicked = False
        for attempt in range(3):
            try:
                for option in driver.find_elements(By.XPATH, "//div[contains(text(),'Turn off') and not(contains(text(),'delete'))] | //span[contains(text(),'Turn off') and not(contains(text(),'delete'))] | //button[contains(.,'Turn off') and not(contains(.,'delete'))] | //div[contains(text(),'Pause')] | //span[contains(text(),'Pause')] | //button[contains(.,'Pause')]"):
                    if option.is_displayed():
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", option)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", option)
                            turn_off_clicked = True
                            break
                        except:
                            driver.execute_script("arguments[0].click();", option)
                            turn_off_clicked = True
                            break
                if turn_off_clicked: break
            except: pass
            time.sleep(1)
            
        time.sleep(2)
        for _ in range(5):
            try:
                for btn in driver.find_elements(By.XPATH, "//button[.//span[contains(text(),'Got it')]] | //button[.//span[contains(text(),'Pause')]] | //button[contains(.,'Turn off')] | //button[contains(.,'OK')] | //button[contains(.,'Confirm')] | //div[@role='button' and contains(.,'Got it')]"):
                    if btn.is_displayed() and btn.is_enabled():
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", btn)
                        except: driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
            except: pass
            time.sleep(1)
            
        driver.refresh()
        time.sleep(4)
        print("✅ Activity toggle process completed!")
        return True
    except: return False

# Execute Login
wait = WebDriverWait(chrome_driver, TIMEOUT)
is_logged_in = False
for url, name in [("https://myaccount.google.com", "Google Account"), ("https://gemini.google.com/app", "Gemini")]:
    try:
        chrome_driver.get(url)
        time.sleep(3)
        WebDriverWait(chrome_driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(2)
        if comprehensive_login_check(chrome_driver, name):
            is_logged_in = True
            break
    except: pass

if is_logged_in:
    print("✅ ALREADY LOGGED IN!")
    save_cookies(chrome_driver)
    turn_off_gemini_activity(chrome_driver)
else:
    print("❌ USER IS NOT LOGGED IN - STARTING LOGIN")
    if handle_google_login_fast(chrome_driver, wait):
        print("✅ LOGIN SUCCESSFUL!")
        turn_off_gemini_activity(chrome_driver)
    else:
        print("❌ LOGIN FAILED. Please login manually via noVNC!")
        t0 = time.time()
        while time.time() - t0 < 180:
            if comprehensive_login_check(chrome_driver):
                print("✅ Login detected manually! Session saved.")
                save_cookies(chrome_driver)
                turn_off_gemini_activity(chrome_driver)
                break
            time.sleep(3.0)

print()

# ============================================================================
# STEP 8: EDGE WATERMARK REMOVER POOL (4 INDEPENDENT WORKERS)"""

new_content = re.sub(pattern, lambda m: replacement.replace('\\\\', '\\'), content, flags=re.DOTALL)

with open('FULL_QUEUE_WORKER_V4_ONE_CELL.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
    
print("File patched successfully!")
