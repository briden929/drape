import re
with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_redis_stats = '''async def update_redis_queue_stats_loop():
    q = None
    try:
        q = Queue(QUEUE_NAME, {'connection': REDIS_URL, 'prefix': REDIS_KEY_PREFIX})
        while True:
            try:
                counts = await q.getJobCounts()
                redis_queue_stats["wait"] = counts.get("waiting", 0)
                redis_queue_stats["active"] = counts.get("active", 0)
                redis_queue_stats["delayed"] = counts.get("delayed", 0)
                redis_queue_stats["prioritized"] = counts.get("prioritized", 0)
                redis_queue_stats["waiting-children"] = counts.get("waiting-children", 0)
            except Exception:
                pass
            await asyncio.sleep(2.5)
    except asyncio.CancelledError:
        pass
    finally:
        if q:
            await q.close()
'''
text = re.sub(r'async def update_redis_queue_stats_loop\(\):.*?(?=def print_pipeline_status\(\):)', new_redis_stats + '\n', text, flags=re.DOTALL)
with open('v13_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated Redis stats loop")
