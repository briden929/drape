with open('FULL_QUEUE_WORKER_V5_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'def handle_google_login_fast' in line:
        for j in range(i, min(i+40, len(lines))):
            print(f"{j}: {lines[j].strip().encode('ascii', 'ignore').decode('ascii')}")
        break
