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