with open('FULL_QUEUE_WORKER_V10_FINAL.py', 'r', encoding='utf-8') as f:
    v10 = f.read()

idx = v10.find('def ensure_flash_mode')
if idx != -1:
    print(v10[idx:idx+500])
