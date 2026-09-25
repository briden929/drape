with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "async def process_bullmq_job" in line:
        print(f"process_bullmq_job at line {i}")
    if "class FirstFreeBroker" in line:
        print(f"FirstFreeBroker at line {i}")
    if "class WmrDriverThread" in line:
        print(f"WmrDriverThread at line {i}")
