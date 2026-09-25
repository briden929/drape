import re, sys

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. State Machine Authentication Code
state_machine_code = """
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
"""

start_login = text.find("def comprehensive_login_check")
end_login = text.find("def extract_verification_number")

if start_login == -1 or end_login == -1:
    print("Could not find comprehensive_login_check bounds")
    sys.exit(1)

# Safely replace login logic
text = text[:start_login] + state_machine_code + "\n\n" + text[end_login:]

# 2. Fix the Entrypoint (No execution namespace manipulation, WORKER_MAIN_TASK uniqueness)
new_entrypoint = """
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
    import asyncio
    log("[V14] Runtime entrypoint reached")
    log("[V14] Colab/Jupyter detected")
    log("[V14] Starting worker")
    log("[V14] Startup sequence beginning")
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
"""

# Replace from `def start_in_current_environment():` to the end of the file
start_env = text.find("def start_in_current_environment():")
if start_env != -1:
    text = text[:start_env] + new_entrypoint
else:
    print("Could not find start_in_current_environment")
    sys.exit(1)

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_FINAL.py", "w", encoding="utf-8") as f:
    f.write(text)

import py_compile
try:
    py_compile.compile(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_FINAL.py", doraise=True)
    print("Compile PASS")
except Exception as e:
    print(f"Compile FAIL: {e}")
    sys.exit(1)
