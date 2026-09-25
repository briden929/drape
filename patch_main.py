import re

with open('v12_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('asyncio.create_task(central_scheduler_loop())', 'asyncio.create_task(central_scheduler_loop())\n    asyncio.create_task(update_redis_queue_stats_loop())')
text = text.replace('V9.0 READY \ufffd CHROME-ONLY', 'V9.1 READY \u2014 CHROME-ONLY')

old_log_block = """        q = Queue(QUEUE_NAME, {'connection': REDIS_URL, 'prefix': REDIS_KEY_PREFIX})
        counts = await q.getJobCounts()
        log(f"[{WORKER_ID}] 📊 Queue status before processing {gen_id}: {counts}")
        await q.close()"""

new_log_block = """        # Queue stats handled by background update loop now"""

text = text.replace(old_log_block, new_log_block)

with open('v12_work.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Patched main and removed old logging')
