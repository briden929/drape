import sys; sys.stdout.reconfigure(encoding="utf-8")
import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'turn_off_\s+for attempt', 'for attempt', text)
text = re.sub(r'turn_off_\s*for attempt', 'for attempt', text)
text = text.replace('turn_off_', '')

text = re.sub(r'^import hmac\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^import math\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^from datetime import datetime\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^import platform\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^import traceback\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^import types\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^from collections import defaultdict\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^import psycopg2\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^import selenium\.webdriver\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^from selenium\.webdriver\.chrome\.options import Options as ChromeOptions\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^from selenium\.webdriver\.chrome\.options import Options\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^from bullmq import Worker, Queue\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^from bullmq import Worker\n', '', text, flags=re.MULTILINE)
text = re.sub(r'^from bullmq import Queue\n', '', text, flags=re.MULTILINE)

# s3
text = re.sub(r'import boto3\n\s*s3 = boto3\.client\([^\)]+\)\n', '', text)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Manual imports cleaned!")
