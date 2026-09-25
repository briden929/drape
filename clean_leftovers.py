import re
with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'async def assign_jobs_to_idle_tabs\(\):.*?def _fail_job', 'def _fail_job', text, flags=re.DOTALL)

# central_scheduler_loop rewrite
new_scheduler = '''async def central_scheduler_loop():
    while True:
        try:
            # Stage 1: Poll Chrome filesystem download watchers
            await poll_active_downloads()

            # Stage 2: Poll WMR Chrome worker completions
            await poll_wmr_workers()

            # Stage 3: Status display
            print_pipeline_status()

        except Exception as e:
            log(f"Scheduler loop error: {e}", file=sys.stderr)

        await asyncio.sleep(0.1)
'''
text = re.sub(r'async def central_scheduler_loop\(\):.*?(?=# ============================================================================)', new_scheduler + '\n', text, flags=re.DOTALL)

# In print_pipeline_status, use gemini_pool.status()
status_patch = '''    submit_count = sum(1 for w in gemini_pool.workers if w.state not in [S_IDLE, S_GEN_WAITING])
    gen_count = sum(1 for w in gemini_pool.workers if w.state == S_GEN_WAITING)'''
text = re.sub(r'    gen_count = sum\(1 for st in tab_states if st\["state"\] == S_GEN_WAITING\).*?dl_waiting = ', status_patch + '\n    dl_waiting = ', text, flags=re.DOTALL)

tab_print_patch = '''    for tid, state, cur_jid, start_time in gemini_pool.status():
        jid = (cur_jid or "---")[:12]
        elapsed = f"{int(now - start_time)}s" if start_time > 0 else "0s"
        print(f"  T{tid} = {state:<13} {elapsed:>3}  {jid}")
'''
text = re.sub(r'    for tid in range\(MAX_CONCURRENT_TABS\):.*?print\(f"  T\{tid\} = \{st\[\'state\'\]:<13\} \{elapsed:>3\}  \{jid\}"\)\n', tab_print_patch, text, flags=re.DOTALL)

with open('v13_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Cleaned up leftovers")
