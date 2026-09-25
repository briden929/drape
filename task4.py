import re
with open('v19_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add resolve_future_once right before poll_wmr_workers
resolve_wrapper = '''
def resolve_future_once(loop, future, *, result=None, exception=None):
    def resolve():
        if future.done(): return
        if exception:
            future.set_exception(exception)
        else:
            future.set_result(result)
    loop.call_soon_threadsafe(resolve)
'''
text = text.replace('async def poll_wmr_workers():', resolve_wrapper + '\nasync def poll_wmr_workers():')

# In WmrWorker._run_loop, use resolve_future_once
text = text.replace(
    'loop.call_soon_threadsafe(future.set_result, (clean_png, webp_path))',
    'resolve_future_once(loop, future, result=(clean_png, webp_path))'
)
text = text.replace(
    'loop.call_soon_threadsafe(future.set_exception, e)',
    'resolve_future_once(loop, future, exception=e)'
)

# In process_bullmq_job, add wait_for timeout
text = text.replace(
    'return await done_future',
    'return await asyncio.wait_for(done_future, timeout=TOTAL_JOB_TIMEOUT_S)'
)

with open('v19_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Task 4 done")
