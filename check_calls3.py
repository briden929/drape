with open('auto_funcs.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'get_chrome_job_dir' in line or 'get_wmr_job_dir' in line:
        print(f"L{i+1}: {line.strip()}")
