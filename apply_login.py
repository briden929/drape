import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

login_flow = """
def perform_startup_login(driver):
    log("============================================================")
    log("🔐 GOOGLE LOGIN STATE MACHINE")
    log("============================================================")
    
    driver.get("https://myaccount.google.com/")
    time.sleep(2)
    
    if comprehensive_login_check(driver, "myaccount.google.com"):
        log("STATE: GOOGLE_LOGGED_IN")
    else:
        log("STATE: GOOGLE_LOGIN_REQUIRED")
        log("Navigating to accounts.google.com...")
        driver.get("https://accounts.google.com/")
        time.sleep(2)
        
        if comprehensive_login_check(driver, "accounts.google.com"):
            log("STATE: GOOGLE_LOGGED_IN")
        else:
            # We are in automated mode, so we cannot do get_user_input directly if running in background.
            # But we can wait a bit for manual intervention and report it.
            log("MANUAL ACTION REQUIRED: Please log into Google in the open Chrome window.")
            log("STATE: GOOGLE_VERIFICATION_REQUIRED")
            
            # Wait up to 5 minutes for manual login
            logged_in = False
            for _ in range(30):
                time.sleep(10)
                if comprehensive_login_check(driver, "manual check"):
                    logged_in = True
                    break
            
            if not logged_in:
                log("STATE: GOOGLE_ACCOUNT_ERROR - Timeout waiting for manual login.")
                raise Exception("Manual Google verification required but timed out.")
            
            log("STATE: GOOGLE_LOGGED_IN (Manual verification successful)")
            
    log("Navigating to Gemini...")
    driver.get("https://gemini.google.com/app")
    time.sleep(3)
    
    # Check Gemini specific states
    page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    if "not supported" in page_text or "unavailable" in page_text:
        log("STATE: GEMINI_UNAVAILABLE")
        raise Exception("Gemini is not available for this account/region.")
        
    log("STATE: GEMINI_LOADING")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "rich-textarea, div[data-placeholder='Enter a prompt here']"))
        )
        log("STATE: GEMINI_READY")
    except:
        log("STATE: GEMINI_UNAVAILABLE (Prompt box not found)")
        raise Exception("Failed to reach GEMINI_READY state.")

    # Save cookies just in case
    try:
        import pickle
        with open(COOKIES_FILE, "wb") as f:
            pickle.dump(driver.get_cookies(), f)
    except Exception as e:
        log(f"Warning: Could not save cookies: {e}")
        
    return True

def check_gemini_health_light(driver):
    \"\"\"Rule #10: lightweight health check during jobs\"\"\"
    try:
        # Just check if we still have the prompt box and current url is correct
        if "gemini.google.com/app" not in driver.current_url:
            return False
        driver.find_element(By.CSS_SELECTOR, "rich-textarea, div[data-placeholder='Enter a prompt here']")
        return True
    except:
        return False
"""

# Inject this before startup_preflight
source = source.replace("def startup_preflight():", login_flow + "\ndef startup_preflight():")

# Now update startup_preflight to call it
new_preflight = """def startup_preflight():
    global chrome_driver
    print("Checking directories...")
    for d in [STATE_DIR, CHROME_DL_BASE, CHROME_STAGING_BASE, WMR_STAGING_BASE, WMR_DL_BASE, FINAL_OUTPUT_BASE]:
        d.mkdir(parents=True, exist_ok=True)
        
    print("Checking Redis URL...")
    assert os.environ.get('REDIS_TUNNEL_URL'), "REDIS_TUNNEL_URL not set"
    
    print("Checking DB...")
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as e:
        print(f"Warning DB check failed: {e}")
            
    print("Checking Chrome Driver creation...")
    chrome_driver = create_persistent_chrome_driver()
    check_chrome_driver_health(chrome_driver)
    
    perform_startup_login(chrome_driver)"""
    
source = re.sub(r'def startup_preflight\(\):.*?check_chrome_driver_health\(chrome_driver\)', new_preflight, source, flags=re.DOTALL)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(source)
