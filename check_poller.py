with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    if 'async def poll_active_downloads(' in f.read():
        print("FOUND")
    else:
        print("MISSING")
