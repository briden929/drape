import re
with open('extracted.py', 'r', encoding='utf-8') as f:
    text = f.read()

m1 = re.search(r'async def poll_active_downloads\(\):.*?(?=def _enqueue_wmr)', text, flags=re.DOTALL)
m2 = re.search(r'async def poll_wmr_workers\(\):.*?(?=async def _finalize_and_clean_job)', text, flags=re.DOTALL)
m3 = re.search(r'async def _finalize_and_clean_job\(.*', text, flags=re.DOTALL)

with open('clean_extracted.py', 'w', encoding='utf-8') as f:
    if m1: f.write(m1.group(0) + '\n\n')
    if m2: f.write(m2.group(0) + '\n\n')
    if m3: f.write(m3.group(0) + '\n\n')
    
    # Let's also include the new _enqueue_wmr logic directly here:
    enqueue_wmr = """
def _enqueue_wmr(job_id: str, dinfo: dict):
    loop = main_loop
    future = loop.create_future()
    dinfo["wmr_future"] = future
    active_wmr[job_id] = dinfo
    wmr_pool.submit_job(
        job_id,
        dinfo["tid"],
        str(dinfo["raw_path"]),
        future,
        loop
    )
    log(f"[{job_id}] WMR_QUEUE -> WMR_GLOBAL_Q")
"""
    f.write(enqueue_wmr + '\n')
print("Wrote clean_extracted.py")
