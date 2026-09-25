import asyncio
import os
import uuid
import time
import traceback
import json
from pathlib import Path
from queue import PriorityQueue
from bullmq import Worker, Queue

MAX_CONCURRENT_TABS = 4
CHROME_WMR_WORKERS = 4
GENERATION_TIMEOUT_S = 300
DOWNLOAD_TIMEOUT_S = 60
TOTAL_JOB_TIMEOUT_S = GENERATION_TIMEOUT_S + DOWNLOAD_TIMEOUT_S
DOWNLOAD_START_WINDOW_S = 30

class JobState:
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    GENERATING = "GENERATING"
    DOWNLOAD_START_WAIT = "DOWNLOAD_START_WAIT"
    DOWNLOAD_START_CONFIRMED = "DOWNLOAD_START_CONFIRMED"
    T_RELEASED = "T_RELEASED"
    BACKGROUND_DOWNLOAD = "BACKGROUND_DOWNLOAD"
    RAW_READY = "RAW_READY"
    WMR_QUEUED = "WMR_QUEUED"
    WMR_ASSIGNED = "WMR_ASSIGNED"
    PROCESSING = "PROCESSING"
    WMR_TAB_RELEASED = "WMR_TAB_RELEASED"
    CLEAN_READY = "CLEAN_READY"
    WEBP_READY = "WEBP_READY"
    R2_READY = "R2_READY"
    DB_READY = "DB_READY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobContext:
    def __init__(self, job_data):
        self.job_id = job_data.get('id', str(uuid.uuid4()))
        self.generation_id = job_data.get('generation_id', self.job_id)
        self.prompt = job_data.get('prompt', '')
        self.refs = job_data.get('refs', [])
        self.user_id = job_data.get('user_id', 'anonymous')
        self.retry_count = job_data.get('retry_count', 0)
        
        self.future = None
        self.state = JobState.QUEUED
        
        self.assigned_tid = None
        self.assigned_wmr_tab = None
        self.download_guid = None
        
        self.raw_path = None
        self.clean_png = None
        self.clean_webp = None
        
        self.error_message = None

    def transition(self, new_state):
        self.state = new_state

def resolve_future_once(main_loop, future, result, is_exception=False):
    if not future or future.done():
        return
    if main_loop.is_closed():
        return
        
    async def _resolve():
        if future.done():
            return
        if is_exception:
            future.set_exception(result)
        else:
            future.set_result(result)
            
    asyncio.run_coroutine_threadsafe(_resolve(), main_loop)
