import json
with open('v13_funcs.json', 'r', encoding='utf-8') as f:
    funcs = json.load(f)

for name, code in funcs.items():
    if 'get_gemini_job_dir' in code and name != 'get_gemini_job_dir':
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if 'get_gemini_job_dir' in line:
                print(f"{name} uses it: {line.strip()}")
                
    if 'get_chrome_job_dir' in code and name != 'get_chrome_job_dir':
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if 'get_chrome_job_dir' in line:
                print(f"{name} uses it: {line.strip()}")
