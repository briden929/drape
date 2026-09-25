# Find the real upload_to_r2 in V11 syms
import json
v11 = json.load(open('v11_syms.json', 'r', encoding='utf-8'))
v13 = json.load(open('v13_syms.json', 'r', encoding='utf-8'))

if 'upload_to_r2' in v11:
    print("=== V11 upload_to_r2 ===")
    print(v11['upload_to_r2'][:1000])
elif 'upload_to_r2' in v13:
    print("=== V13 upload_to_r2 ===")
    print(v13['upload_to_r2'][:1000])
else:
    print("Not found in v11/v13")
    
# Check auto_funcs
with open('auto_funcs.py', 'r', encoding='utf-8') as f:
    af = f.read()
if 'def upload_to_r2' in af:
    idx = af.index('def upload_to_r2')
    print("\n=== auto_funcs upload_to_r2 ===")
    print(af[idx:idx+600])
