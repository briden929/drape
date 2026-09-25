with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    content = f.read()
import re
print("FOUND poll:", bool(re.search(r'async def poll_active_downloads', content)))
