# Look for R2 upload in the V11 source directly
v11_path = r'C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V11_FINAL.py'
try:
    with open(v11_path, 'r', encoding='utf-8') as f:
        v11_src = f.read()
    idx = v11_src.find('def upload_to_r2')
    if idx >= 0:
        print("=== V11 upload_to_r2 ===")
        print(v11_src[idx:idx+1200])
    else:
        print("Not in V11, checking for boto3")
        import re
        for m in re.finditer(r'boto3|put_object|upload_file|R2_ACCOUNT', v11_src):
            print(v11_src[max(0, m.start()-20):m.end()+200])
            print("---")
except FileNotFoundError:
    print("V11 not found")
