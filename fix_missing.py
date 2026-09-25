with open('extracted.py', 'r', encoding='utf-8') as f:
    extracted = f.read()

import re
extracted = re.sub(r'def _enqueue_wmr.*?wmr_pool\.submit\(.*?loop\n    \)', '''
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
''', extracted, flags=re.DOTALL)

with open('v17_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('async def central_scheduler_loop():', extracted + '\nasync def central_scheduler_loop():')

with open('v17_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Injected missing functions")
