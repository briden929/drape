# Check the asyncio.run issue - is there a bare asyncio.run(main()) at module level?
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if 'asyncio.run(' in line:
        print(f"L{i}: {line.rstrip()}")

print("\n--- Last 30 lines ---")
for i, line in enumerate(lines[-30:], len(lines)-30+1):
    print(f"L{i}: {line.rstrip()}")
