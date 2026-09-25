import re
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V9.1_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

m1 = re.search(r'async def poll_active_downloads\(\):.*?(?=def _enqueue_wmr|async def poll_wmr_workers|async def assign_jobs_to_idle_tabs|async def _finalize_and_clean_job)', text, flags=re.DOTALL)
m2 = re.search(r'def _enqueue_wmr\(.*?(?=async def poll_wmr_workers|async def assign_jobs_to_idle_tabs|async def _finalize_and_clean_job)', text, flags=re.DOTALL)
m3 = re.search(r'async def poll_wmr_workers\(\):.*?(?=async def _finalize_and_clean_job|async def central_scheduler_loop)', text, flags=re.DOTALL)
m4 = re.search(r'async def _finalize_and_clean_job\(.*?(?=async def central_scheduler_loop)', text, flags=re.DOTALL)

with open('extracted.py', 'w', encoding='utf-8') as f:
    if m1: f.write(m1.group(0) + '\n\n')
    if m2: f.write(m2.group(0) + '\n\n')
    if m3: f.write(m3.group(0) + '\n\n')
    if m4: f.write(m4.group(0) + '\n\n')

print("Extracted to extracted.py")
