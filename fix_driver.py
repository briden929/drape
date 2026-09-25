with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# 1. Replace create_chrome_driver() with create_gemini_driver(tid)
driver_code = '''def create_gemini_driver(tid: int):
    worker_profile = Path(str(CHROME_PROFILE_DIR) + f"_T{tid}")
    
    if not worker_profile.exists():
        if CHROME_PROFILE_DIR.exists():
            import shutil
            log(f"[T{tid}] Cloning master Gemini profile...")
            shutil.copytree(CHROME_PROFILE_DIR, worker_profile)
        else:
            worker_profile.mkdir(parents=True, exist_ok=True)
            
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = worker_profile / fname
        if fpath.exists():
            try: fpath.unlink()
            except Exception: pass
                
    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={worker_profile}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={SCREEN_W},{SCREEN_H}")

    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-sync")
    
    dl_dir = CHROME_DL_BASE / f"T{tid}"
    dl_dir.mkdir(parents=True, exist_ok=True)
    
    prefs = {
        "download.default_directory": str(dl_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    opts.add_experimental_option("prefs", prefs)
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    drv = webdriver.Chrome(options=opts)
    try:
        drv.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        drv.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception:
        pass
        
    return drv
'''
text = re.sub(r'def create_chrome_driver\(\):.*?(?=def create_wmr_chrome_driver)', driver_code + '\n', text, flags=re.DOTALL)

with open('v13_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Replaced create_chrome_driver")
