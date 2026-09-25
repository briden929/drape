import re, sys

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_TEST.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Replace Login Check
new_login_code = """
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
        print(f"[AUTH] Google check error: {e}")
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
        print(f"[AUTH] Gemini check error: {e}")
        return "BROWSER_ERROR"

def get_authentication_state(driver, wait):
    state_a = verify_google_account_auth(driver, wait)
    print(f"[AUTH] Google Account State: {state_a}")
    if state_a in ["NOT_AUTHENTICATED", "CHALLENGE_REQUIRED", "BROWSER_ERROR"]:
        print(f"[AUTH] FINAL: {state_a}")
        return state_a
    
    state_b = verify_gemini_auth(driver, wait)
    print(f"[AUTH] Gemini State: {state_b}")
    if state_b == "AUTHENTICATED" and state_a == "AUTHENTICATED":
        print("[AUTH] Composer: FOUND")
        print("[AUTH] Attachment Control: FOUND")
        print("[AUTH] Account/Profile: FOUND")
        print("[AUTH] Sign-in Wall: NOT FOUND")
        print("[AUTH] Challenge: NOT FOUND")
        print("[AUTH] FINAL: AUTHENTICATED")
        return "AUTHENTICATED"
    
    if state_b in ["NOT_AUTHENTICATED", "CHALLENGE_REQUIRED", "BROWSER_ERROR"]:
        print("[AUTH] Composer: NOT FOUND")
        print(f"[AUTH] FINAL: {state_b}")
        return state_b
        
    print("[AUTH] FINAL: UNKNOWN")
    return "UNKNOWN"

def check_gemini_login_v14(driver):
    state = get_authentication_state(driver, None)
    return state == "AUTHENTICATED"
"""

# Replace `check_gemini_login_v14` and `comprehensive_login_check_v14` logic
text = re.sub(r'def check_gemini_login_v14.*?return False', new_login_code, text, flags=re.DOTALL, count=1)
text = re.sub(r'def comprehensive_login_check_v14.*?return confidence >= 43\n', '', text, flags=re.DOTALL)

# 2. Fix the pkill logic to be safe
text = text.replace('run_cmd("pkill -f Xvfb", "pkill xvfb")', '# Xvfb handled targetedly')
text = text.replace('run_cmd("pkill -f x11vnc", "pkill x11vnc")', '# x11vnc handled targetedly')
text = text.replace('run_cmd("pkill -f websockify", "pkill websockify")', '# websockify handled targetedly')
text = text.replace('run_cmd("pkill -f fluxbox", "pkill fluxbox")', '# fluxbox handled targetedly')
text = text.replace('run_cmd("pkill -f cloudflared", "pkill cloudflared")', '# cloudflared handled targetedly')
text = text.replace('subprocess.run("pkill -f Xvfb"', '# subprocess.run("pkill -f Xvfb"')
text = text.replace('subprocess.run("pkill -f fluxbox"', '# subprocess.run("pkill -f fluxbox"')
text = text.replace('subprocess.run("pkill -f x11vnc"', '# subprocess.run("pkill -f x11vnc"')
text = text.replace('subprocess.run("pkill -f websockify"', '# subprocess.run("pkill -f websockify"')
text = text.replace('subprocess.run("pkill -f cloudflared"', '# subprocess.run("pkill -f cloudflared"')

# 3. Fix the entrypoint to use WORKER_MAIN_TASK
new_entrypoint = """
WORKER_MAIN_TASK = None

def worker_done_callback(task):
    if task.cancelled():
        print("[V14] MAIN TASK FAILED")
        print("[V14] Exception: CancelledError")
    elif task.exception():
        print("[V14] MAIN TASK FAILED")
        print(f"[V14] Exception: {task.exception()}")
        import traceback
        try:
            task.result()
        except Exception:
            traceback.print_exc()
    else:
        print("[V14] MAIN TASK COMPLETED")

def start_worker():
    global WORKER_MAIN_TASK
    import asyncio
    print("[V14] Runtime entrypoint reached")
    print("[V14] Colab/Jupyter detected")
    print("[V14] Starting worker")
    print("[V14] Startup sequence beginning")
    try:
        loop = asyncio.get_running_loop()
        if WORKER_MAIN_TASK is not None and not WORKER_MAIN_TASK.done():
            print("[V14] Worker already running")
            print("[V14] Existing task reused")
            return WORKER_MAIN_TASK
        WORKER_MAIN_TASK = loop.create_task(run_worker_forever_v14())
        WORKER_MAIN_TASK.add_done_callback(worker_done_callback)
        return WORKER_MAIN_TASK
    except RuntimeError:
        asyncio.run(run_worker_forever_v14())

if __name__ == "__main__":
    start_worker()
"""

# Replace the old entrypoint
text = re.sub(r'def start_in_current_environment_v14\(\):.*', new_entrypoint, text, flags=re.DOTALL)

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_FINAL.py", "w", encoding="utf-8") as f:
    f.write(text)

import py_compile
try:
    py_compile.compile(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_FINAL.py", doraise=True)
    print("Compile PASS")
except Exception as e:
    print(f"Compile FAIL: {e}")
    sys.exit(1)
