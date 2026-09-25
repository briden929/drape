import re
with open('v18_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

for kw in ['create_chrome_driver', 'chrome_driver.window_handles', 'Target.createTarget', 'tab_states', 'assign_jobs_to_idle_tabs', '_create_gemini_tab', 'self.work_queue']:
    matches = list(re.finditer(re.escape(kw), text))
    if matches:
        print(f"FOUND {kw}: {len(matches)}")
