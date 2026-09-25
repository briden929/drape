import re, sys

with open('v18_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Remove ALL Redis stats loops and redis_queue_stats definitions
text = re.sub(r'redis_queue_stats = \{.*?\}\n', '', text, flags=re.DOTALL)
text = re.sub(r'async def update_redis_queue_stats_loop\(\):.*?(?=async def central_scheduler_loop\(\):|# =================)', '', text, flags=re.DOTALL)

# 2. Add EXACTLY ONE Redis stats block right before central_scheduler_loop
redis_stats_code = '''
redis_queue_stats = {
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
                log(f"Redis stats update failed: {e}", file=sys.stderr)
            await asyncio.sleep(2.5)
    finally:
        try:
            await q.close()
        except Exception:
            pass
'''
text = re.sub(r'(async def central_scheduler_loop\(\):)', redis_stats_code + r'\n\n\1', text)

# 3. Remove find_first_idle_tab() completely
text = re.sub(r'def find_first_idle_tab\(\):.*?(?=def print_pipeline_status|async def central_scheduler_loop)', '', text, flags=re.DOTALL)

# 4. Fix MAX_WMR_WORKERS -> CHROME_WMR_WORKERS
text = text.replace('MAX_WMR_WORKERS', 'CHROME_WMR_WORKERS')

# 5. Mask Credentials
text = re.sub(r'\'DATABASE_URL\': \'.*?\'', "'DATABASE_URL': 'postgresql://MASKED'", text)
text = re.sub(r'\'R2_ACCESS_KEY_ID\': \'.*?\'', "'R2_ACCESS_KEY_ID': 'MASKED'", text)
text = re.sub(r'\'R2_SECRET_ACCESS_KEY\': \'.*?\'', "'R2_SECRET_ACCESS_KEY': 'MASKED'", text)

# 6. Set Canonical Configs at top (around line 50 where they usually are)
config_text = """
GEMINI_WORKERS = 4
WMR_WORKERS = 4
BULLMQ_CONCURRENCY = 8
GEMINI_ADMISSION_SIZE = 4
CHROME_WMR_WORKERS = WMR_WORKERS
MAX_CONCURRENT_TABS = GEMINI_WORKERS
"""
# Let's just define them globally
text = text.replace('MAX_CONCURRENT_TABS = 4', config_text)
text = text.replace('CHROME_WMR_WORKERS = 4', '')

with open('v18_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Step 1 done")
