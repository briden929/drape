import ast
import json
import re

with open('v13_funcs.json', 'r', encoding='utf-8') as f:
    funcs = json.load(f)

# Helper function to get exact source
def get_func(name):
    return funcs.get(name, f"# MISSING FUNCTION: {name}")

# Let's fix the tuple mismatch in get_chrome_job_dir calls!
# I will write a regex to fix `job_dir = get_chrome_job_dir` to `job_dir, incoming_dir = get_chrome_job_dir` in the orchestration.
# But wait, I'm rewriting the orchestration, so I will write the correct code natively!

v14_imports_and_constants = """# ==============================================================================
# FULL QUEUE WORKER V14 FINAL
# ==============================================================================
import asyncio
import os
import sys
import uuid
import time
import queue
import threading
import traceback
import json
import concurrent.futures
from pathlib import Path
from collections import deque
from bullmq import Worker, Queue
import psycopg2
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException

import db
import credits
import fashion_studio

MAX_CONCURRENT_TABS = 4
CHROME_WMR_WORKERS = 4
GENERATION_TIMEOUT_S = 300
DOWNLOAD_TIMEOUT_S = 60
TOTAL_JOB_TIMEOUT_S = GENERATION_TIMEOUT_S + DOWNLOAD_TIMEOUT_S
DOWNLOAD_START_WINDOW_S = 30
WMR_TABS_PER_DRIVER = 4

STATE_DIR = Path("/content/queue_worker_bundle/queue_worker_state")
CHROME_DL_BASE = Path("/content/downloads/chrome")
CHROME_STAGING_BASE = Path("/content/downloads/chrome_staging")
WMR_STAGING_BASE = Path("/content/downloads/wmr_staging")
WMR_DL_BASE = Path("/content/downloads/wmr")
FINAL_OUTPUT_BASE = Path("/content/downloads/final_output")
"""

v14_state = """
class JobState:
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    GENERATING = "GENERATING"
    DOWNLOAD_START_WAIT = "DOWNLOAD_START_WAIT"
    DOWNLOAD_START_CONFIRMED = "DOWNLOAD_START_CONFIRMED"
    BACKGROUND_DOWNLOAD = "BACKGROUND_DOWNLOAD"
    RAW_READY = "RAW_READY"
    WMR_QUEUED = "WMR_QUEUED"
    WMR_ASSIGNED = "WMR_ASSIGNED"
    PROCESSING = "PROCESSING"
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

# Globals initialized correctly
job_contexts = {}
download_registry = {}
main_loop = None
gemini_pool = None
wmr_pool = None
"""

v14_business_logic = "\n\n".join([
    get_func("get_chrome_job_dir"),
    get_func("get_wmr_job_dir"),
    get_func("get_wmr_staging_dir"),
    get_func("get_final_output_dir"),
    get_func("validate_image_file"),
    get_func("convert_to_webp"),
    get_func("upload_to_r2"),
    get_func("create_persistent_chrome_driver"),
    get_func("create_wmr_chrome_driver"),
    get_func("_click_menu_item"),
    get_func("turn_off_gemini_activity"),
    get_func("check_chrome_driver_health"),
    get_func("wait_for_attachment_chip"),
    get_func("_hover_and_download"),
    get_func("_click_download_button"),
    get_func("_wmr_find_file_input"),
    get_func("_wmr_check_status"),
    get_func("_wmr_click_download"),
    get_func("_direct_fetch_image"),
    get_func("snapshot_urls"),
    get_func("check_new_image"),
    get_func("check_new_image_lenient"),
    get_func("wait_for_image"),
    get_func("set_download_behavior"),
    get_func("check_limit_or_refusal"),
    get_func("start_new_chat"),
    get_func("click_plus_button"),
    get_func("click_create_image"),
    get_func("_in_image_mode"),
    get_func("wait_for_image_mode"),
    get_func("activate_create_image_mode"),
    get_func("select_gemini_model"),
    get_func("handle_consent"),
    get_func("click_upload_files_in_drawer"),
    get_func("find_file_input"),
    get_func("jsdrop_single"),
    get_func("save_debug_screenshot"),
    get_func("upload_images"),
    get_func("_attach_images_together"),
    get_func("_attach_one_image"),
    get_func("get_editor"),
    get_func("_strip_ws"),
    get_func("_verify_editor_content"),
    get_func("_clear_editor"),
    get_func("type_prompt"),
    get_func("click_send")
])

with open('v14_build_part1.py', 'w', encoding='utf-8') as f:
    f.write(v14_imports_and_constants + "\n" + v14_state + "\n" + v14_business_logic)
print("Part 1 generated.")
