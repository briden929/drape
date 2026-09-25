with open('FULL_QUEUE_WORKER_V7_FINAL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print(f'Total lines: {len(lines)}')
for i, line in enumerate(lines):
    stripped = line.strip().encode('ascii','ignore').decode('ascii')
    if (stripped.startswith('def ') or stripped.startswith('async def ') or 
        stripped.startswith('class ') or '# STEP ' in stripped or 
        '# ====' in stripped[:6]):
        print(f'{i+1}: {stripped[:120]}')
