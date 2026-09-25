with open("FULL_QUEUE_WORKER_FINAL_V16_PREP.py", "r", encoding="utf-8") as f:
    text = f.read()

import re

# Replace `create_wmr_chrome_driver(worker_id: int)` with `create_wmr_chrome_driver(resource_id: str)`
pattern = r"def create_wmr_chrome_driver\(worker_id: int\) -> webdriver\.Chrome:.*?opts\.add_argument\('--no-sandbox'\)"
replacement = """def create_wmr_chrome_driver(resource_id: str) -> webdriver.Chrome:
    \"\"\"Create a dedicated Chrome WMR driver for a specific logical resource (e.g., W0-T0).\"\"\"
    staging_dir = WMR_STAGING_BASE / resource_id
    profile_dir = WMR_PROFILES_BASE / resource_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = profile_dir / fname
        if fpath.exists():
            try:
                fpath.unlink()
            except:
                pass
    dl_dir_str = str(staging_dir.resolve())
    opts = ChromeOptions()
    opts.add_argument(f'--user-data-dir={profile_dir}')
    opts.add_argument('--profile-directory=Default')
    opts.add_argument('--no-sandbox')"""

text = re.sub(pattern, replacement, text, flags=re.DOTALL)
with open("FULL_QUEUE_WORKER_FINAL_V16_PREP.py", "w", encoding="utf-8") as f:
    f.write(text)
