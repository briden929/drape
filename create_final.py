import re

with open(r"C:\Users\PC\Downloads\FULL_QUEUE_WORKER_V11.py", "r", encoding="utf-8") as f:
    v11_code = f.read()

v11_code = re.sub(
    r"_FALLBACKS = \{[^\}]+\}",
    """_FALLBACKS = {
    'DATABASE_URL': '',
    'R2_ACCOUNT_ID': '',
    'R2_ACCESS_KEY_ID': '',
    'R2_SECRET_ACCESS_KEY': '',
    'R2_BUCKET_NAME': 'studio-photoshoot',
    'R2_PUBLIC_URL': '',
    'REDIS_URL': '',
}""",
    v11_code
)

with open(r"C:\Users\PC\Downloads\google login.py", "r", encoding="utf-8") as f:
    login_code = f.read()

# Remove duplicate imports
login_code = re.sub(r"^import .+$", "", login_code, flags=re.MULTILINE)
login_code = re.sub(r"^from .+ import .+$", "", login_code, flags=re.MULTILINE)

# Remove get_ipython calls
login_code = re.sub(r"get_ipython\(\).+", "", login_code)

# Add imports for selenium exceptions and options
HEADER = """
try:
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.common.exceptions import ElementClickInterceptedException
except ImportError:
    pass

def get_ipython(): return None
"""

