import os
import ast

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
V14_N2N = os.path.join(ROOT, "FULL_QUEUE_WORKER_V14_N2N_FINAL.py")
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(V14_N2N, "r", encoding="utf-8") as f:
    v14_ast = ast.parse(f.read())

# 1. Define standard library imports
std_imports = ast.parse("""
import os
import sys
import time
import json
import uuid
import queue
import asyncio
import threading
import traceback
import subprocess
import importlib.util
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import heapq
from pathlib import Path
""").body

# 2. Define Bootstrap and Third-Party Imports
bootstrap_code = ast.parse("""
def bootstrap_dependencies():
    required = ["selenium", "bullmq", "boto3", "psycopg2", "PIL", "websockets", "undetected_chromedriver"]
    missing = []
    for pkg in required:
        if importlib.util.find_spec(pkg) is None:
            missing.append(pkg)
    if missing:
        print(f"[BOOTSTRAP] Installing missing packages: {missing}")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + missing, check=True)
        import importlib
        importlib.invalidate_caches()
        print("[BOOTSTRAP] Packages installed.")

bootstrap_dependencies()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc
from PIL import Image
import boto3
from psycopg2 import pool as pgpool
from bullmq import Worker, Job
""").body

# 3. Define Dataclasses & State Machine
dataclasses_code = ast.parse("""
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
""").body

# 4. Define Broker
broker_code = ast.parse("""
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
""").body

# 5. Extract logic from V14 (ignoring its own imports and old classes)
v14_keep = []
skip_names = {'JobState', 'JobContext', 'FirstFreeBroker', 'bootstrap_dependencies', 'import_runtime_dependencies'}
for node in v14_ast.body:
    if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
        continue
    if hasattr(node, 'name') and node.name in skip_names:
        continue
    # Strip inline imports inside functions to prevent shadowed NameErrors
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
        new_body = []
        for stmt in node.body:
            if isinstance(stmt, ast.Import) or isinstance(stmt, ast.ImportFrom):
                continue
            new_body.append(stmt)
        node.body = new_body
    
    if isinstance(node, ast.ClassDef):
        for class_node in node.body:
            if isinstance(class_node, ast.FunctionDef) or isinstance(class_node, ast.AsyncFunctionDef):
                new_body = []
                for stmt in class_node.body:
                    if isinstance(stmt, ast.Import) or isinstance(stmt, ast.ImportFrom):
                        continue
                    new_body.append(stmt)
                class_node.body = new_body
                
    v14_keep.append(node)

# Construct final module
final_body = std_imports + bootstrap_code + dataclasses_code + broker_code + v14_keep
final_module = ast.Module(body=final_body, type_ignores=[])

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(ast.unparse(final_module))
