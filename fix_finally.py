with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
import re
text = re.sub(r'asyncio\.create_task\(update_redis_queue_stats_loop\(\)\)', 'redis_stats_task = asyncio.create_task(update_redis_queue_stats_loop())', text)

finally_block = '''    finally:
        if 'redis_stats_task' in locals():
            redis_stats_task.cancel()
            try:
                await redis_stats_task
            except asyncio.CancelledError:
                pass
        await worker.close()
        try:
            wmr_pool.quit_all()
        except Exception:
            pass'''
text = re.sub(r'    finally:\n        await worker\.close\(\)\n.*?pass', finally_block, text, flags=re.DOTALL)
with open('v13_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patched main finally block")
