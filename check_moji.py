# Check mojibake more carefully - look for raw escape sequences
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", 'rb') as f:
    raw = f.read()

# Decode to string, replacing errors
text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# Check for specific bad patterns
moji_found = []
for i, line in enumerate(lines, 1):
    if '\xa0\x8f' in line or '\xc2\xa0' in line or '\ufffd' in line or '\\xa0' in line or '\\x8f' in line or '\\x90' in line:
        moji_found.append(f"L{i}: {line.strip()[:100]}")

if moji_found:
    print(f"FOUND {len(moji_found)} mojibake lines:")
    for m in moji_found:
        print(m)
else:
    print("No raw mojibake bytes found in file")
    
# Also check for raw escaped versions in source
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", 'r', encoding='utf-8', errors='replace') as f:
    source = f.read()

escaped = []
for i, line in enumerate(source.split('\n'), 1):
    # Look for \xa0, \x8f, \x90 as literal escaped strings in code
    if '\\xa0' in line or '\\x8f' in line or '\\x90' in line:
        escaped.append(f"L{i}: {line.strip()[:100]}")

if escaped:
    print(f"\nFOUND {len(escaped)} escaped mojibake references:")
    for e in escaped:
        print(e)
else:
    print("No escaped mojibake references found")
