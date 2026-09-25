
import re

with open('C:/Users/PC/.gemini/antigravity/scratch/Reddis/FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    code = f.read()

lines = code.split('\n')
out = []
for i, line in enumerate(lines):
    l = line.lower()
    if 'boto3' in l or 'credit' in l or 'db.' in l or 'psycopg' in l or 'upload' in l or 's3' in l or 'r2' in l:
        out.append(f"{i+1}: {line.strip()}")

print("\n".join(out))
