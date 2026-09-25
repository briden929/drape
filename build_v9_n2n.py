import ast
import os
import re

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
V9_FILE = os.path.join(ROOT, "FULL_QUEUE_WORKER_V9_FINAL.py")
FINAL_FILE = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(V9_FILE, "r", encoding="utf-8") as f:
    v9_source = f.read()

# Parse V9
v9_ast = ast.parse(v9_source)

# 1. Imports and Bootstrap
new_header_code = """
import asyncio
import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import os
import pathlib
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
import mimetypes
import base64
import math
import pickle
import platform
import hmac
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import heapq

def bootstrap_dependencies():
    pkg_map = {
        "selenium": "selenium",
        "bullmq": "bullmq",
        "boto3": "boto3",
        "psycopg2": "psycopg2-binary",
        "PIL": "Pillow",
        "websockets": "websockets",
        "undetected_chromedriver": "undetected-chromedriver",
        "pyvirtualdisplay": "pyvirtualdisplay"
    }
    missing = []
    for mod, pkg in pkg_map.items():
        if importlib.util.find_spec(mod) is None:
            missing.append(pkg)
    if missing:
        print(f"[BOOTSTRAP] Installing missing dependencies: {missing}")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + missing, check=True)
        importlib.invalidate_caches()
        print("[BOOTSTRAP] Dependencies installed.")

bootstrap_dependencies()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException, StaleElementReferenceException
from PIL import Image
import boto3
import undetected_chromedriver as uc
from bullmq import Worker, Job
import psycopg2
from psycopg2 import pool as _pgpool
try:
    from IPython.display import display as ipy_display, HTML
except ImportError:
    ipy_display = print
    HTML = str
try:
    from pyvirtualdisplay import Display
except ImportError:
    Display = None
"""
header_ast = ast.parse(new_header_code).body

# 2. V14 Architecture (Dataclasses, Brokers)
arch_code = """
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

DOWNLOAD_REGISTRY: Dict[str, DownloadRecord] = {}

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
            print(f"[JOB_STATE] {self.job_id} {self.state.name} -> {new_state.name}")
            self.state = new_state
            self.updated_at = time.time()

JOB_CONTEXTS: Dict[str, JobContext] = {}

class FirstFreeBroker:
    def __init__(self):
        self._free_heap = []
        self._seq = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._known_resources = set()
        self._dead_resources = set()

    def add_resource(self, resource_id: str):
        with self._lock:
            if resource_id not in self._known_resources:
                self._known_resources.add(resource_id)
                self._seq += 1
                heapq.heappush(self._free_heap, (self._seq, resource_id))
                self._condition.notify_all()

    async def acquire(self) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._acquire_sync)

    def _acquire_sync(self) -> str:
        with self._lock:
            while not self._free_heap:
                self._condition.wait()
            _, resource_id = heapq.heappop(self._free_heap)
            return resource_id

    def release(self, resource_id: str):
        with self._lock:
            if resource_id in self._known_resources and resource_id not in self._dead_resources:
                if not any(res_id == resource_id for _, res_id in self._free_heap):
                    self._seq += 1
                    heapq.heappush(self._free_heap, (self._seq, resource_id))
                    print(f"[BROKER] Released {resource_id}")
                    self._condition.notify_all()

    def fail(self, resource_id: str):
        with self._lock:
            self._dead_resources.add(resource_id)
            print(f"[BROKER] Marked {resource_id} DEAD")

    def recover(self, resource_id: str):
        with self._lock:
            if resource_id in self._dead_resources:
                self._dead_resources.remove(resource_id)
                self._seq += 1
                heapq.heappush(self._free_heap, (self._seq, resource_id))
                print(f"[BROKER] Recovered {resource_id}")
                self._condition.notify_all()

    def is_free(self, resource_id: str) -> bool:
        with self._lock:
            return any(res_id == resource_id for _, res_id in self._free_heap)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total": len(self._known_resources),
                "free": len(self._free_heap),
                "dead": len(self._dead_resources),
                "free_items": [r for _, r in self._free_heap]
            }

GEMINI_BROKER = FirstFreeBroker()
WMR_BROKER = FirstFreeBroker()

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
"""
arch_ast = ast.parse(arch_code).body

# 3. Filter V9 Nodes
remove_funcs = {
    'find_first_idle_tab', '_free_tab', '_fail_job', 'poll_active_downloads',
    '_enqueue_wmr', 'poll_wmr_workers', '_finalize_and_clean_job',
    'assign_jobs_to_idle_tabs', '_submit_job_to_tab', 'poll_active_tabs',
    '_recover_stuck_tab', 'print_pipeline_status', 'central_scheduler_loop',
    'process_bullmq_job', 'main'
}
remove_classes = {'_PooledBorrow', 'WmrWorker'}
remove_assigns = {'_tabs', 'active_downloads', '_workers', 'pool'}

filtered_v9 = []
for node in v9_ast.body:
    if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
        continue
    if hasattr(node, 'name') and node.name in remove_funcs:
        continue
    if hasattr(node, 'name') and node.name in remove_classes:
        continue
    if isinstance(node, ast.Assign):
        if any(getattr(t, 'id', '') in remove_assigns for t in node.targets if isinstance(t, ast.Name)):
            continue
            
    # Strip inline imports inside functions (we moved everything to global!)
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
        new_body = []
        for stmt in node.body:
            if isinstance(stmt, ast.Import) or isinstance(stmt, ast.ImportFrom):
                continue
            new_body.append(stmt)
        node.body = new_body
        
    filtered_v9.append(node)

# We will inject the new orchestration logic in the next step to keep the string manageable.
final_body = header_ast + arch_ast + filtered_v9
final_module = ast.Module(body=final_body, type_ignores=[])

with open(FINAL_FILE, "w", encoding="utf-8") as f:
    f.write(ast.unparse(final_module))
