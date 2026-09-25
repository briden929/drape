import re
with open('final_build.py', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
for i, l in enumerate(lines[:300]):
    if "'DATABASE_URL': '" in l: lines[i] = "    'DATABASE_URL': 'postgresql://MASKED',"
    elif "'R2_ACCESS_KEY_ID': '" in l: lines[i] = "    'R2_ACCESS_KEY_ID': 'MASKED',"
    elif "'R2_SECRET_ACCESS_KEY': '" in l: lines[i] = "    'R2_SECRET_ACCESS_KEY': 'MASKED',"

    if 'MAX_CONCURRENT_TABS = 4' in l:
        lines[i] = "GEMINI_WORKERS = 4\nWMR_WORKERS = 4\nBULLMQ_CONCURRENCY = 8\nGEMINI_ADMISSION_SIZE = 4\nCHROME_WMR_WORKERS = WMR_WORKERS\nMAX_CONCURRENT_TABS = GEMINI_WORKERS"
    if 'MAX_WMR_WORKERS' in l:
        lines[i] = l.replace('MAX_WMR_WORKERS', 'CHROME_WMR_WORKERS')
    
with open('top.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines[:870]))
