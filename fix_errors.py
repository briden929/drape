import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()
    
# ADD IMPORTS
imports = """
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

# ADD CONSTANTS
constants = """
SCREEN_W = 1280
SCREEN_H = 1024
VNC_PORT = 5900
NOVNC_PORT = 6080
CHROME_PROFILE_DIR = Path("/content/queue_worker_bundle/queue_worker_state/chrome_profile")
WMR_PROFILES_BASE = Path("/content/queue_worker_bundle/queue_worker_state/wmr_chrome_profiles")
DOWNLOAD_MIN_SIZE = 1024
DOWNLOAD_STABLE_CHECKS = 3
COOKIES_FILE = Path("/content/queue_worker_bundle/queue_worker_state/cookies.pkl")
SHORT_WAIT = 5
MAX_VERIFICATION_ATTEMPTS = 3
MAX_NEW_CHAT_RETRIES = 3
GEMINI_APP_URL = "https://gemini.google.com/app"
REFS_CACHE_DIR = Path("/content/queue_worker_bundle/queue_worker_state/refs")
QUEUE_NAME = "generations"
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"
SCREENSHOT_FOLDER = Path("/content/queue_worker_bundle/queue_worker_state/screenshots")
"""

source = source.replace("import psycopg2", imports + "\nimport psycopg2")
source = source.replace("GEMINI_WORKERS = 4", constants + "\nGEMINI_WORKERS = 4")

# Delete functions that we don't need
def delete_func(src, func_name):
    # This is a bit brittle, but we know they start with `def func_name(` and end with the next `def ` or class
    pattern = r"^(?:async )?def " + func_name + r"\(.*?(?=\n(?:async )?def |\nclass |\Z)"
    return re.sub(pattern, "", src, flags=re.DOTALL | re.MULTILINE)

for fn in ['record_dead_letter', 'fetch_generation', 'update_redis_queue_stats_loop', 
           '_enqueue_wmr', '_finalize_and_clean_job', 'poll_wmr_workers', 'print_pipeline_status', 'poll_active_downloads', 'poll_wmr_workers']:
    source = delete_func(source, fn)

# Fix remaining NameErrors
source = source.replace("active_downloads", "download_registry")
source = source.replace("active_wmr", "download_registry")
source = source.replace("counters", "{}")

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(source)
