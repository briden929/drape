import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Add missing imports
missing_imports = """
import socket
from pyvirtualdisplay import Display
"""
source = source.replace("import psycopg2", missing_imports + "import psycopg2")

source = source.replace("poll_download_registry", "poll_active_downloads")

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(source)
