# Dependency Bootstrap Analysis

## Phase A: Standard Library Only

The V14 N2N Final implements the correct 4-phase bootstrap:

```python
# PHASE A: STDLIB-ONLY IMPORTS
import asyncio, os, sys, uuid, time, queue, threading, traceback
import json, concurrent.futures, subprocess, re, shutil, pickle
import base64, io, socket, heapq, importlib, platform
from pathlib import Path
from collections import deque
from datetime import datetime
```

## Phase B: Dependency Check & Install

```python
PYTHON_DEPENDENCIES = {
    "selenium": "selenium",
    "bullmq": "bullmq",
    "psycopg2": "psycopg2-binary",
    "boto3": "boto3",
    "PIL": "Pillow",
    "websockets": "websockets",
    "requests": "requests",
}

def bootstrap_dependencies():
    # Check each package
    # If missing: subprocess.run([sys.executable, "-m", "pip", "install", ...])
    # importlib.invalidate_caches()
    # Verify all packages import successfully
```

## Phase C: Invalidate Import Caches

```python
importlib.invalidate_caches()
```

## Phase D: Import Third-Party Modules

```python
# Only AFTER bootstrap
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bullmq import Worker, Queue
from PIL import Image
import psycopg2
import boto3
```

## System Dependencies (Colab)

```
google-chrome (REQUIRED - Chrome only)
Xvfb (virtual display)
x11vnc (VNC server)
websockify (noVNC bridge)
fluxbox (window manager)
```

## KEY RULES

1. **Chrome only** - NO Microsoft Edge, NO msedgedriver
2. **sys.executable -m pip** - NOT random `pip` command
3. **Import after bootstrap** - NEVER import third-party before bootstrap
4. **invalidate_caches()** - Must be called after pip install
5. **Verify imports** - Must confirm all packages import after install

## Historical Bug: Import Before Bootstrap

Some V13/V14 versions imported `selenium` and `PIL` at the top of the file BEFORE dependency bootstrap, causing `ImportError` in fresh environments.

**Fixed in:** V14 N2N Final (Phases A-D architecture)

## Historical Bug: Random pip command

Some versions used `pip install` instead of `sys.executable -m pip install`, which could use a different Python interpreter.

**Fixed in:** V14 N2N Final

## Historical Bug: No invalidate_caches()

Some versions installed packages but didn't call `importlib.invalidate_caches()`, causing `ImportError` after pip install.

**Fixed in:** V14 N2N Final

## Required Packages

| Package | pip name | Purpose |
|---------|----------|---------|
| selenium | selenium | Chrome automation |
| bullmq | bullmq | Queue management |
| psycopg2-binary | psycopg2-binary | PostgreSQL |
| boto3 | boto3 | R2/S3 |
| Pillow | Pillow | Image processing |
| websockets | websockets | WebSocket support |
| requests | requests | HTTP requests |
| numpy | numpy | Array operations |
| pyvirtualdisplay | pyvirtualdisplay | Virtual display |
| webdriver-manager | webdriver-manager | Chrome driver |
| IPython | IPython | Colab support |
