import re

with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

# The regex matches starting from `class JobState(Enum):` to `WMR_BROKER = FirstFreeBroker()`
pattern = r"class JobState\(Enum\):.*?WMR_BROKER = FirstFreeBroker\(\)"
new_text = re.sub(pattern, "", text, flags=re.DOTALL)

with open("FULL_QUEUE_WORKER_FINAL.py", "w", encoding="utf-8") as f:
    f.write(new_text)

print("Removed duplicate definitions at the top.")
