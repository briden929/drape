with open('FULL_QUEUE_WORKER_V6_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'pages_to_check' in line or 'Checking login status (Google Account)' in line:
        for j in range(max(0, i-5), min(i+40, len(lines))):
            print(f"{j}: {lines[j].strip().encode('ascii', 'ignore').decode('ascii')}")
        break
