import re
import sys

src = 'FULL_QUEUE_WORKER_V8_FINAL.py'

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove Edge imports
content = re.sub(r'from selenium\.webdriver\.edge\.options import Options as EdgeOptions\n', '', content)
content = re.sub(r'from selenium\.webdriver\.edge\.service import Service as EdgeService\n', '', content)

# 2. Remove Microsoft Edge verification block
edge_verification_pattern = r'print\("  Verifying Microsoft Edge\.\.\."\).*?print\("  ⚠️ Edge binary not found.*?\\n"\)\n'
content = re.sub(edge_verification_pattern, '', content, flags=re.DOTALL)

# 3. Clean up other edge/Edge comments
content = content.replace('independent Edge WMR workers.', 'independent WMR workers.')
content = content.replace('EDGE_QUEUE -> Edge Worker E{worker.worker_id}', 'WMR_QUEUE -> Chrome WMR Worker W{worker.worker_id}')
content = content.replace('Edge WMR jobs have completed', 'WMR Chrome jobs have completed')
content = content.replace('Edge clean PNG', 'WMR clean PNG')

with open(src, 'w', encoding='utf-8') as f:
    f.write(content)

print("Edge remnants removed.")
