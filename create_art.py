with open('FULL_QUEUE_WORKER_V5_FINAL.py', 'r', encoding='utf-8') as f:
    content = f.read()

import os
art_path = r'C:\Users\PC\.gemini\antigravity\brain\81552632-81a7-4eef-a137-f9f74093c534\queue_worker_v5_fix.md'
with open(art_path, 'w', encoding='utf-8') as f:
    f.write("# Queue Worker V5 (Final Fix)\n\n")
    f.write("```python\n")
    f.write(content)
    f.write("\n```\n")
