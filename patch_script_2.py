import re
import sys

with open('FULL_QUEUE_WORKER_V4_ONE_CELL.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add anti-popup flags to create_chrome_driver
chrome_driver_patch = """
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-sync")
    opts.add_argument("--disable-features=IdentityConsistencyBrowserUI,SyncPromoUI")
"""
content = content.replace('    opts.add_argument("--disable-blink-features=AutomationControlled")', chrome_driver_patch)

# 2. Switch Edge to Chrome in create_edge_driver_for_worker
edge_driver_patch = """
    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={profile_dir}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-sync")
    opts.add_argument("--disable-features=IdentityConsistencyBrowserUI,SyncPromoUI")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    prefs = {
        "download.default_directory": dl_dir_str,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    opts.add_experimental_option("prefs", prefs)
    drv = webdriver.Chrome(options=opts)
"""
pattern_edge_drv = r'    opts = EdgeOptions\(\).*?drv = webdriver.Edge\(options=opts\)'
content = re.sub(pattern_edge_drv, lambda m: edge_driver_patch, content, flags=re.DOTALL)

# Also rename the logs and function names to not say "Edge" if we want, but it's okay to just leave it as EdgeWorker class 
# since it's just the WMR worker. I'll replace the log string:
content = content.replace('Launching Edge driver', 'Launching Chrome WMR driver')

# 3. Optimize the new chat logic (skip drv.get(new_url))
new_chat_patch = """
            if not new_url:
                log(f"{prefix} NEW_CHAT_URL_NOT_CHANGED (attempt {attempt}) — retrying")
                time.sleep(0.5)
                continue

            log(f"{prefix} NEW_CHAT_URL={new_url}")

            # Verify clean composer first without reloading
            if _verify_clean_composer(drv):
                log(f"{prefix} NEW_CHAT_VERIFIED ✅")
                return True
                
            # If not clean, reload the exact new URL for a clean state
            log(f"{prefix} COMPOSER NOT CLEAN — RELOADING")
            drv.get(new_url)
            time.sleep(1.0)
            
            log(f"{prefix} NEW_CHAT_RELOADED")

            # Verify clean composer again
"""
pattern_new_chat = r'            if not new_url:\n                log\(f"\{prefix\} NEW_CHAT_URL_NOT_CHANGED.*?# Verify clean composer'
content = re.sub(pattern_new_chat, lambda m: new_chat_patch, content, flags=re.DOTALL)

with open('FULL_QUEUE_WORKER_V4_ONE_CELL.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied successfully.")
