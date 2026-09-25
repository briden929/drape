with open('v14_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

for keyword in ['create_chrome_driver', 'chrome_lock', 'tab_states', 'chrome_driver =', 'poll_active_tabs', 'assign_jobs_to_idle_tabs']:
    matches = [m.start() for m in re.finditer(re.escape(keyword), text)]
    print(f"{keyword}: {len(matches)} occurrences")
