# Find upload_to_r2 in ECOM source
ecom_source = open(r'C:\Users\PC\Downloads\copy_of_ecom_combo_photoshoot_order.py', 'r', encoding='utf-8').read()
idx = ecom_source.find('def upload_to_r2')
if idx >= 0:
    print(ecom_source[idx:idx+800])
else:
    print("Not found in ECOM - searching for r2/boto3/S3")
    
import re
for match in re.finditer(r'(r2|boto3|s3_client|upload_file|put_object)', ecom_source, re.IGNORECASE):
    start = max(0, match.start()-50)
    end = min(len(ecom_source), match.end()+200)
    print(f"\n--- at pos {match.start()} ---")
    print(ecom_source[start:end])
    print()
