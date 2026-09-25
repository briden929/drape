with open('FULL_QUEUE_WORKER_V10_FINAL.py', 'r', encoding='utf-8') as f:
    v10 = f.read()

import re
funcs = re.findall(r'def _wait_for_composer', v10)
print(funcs)
