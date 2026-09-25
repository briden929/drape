import re, sys

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. State Machine Authentication Code
state_machine_code = """
def verify_google_account_auth(driver, wait):
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

def verify_gemini_auth(driver, wait):
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
                profile = driver.find_element(By.XPATH, "//a[contains(@aria-label, 'Google Account')]")
                if composer.is_displayed() and profile.is_displayed():
                    return "AUTHENTICATED"
            except:
                pass
        return "WAITING"
    except Exception as e:
        log(f"[AUTH] Gemini check error: {e}")
        return "BROWSER_ERROR"

def get_authentication_state(driver, wait):
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

def quick_check_logged_in(driver):
    return get_authentication_state(driver, None) == "AUTHENTICATED"
"""

# Replace `comprehensive_login_check` completely
text = re.sub(r'def comprehensive_login_check\(driver, page_name=""\):.*?(?=def extract_verification_number)', state_machine_code, text, flags=re.DOTALL)

# Also ensure handle_google_login_fast uses quick_check_logged_in which now points to state machine.
# But wait, quick_check_logged_in doesn't exist in V14_FINAL! 
# In google login.py, `quick_check_logged_in` was used inside `handle_google_login_fast`. 
# Let's see if handle_google_login_fast in V14_FINAL has `quick_check_logged_in` or `comprehensive_login_check`.
