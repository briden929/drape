with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# find poll_active_downloads
m1 = re.search(r'async def poll_active_downloads\(\):.*?(?=def _enqueue_wmr|async def poll_wmr_workers|async def assign_jobs_to_idle_tabs)', text, flags=re.DOTALL)
if m1: print("Found poll_active_downloads")

m2 = re.search(r'def _enqueue_wmr\(.*?(?=async def poll_wmr_workers|async def assign_jobs_to_idle_tabs)', text, flags=re.DOTALL)
if m2: print("Found _enqueue_wmr")

m3 = re.search(r'async def poll_wmr_workers\(\):.*?(?=async def _finalize_and_clean_job)', text, flags=re.DOTALL)
if m3: print("Found poll_wmr_workers")

m4 = re.search(r'async def _finalize_and_clean_job\(.*?(?=async def central_scheduler_loop)', text, flags=re.DOTALL)
if m4: print("Found _finalize_and_clean_job")

# Output to a file so we can view it properly
with open('extracted_funcs.py', 'w', encoding='utf-8') as out:
    if m1: out.write(m1.group(0) + "\n\n")
    if m2: out.write(m2.group(0) + "\n\n")
    if m3: out.write(m3.group(0) + "\n\n")
    if m4: out.write(m4.group(0) + "\n\n")

print("Extracted to extracted_funcs.py")
