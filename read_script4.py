with open('FULL_QUEUE_WORKER_V4_ONE_CELL.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'def _process_gen_job' in line or 'def _gen_loop' in line or 'def process_job' in line or 'def _run_gen' in line:
        print(f"{i}: {line.strip()}")
