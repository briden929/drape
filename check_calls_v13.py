import json
import re

with open('v13_syms.json', 'r', encoding='utf-8') as f:
    v13 = json.load(f)

for name, code in v13.items():
    if 'get_chrome_job_dir' in code or 'get_wmr_job_dir' in code:
        print(f"--- {name} ---")
        for line in code.split('\n'):
            if 'get_chrome_job_dir' in line or 'get_wmr_job_dir' in line:
                print(line.strip())
