with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
# Let's find resolve_future_once
import re
print("FOUND resolve:", bool(re.search(r'def resolve_future_once', content)))
print("FOUND main:", bool(re.search(r'async def main\(', content)))
