import os

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

missing_imports = """
import shutil
import platform
import socket
import re
import io
import datetime
import pickle
import base64
import concurrent.futures

try:
    from IPython.display import display as ipy_display, HTML
except ImportError:
    ipy_display = print
    HTML = str

try:
    from pyvirtualdisplay import Display
except ImportError:
    Display = None

from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.keys import Keys
"""

# Insert right after the third-party imports block
target = "from bullmq import Worker, Job"
text = text.replace(target, target + "\n" + missing_imports)

# Remove the broken call to import_runtime_dependencies()
text = text.replace("import_runtime_dependencies()", "")

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
