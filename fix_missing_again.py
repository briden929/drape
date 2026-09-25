import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

imports_to_add = """
import subprocess
import re
import shutil
import pickle
import base64
import io
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
try:
    from IPython.display import HTML, display as ipy_display
except:
    pass
"""

if "import subprocess" not in source:
    source = source.replace("import asyncio", imports_to_add + "\nimport asyncio")

poll_func = """
async def poll_active_downloads():
    while True:
        try:
            completed_guids = []
            for guid, dinfo in list(download_registry.items()):
                ctx = dinfo['ctx']
                staging_dir = dinfo['staging_dir']
                files_before = dinfo['files_before']
                
                if not staging_dir.exists():
                    continue
                    
                cur = set(staging_dir.iterdir())
                new_files = cur - files_before
                
                crdownloads = [f for f in new_files if f.name.endswith('.crdownload')]
                if crdownloads:
                    continue
                    
                final_files = [f for f in new_files if f.name.endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                if not final_files:
                    if time.time() - dinfo['started_at'] > DOWNLOAD_TIMEOUT_S:
                        ctx.error_message = "Download timeout"
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                        completed_guids.append(guid)
                    continue
                    
                dl_file = final_files[0]
                
                sz1 = dl_file.stat().st_size
                await asyncio.sleep(0.5)
                sz2 = dl_file.stat().st_size
                if sz1 != sz2:
                    continue
                    
                if dinfo['type'] == 'GEMINI':
                    import shutil
                    raw_path = dinfo['job_dir'] / f"{ctx.job_id}_raw{dl_file.suffix}"
                    shutil.move(str(dl_file), str(raw_path))
                    ctx.raw_path = raw_path
                    try:
                        valid, msg = validate_image_file(str(raw_path), 512, 1024)
                        if not valid:
                            raise Exception(f"Invalid raw image: {msg}")
                        ctx.transition(JobState.RAW_READY)
                    except Exception as e:
                        ctx.error_message = str(e)
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                elif dinfo['type'] == 'WMR':
                    import shutil
                    clean_path = dinfo['job_dir'] / f"{ctx.job_id}_clean{dl_file.suffix}"
                    shutil.move(str(dl_file), str(clean_path))
                    ctx.clean_path = clean_path
                    try:
                        valid, msg = validate_image_file(str(clean_path), 512, 1024)
                        if not valid:
                            raise Exception(f"Invalid clean image: {msg}")
                        ctx.transition(JobState.CLEAN_READY)
                    except Exception as e:
                        ctx.error_message = str(e)
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                completed_guids.append(guid)
                
            for g in completed_guids:
                del download_registry[g]
        except Exception as e:
            traceback.print_exc()
        await asyncio.sleep(1.0)
"""

if "async def poll_active_downloads():" not in source:
    source = source.replace("async def main():", poll_func + "\nasync def main():")

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(source)
