# Check duplicate __init__ methods - they're just class constructors, not problematic
# Also check duplicate _reg - this is a local function defined inside methods
# Let's look at the actual concerns

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find start_all duplicates
for i, line in enumerate(lines, 1):
    if 'def start_all' in line or 'def quit_all' in line:
        print(f"L{i}: {line.rstrip()}")
