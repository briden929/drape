# Check validate_image_file signature - it's being called with 3 args in some places
import re
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", 'r', encoding='utf-8') as f:
    source = f.read()
    
# Find all validate_image_file calls and definition
for i, line in enumerate(source.split('\n'), 1):
    if 'validate_image_file' in line:
        print(f"L{i}: {line.strip()[:100]}")
