# Extract the full push_generation and key constants from V11
v11_path = r'C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V11_FINAL.py'
with open(v11_path, 'r', encoding='utf-8') as f:
    v11_src = f.read()

import re

# Get R2 constants block
m = re.search(r'(R2_ACCOUNT_ID\s*=.*?R2_PUBLIC_URL\s*=.*?\n)', v11_src, re.DOTALL)
if m:
    print("=== R2 constants ===")
    print(m.group(0))

# Get full push_generation
m = re.search(r'def push_generation\(.*?\ndef ', v11_src, re.DOTALL)
if m:
    print("=== push_generation ===")
    print(m.group(0)[:2000])
    
# Also check what the _finalize_job in V14 calls
v14_path = r'C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py'
with open(v14_path, 'r', encoding='utf-8') as f:
    v14_src = f.read()
m = re.search(r'def _finalize_job.*?\ndef ', v14_src, re.DOTALL)
if m:
    print("=== V14 _finalize_job ===")
    print(m.group(0)[:1500])
