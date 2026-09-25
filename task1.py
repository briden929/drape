with open('v19_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
import re

# Remove any update_redis_queue_stats_loop occurrences completely
text = re.sub(r'redis_queue_stats = \{.*?\}\n', '', text, flags=re.DOTALL)
text = re.sub(r'async def update_redis_queue_stats_loop\(\):.*?(?=async def central_scheduler_loop\(\):|# ============================================================================)', '', text, flags=re.DOTALL)

# Add exact single copy before central scheduler loop
redis_code = '''redis_queue_stats = {
    "wait": 0, "active": 0, "delayed": 0, "prioritized": 0, "waiting-children": 0,
}

async def update_redis_queue_stats_loop():
    from bullmq import Queue
    q = Queue(QUEUE_NAME, {"connection": REDIS_URL, "prefix": REDIS_KEY_PREFIX})
    try:
        while True:
            try:
                counts = await q.getJobCounts()
                redis_queue_stats.update({k: counts.get(k, 0) for k in redis_queue_stats.keys()})
            except asyncio.CancelledError:
                raise
            except Exception as e:
                import sys
                log(f"Redis stats update failed: {e}", file=sys.stderr)
            await asyncio.sleep(2.5)
    finally:
        try:
            await q.close()
        except Exception:
            pass

'''
text = text.replace('async def central_scheduler_loop():', redis_code + 'async def central_scheduler_loop():')

# Remove find_first_idle_tab
text = re.sub(r'def find_first_idle_tab\(\):.*?(?=def print_pipeline_status|async def central_scheduler_loop)', '', text, flags=re.DOTALL)

# Config and masking
text = text.replace('MAX_WMR_WORKERS', 'CHROME_WMR_WORKERS')
text = text.replace('MAX_CONCURRENT_TABS = 4', 'GEMINI_WORKERS = 4\nWMR_WORKERS = 4\nBULLMQ_CONCURRENCY = 8\nGEMINI_ADMISSION_SIZE = 4\nCHROME_WMR_WORKERS = 4\nMAX_CONCURRENT_TABS = 4')

text = re.sub(r'\'DATABASE_URL\': \'.*?\'', "'DATABASE_URL': 'postgresql://MASKED'", text)
text = re.sub(r'\'R2_ACCESS_KEY_ID\': \'.*?\'', "'R2_ACCESS_KEY_ID': 'MASKED'", text)
text = re.sub(r'\'R2_SECRET_ACCESS_KEY\': \'.*?\'', "'R2_SECRET_ACCESS_KEY': 'MASKED'", text)

with open('v19_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Task 1 done")
