import re

with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Fix push_generation DB update
text = text.replace(
    "UPDATE image_generations SET output_url = %s, webp_url = %s, status = 'done', completed_at = NOW() WHERE id = %s",
    "UPDATE image_generations SET output_url = %s, webp_url = %s WHERE id = %s"
)

# 2. Fix REDIS_URL printing (secure URL masking)
pattern = r"print\(f'  Redis URL:         \{REDIS_URL\}'\)"
replacement = """from urllib.parse import urlparse
_u = urlparse(REDIS_URL or "")
print(f"  Redis: {_u.scheme}://{_u.hostname}:{_u.port or 6379} (credentials={'configured' if _u.password else 'none'})")"""
text = re.sub(pattern, replacement, text)

# 3. Truncate at the start of orchestration
truncation_point = 0
lines = text.split("\n")
for i, line in enumerate(lines):
    if line.startswith("class FirstFreeBroker") or line.startswith("class JobState") or line.startswith("import asyncio"):
        if i > 0 and lines[i-1].strip() == "":
            if i > 2000:
                truncation_point = i
                break

if truncation_point > 0:
    while "import asyncio" in lines[truncation_point-1] or "from enum" in lines[truncation_point-1]:
        truncation_point -= 1
    while lines[truncation_point-1].strip() == "":
        truncation_point -= 1
    core_lines = lines[:truncation_point]
else:
    core_lines = lines 

with open("header.txt", "r", encoding="utf-8") as h:
    header = h.read()

final_text = header + "\n" + "\n".join(core_lines)
with open("FULL_QUEUE_WORKER_FINAL_V16_PREP.py", "w", encoding="utf-8") as f:
    f.write(final_text)
