import re
with open('FULL_QUEUE_WORKER_V5_FINAL.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Make generation polling super fast
content = re.sub(
    r'        elapsed = now - info\["start_time"\].*?info\["next_poll"\] = now \+ interval',
    '        info["next_poll"] = now + 0.5  # SUPER FAST POLLING',
    content,
    flags=re.DOTALL
)

with open('FULL_QUEUE_WORKER_V5_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(content)
