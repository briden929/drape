# Extract the real upload_to_r2 from V11
v11_path = r'C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V11_FINAL.py'
with open(v11_path, 'r', encoding='utf-8') as f:
    v11_src = f.read()
    
# Find R2 related
import re
# find fs_configured and upload
matches = list(re.finditer(r'def (fs_configured|_r2_client|push_generation)', v11_src))
for m in matches:
    end_pos = v11_src.find('\ndef ', m.start()+1)
    if end_pos < 0: end_pos = m.start() + 2000
    print(f"=== {m.group(1)} ===")
    print(v11_src[m.start():end_pos][:1200])
    print()
