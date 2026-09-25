import re
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V12_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(
    r'(\s+)hover_ok = _hover_and_dl_single_click',
    r'\1files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()\1hover_ok = _hover_and_dl_single_click',
    text
)

text = re.sub(
    r'\s+files_before = set\(os\.listdir\(incoming_dir\)\) if incoming_dir\.exists\(\) else set\(\)\n(\s+dl_confirmed = False)',
    r'\n\1',
    text
)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V12_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)