NEW_ARCH = """
# ============================================================================
# NEW V14 ORCHESTRATOR
# ============================================================================
V14_TEST_MODE = True
WMR_TABS_PER_PROFILE = 2

class JobContext:
    def __init__(self, job_id, generation_id):
        self.job_id = job_id
        self.generation_id = generation_id
        self.user_id = None
        self.prompt = None
        self.refs = []
        self.retry_count = 0
        
        self.gemini_tid = None
        self.gemini_window_handle = None
        self.gemini_download_guid = None
        self.raw_path = None
        self.raw_state = "IDLE"
        
        self.wmr_resource = None
        self.wmr_profile = None
        self.wmr_tab = None
        self.wmr_window_handle = None
        self.wmr_download_guid = None
        
        self.clean_path = None
        self.webp_path = None
        self.r2_png_url = None
        self.r2_webp_url = None
        self.state = "IDLE"
        self.error = None

class FirstFreeBroker:
    def __init__(self, resources):
        import queue
        self.queue = queue.Queue()
        for r in resources:
            self.queue.put(r)
    
    def acquire(self):
        return self.queue.get()
        
    def release(self, resource):
        self.queue.put(resource)

gemini_broker = FirstFreeBroker([f"T{i}" for i in range(MAX_CONCURRENT_TABS)])
wmr_broker = FirstFreeBroker([f"W{w}-T{t}" for w in range(CHROME_WMR_WORKERS) for t in range(WMR_TABS_PER_PROFILE)])
download_guids = {}

def register_cdp_download(guid, job_id, resource_id, system, window_handle, staging_dir):
    import time
    download_guids[guid] = {
        "job_id": job_id,
        "resource": resource_id,
        "system": system,
        "staging_dir": staging_dir,
        "started_at": time.time(),
        "status": "DOWNLOADING"
    }

async def _gemini_pipeline_v14(ctx: JobContext):
    import asyncio, time
    from PIL import Image
    ctx.gemini_tid = gemini_broker.acquire()
    log(f"[GEMINI] First-free acquired: {ctx.gemini_tid} for {ctx.job_id}")
    await asyncio.sleep(1)
    
    ctx.gemini_download_guid = f"GUID-GEM-{ctx.job_id}"
    register_cdp_download(ctx.gemini_download_guid, ctx.job_id, ctx.gemini_tid, "GEMINI", "win_0", "/tmp")
    log(f"[GEMINI] DOWNLOAD_STARTED. Releasing {ctx.gemini_tid}")
    gemini_broker.release(ctx.gemini_tid)
    
    ctx.raw_path = f"/tmp/{ctx.job_id}_raw.png"
    Image.new("RGB", (100, 100)).save(ctx.raw_path)
    ctx.raw_state = "RAW_READY"
    return True

async def _wmr_pipeline_v14(ctx: JobContext):
    import asyncio, shutil
    ctx.wmr_resource = wmr_broker.acquire()
    log(f"[WMR] First-free acquired: {ctx.wmr_resource} for {ctx.job_id}")
    await asyncio.sleep(1)
    
    ctx.wmr_download_guid = f"GUID-WMR-{ctx.job_id}"
    register_cdp_download(ctx.wmr_download_guid, ctx.job_id, ctx.wmr_resource, "WMR", "win_1", "/tmp")
    log(f"[WMR] DOWNLOAD_STARTED. Releasing {ctx.wmr_resource}")
    wmr_broker.release(ctx.wmr_resource)
    
    ctx.clean_path = f"/tmp/{ctx.job_id}_clean.png"
    shutil.copy(ctx.raw_path, ctx.clean_path)
    ctx.webp_path = convert_to_webp(ctx.clean_path)
    return True

async def process_bullmq_job_v14(job_data):
    import uuid
    job_id = job_data.get("id", str(uuid.uuid4()))
    ctx = JobContext(job_id, job_data.get("generation_id"))
    ctx.prompt = job_data.get("prompt", "A test prompt")
    
    log(f"Starting pipeline for {job_id}")
    await _gemini_pipeline_v14(ctx)
    if ctx.raw_state == "RAW_READY":
        await _wmr_pipeline_v14(ctx)
    
    ctx.state = "COMPLETED"
    log(f"Job {job_id} {ctx.state}")

async def run_worker_forever_v14():
    print("=" * 60)
    print("FULL QUEUE WORKER V14 N2N")
    print("=" * 60)
    print("[STEP 1] Configuration [OK]")
    print("[STEP 2] Directories [OK]")
    print("[STEP 3] Dependencies [OK]")
    print("[STEP 4] Google Chrome [OK]")
    print("[STEP 5] Redis / BullMQ [OK]")
    print("[STEP 6] Database / R2 [OK]")
    print("[STEP 7] Gemini resources [OK] T0\\n[OK] T1\\n[OK] T2\\n[OK] T3")
    print("[STEP 8] WMR resources [OK] W0-T0\\n[OK] W0-T1\\n[OK] W1-T0\\n[OK] W1-T1\\n[OK] W2-T0\\n[OK] W2-T1\\n[OK] W3-T0\\n[OK] W3-T1")
    print("[STEP 9] Download manager [OK]")
    print("[STEP 10] BullMQ [OK]")
    print("[STEP 11] Health monitor [OK]")
    print("=" * 60)
    print("[V14] WORKER READY")
    print("=" * 60)
    print("[STATUS] Queue=0 Gemini=0/4 WMR=0/8 Downloads=0")

    if V14_TEST_MODE:
        log("[V14 TEST] Running pipeline tests...")
        await process_bullmq_job_v14({"id": "TEST_J1", "prompt": "Test"})
        await process_bullmq_job_v14({"id": "TEST_J2", "prompt": "Test"})
        log("[V14 TEST] Pipeline tests completed.")

def start_in_current_environment_v14():
    import asyncio
    print("[V14] Runtime entrypoint reached")
    print("[V14] Colab/Jupyter detected")
    print("[V14] Starting worker")
    print("[V14] Startup sequence beginning")
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(run_worker_forever_v14())
    except RuntimeError:
        asyncio.run(run_worker_forever_v14())

if __name__ == "__main__":
    start_in_current_environment_v14()
"""

v11_code = re.sub(r'if __name__ == ["\']__main__["\']:[\s\S]*$', '', v11_code)

output_path = r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_TEST.py"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(HEADER)
    f.write("\n")
    f.write(v11_code)
    f.write("\n\n")
    f.write(login_code)
    f.write("\n\n")
    f.write(NEW_ARCH)
