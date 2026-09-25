with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

import re
m = re.search(r'def _process_job_thread.*?(?=class)', source, re.DOTALL)
if m: print(m.group(0))
