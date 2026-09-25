import json
v13 = json.load(open('v13_syms.json', 'r', encoding='utf-8'))
v11 = json.load(open('v11_syms.json', 'r', encoding='utf-8'))

add("""
import heapq

class JobState:
    QUEUED = "QUEUED"
    GEMINI_ASSIGNED = "GEMINI_ASSIGNED"
    UPLOADING = "UPLOADING"
    GENERATING = "GENERATING"
    GEMINI_DOWNLOAD_CLICKED = "GEMINI_DOWNLOAD_CLICKED"
    GEMINI_DOWNLOAD_STARTED = "GEMINI_DOWNLOAD_STARTED"
    GEMINI_RESOURCE_RELEASED = "GEMINI_RESOURCE_RELEASED"
    RAW_DOWNLOADING = "RAW_DOWNLOADING"
    RAW_READY = "RAW_READY"
    WMR_QUEUED = "WMR_QUEUED"
    WMR_ASSIGNED = "WMR_ASSIGNED"
    WMR_PROCESSING = "WMR_PROCESSING"
    WMR_DOWNLOAD_CLICKED = "WMR_DOWNLOAD_CLICKED"
    WMR_DOWNLOAD_STARTED = "WMR_DOWNLOAD_STARTED"
    WMR_RESOURCE_RELEASED = "WMR_RESOURCE_RELEASED"
    CLEAN_DOWNLOADING = "CLEAN_DOWNLOADING"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    R2_UPLOADING = "R2_UPLOADING"
    R2_READY = "R2_READY"
    DB_FINALIZING = "DB_FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobContext:
    def __init__(self, job_data, future):
        self.job_data = job_data
        self.job_id = job_data.get('id', str(uuid.uuid4()))
        self.generation_id = job_data.get('generation_id', self.job_id)
        self.prompt = job_data.get('prompt', '')
        self.refs = job_data.get('refs', [])
        self.user_id = job_data.get('user_id', 'anonymous')
        self.retry_count = job_data.get('retry_count', 0)
        
        self.future = future
        self.state = JobState.QUEUED
        
        self.assigned_tid = None
        self.assigned_wmr_tab = None  # Expected format: "W0-T0"
        self.gemini_download_guid = None
        self.wmr_download_guid = None
        
        self.raw_path = None
        self.clean_path = None
        self.webp_path = None
        self.r2_png_url = None
        self.r2_webp_url = None
        
        self.error_message = None
        self.created_at = time.time()
        self.updated_at = time.time()

    def transition(self, new_state):
        self.state = new_state
        self.updated_at = time.time()
        res = f"[{self.assigned_tid}]" if self.assigned_tid is not None else ""
        if self.assigned_wmr_tab:
            res = f"[{self.assigned_wmr_tab}]"
        log(f"[JOB {self.job_id}]{res} {self.state}")

class FirstFreeBroker:
    def __init__(self):
        self.seq = 0
        self.lock = threading.Lock()
        self.free_q = []
        self.in_q = set()

    def release(self, resource_id):
        with self.lock:
            if resource_id not in self.in_q:
                self.seq += 1
                heapq.heappush(self.free_q, (self.seq, resource_id))
                self.in_q.add(resource_id)

    def acquire(self):
        with self.lock:
            if not self.free_q:
                return None
            seq, resource_id = heapq.heappop(self.free_q)
            self.in_q.remove(resource_id)
            return resource_id

    def remove(self, resource_id):
        with self.lock:
            if resource_id in self.in_q:
                self.free_q = [x for x in self.free_q if x[1] != resource_id]
                heapq.heapify(self.free_q)
                self.in_q.remove(resource_id)
""")
with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("\n" + code.split('add("""\n')[1].rsplit('""")')[0] + "\n")
