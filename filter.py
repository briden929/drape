import re
with open('extracted.py', 'r', encoding='utf-8') as f:
    text = f.read()
    
m1 = re.search(r'async def poll_active_downloads\(\):.*?(?=def _enqueue_wmr)', text, flags=re.DOTALL)
m2 = re.search(r'async def poll_wmr_workers\(\):.*?(?=async def _finalize_and_clean_job)', text, flags=re.DOTALL)
m3 = re.search(r'async def _finalize_and_clean_job\([^)]*\):.*?(?=async def central_scheduler_loop)', text, flags=re.DOTALL)

with open('clean_extracted.py', 'w', encoding='utf-8') as f:
    if m1: f.write(m1.group(0) + '\n\n')
    if m2: f.write(m2.group(0) + '\n\n')
    if m3: f.write(m3.group(0) + '\n\n')

print("Wrote clean_extracted.py")
