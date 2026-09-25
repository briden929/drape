import re

with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

print("Initial len:", len(text))

# Let's verify we can find the blocks to replace
tab_states_match = re.search(r'tab_states = \[\](.*?)chrome_lock = asyncio\.Lock\(\)', text, re.DOTALL)
if tab_states_match: print("Found tab_states")

poll_active_tabs_match = re.search(r'async def poll_active_tabs\(\):.*?def open_new_chat_and_reload', text, re.DOTALL)
if poll_active_tabs_match: print("Found poll_active_tabs")

assign_jobs_match = re.search(r'async def assign_jobs_to_idle_tabs\(\):.*?async def _submit_job_to_tab', text, re.DOTALL)
if assign_jobs_match: print("Found assign_jobs_to_idle_tabs")

submit_job_match = re.search(r'async def _submit_job_to_tab\(tid: int\):.*?def verify_generation_started', text, re.DOTALL)
if submit_job_match: print("Found _submit_job_to_tab")

