import re

with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

def count_occurrences(pattern):
    return len(re.findall(pattern, text, flags=re.MULTILINE))

print("class FirstFreeBroker:", count_occurrences(r"^class FirstFreeBroker\b"))
print("class JobContext:", count_occurrences(r"^class JobContext\b"))
print("def process_bullmq_job:", count_occurrences(r"^async def process_bullmq_job\b"))
print("def central_scheduler_loop:", count_occurrences(r"^async def central_scheduler_loop\b"))
