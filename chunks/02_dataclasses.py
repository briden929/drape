# ================================================================================================================
# LAYER 2: DATACLASSES AND STATE MACHINE
# ================================================================================================================

class JobState(Enum):
    QUEUED = "QUEUED"
    GEMINI_RESERVED = "GEMINI_RESERVED"
    GEMINI_GENERATING = "GEMINI_GENERATING"
    RAW_DOWNLOAD_START = "RAW_DOWNLOAD_START"
    GEMINI_RELEASED = "GEMINI_RELEASED"
    RAW_DOWNLOADING = "RAW_DOWNLOADING"
    RAW_READY = "RAW_READY"
    RAW_VALIDATED = "RAW_VALIDATED"
    WMR_QUEUED = "WMR_QUEUED"
    WMR_RESERVED = "WMR_RESERVED"
    WMR_PROCESSING = "WMR_PROCESSING"
    WMR_DOWNLOAD_START = "WMR_DOWNLOAD_START"
    WMR_RELEASED = "WMR_RELEASED"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    R2_READY = "R2_READY"
    DB_FINALIZING = "DB_FINALIZING"
    DB_READY = "DB_READY"
    CREDITS_SETTLED = "CREDITS_SETTLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class DownloadRecord:
    guid: str
    job_id: str
    resource_id: str
    resource_type: str
    staging_dir: str
    expected_filename: str
    suggested_filename: Optional[str] = None
    state: str = "inProgress"
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    path: Optional[str] = None
    error: Optional[str] = None

@dataclass
class JobContext:
    job_id: str
    payload: Dict[str, Any]
    state: JobState = JobState.QUEUED
    gemini_resource: Optional[str] = None
    wmr_resource: Optional[str] = None
    raw_guid: Optional[str] = None
    wmr_guid: Optional[str] = None
    raw_path: Optional[str] = None
    clean_png_path: Optional[str] = None
    webp_path: Optional[str] = None
    r2_key: Optional[str] = None
    output_url: Optional[str] = None
    charge_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: Optional[str] = None
    completion_future: Optional[asyncio.Future] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def transition(self, new_state: JobState):
        async with self.lock:
            # Add strict transition validation here if required
            print(f"[JOB_STATE] {self.job_id} {self.state.name} -> {new_state.name}")
            self.state = new_state
            self.updated_at = time.time()

DOWNLOAD_REGISTRY: Dict[str, DownloadRecord] = {}
JOB_CONTEXTS: Dict[str, JobContext] = {}

def resolve_future_once(fut: asyncio.Future, result=None, exception=None):
    if fut and not fut.done():
        try:
            if exception:
                fut.set_exception(exception)
            else:
                fut.set_result(result)
        except asyncio.InvalidStateError:
            pass

def threadsafe_resolve_future(loop, fut: asyncio.Future, result=None, exception=None):
    loop.call_soon_threadsafe(resolve_future_once, fut, result, exception)
