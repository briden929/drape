import os
import re
import ast

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
V14_FILE = os.path.join(ROOT, "FULL_QUEUE_WORKER_V14_N2N_FINAL.py")

with open(V14_FILE, "r", encoding="utf-8") as f:
    v14_text = f.read()

# Remove old imports scattered inside functions to prevent NameErrors
v14_text = re.sub(r'^\s*from selenium.*?\n', '', v14_text, flags=re.MULTILINE)
v14_text = re.sub(r'^\s*import selenium.*?\n', '', v14_text, flags=re.MULTILINE)

# Remove the fake chunks we injected previously
v14_text = re.sub(r'class JobContext:.*', '', v14_text, flags=re.DOTALL) # Cut off everything from JobContext down for a moment
