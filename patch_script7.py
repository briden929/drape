import re

with open('FULL_QUEUE_WORKER_V6_FINAL.py', 'r', encoding='utf-8') as f:
    content = f.read()

cleanup_code = '''def create_chrome_driver():
    # 🧹 CRITICAL: Delete SingletonLocks to prevent Chrome from loading a temporary blank profile!
    import shutil
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = CHROME_PROFILE_DIR / fname
        if fpath.exists():
            try:
                fpath.unlink()
            except Exception as e:
                print(f'Warning: Could not delete {fname}: {e}')
                
    opts = ChromeOptions()'''

content = content.replace('def create_chrome_driver():\n    opts = ChromeOptions()', cleanup_code)

cleanup_code_wmr = '''def create_edge_driver_for_worker(worker_id: int, dl_dir: str):
    profile_dir = EDGE_PROFILES_BASE / f'worker_{worker_id}'
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    # 🧹 Clean locks for WMR profile too
    for fname in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        fpath = profile_dir / fname
        if fpath.exists():
            try: fpath.unlink()
            except: pass

    dl_dir_str = str(Path(dl_dir).resolve())'''

content = re.sub(r'def create_edge_driver_for_worker.*?dl_dir_str = str\(Path\(dl_dir\)\.resolve\(\)\)', cleanup_code_wmr, content, flags=re.DOTALL)

with open('FULL_QUEUE_WORKER_V7_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('V7 script created.')
