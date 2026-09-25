# ================================================================================================================
# LAYER 1: STARTUP / DEPENDENCY
# ================================================================================================================
import sys
import importlib.util
import subprocess
import os
import time
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from enum import Enum

# Dependency Bootstrap
def _ensure_packages():
    required = ["selenium", "bullmq", "boto3", "psycopg2", "PIL", "websockets", "undetected_chromedriver"]
    missing = []
    for pkg in required:
        if importlib.util.find_spec(pkg) is None:
            missing.append(pkg)
    if missing:
        print(f"[BOOTSTRAP] Missing packages: {missing}. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + missing, check=True)
        import importlib
        importlib.invalidate_caches()
        print("[BOOTSTRAP] Installation complete.")

_ensure_packages()

import selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from PIL import Image
import boto3
from psycopg2 import pool as pgpool
from bullmq import Worker, Job
