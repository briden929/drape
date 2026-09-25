import re
with open('v17_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

status_func = '''
last_status_print = 0
def print_pipeline_status():
    global last_status_print
    now = time.time()
    if now - last_status_print < 2.5:
        return
    last_status_print = now

    dl_waiting = sum(1 for d in active_downloads.values() if d.get("state") == "DOWNLOAD_WAITING")
    dl_raw = sum(1 for d in active_downloads.values() if d.get("state") == "CHROME_RAW_READY")
    wmr_status = wmr_pool.status()

    print("\\n" + "=" * 68)
    print(f"PIPELINE STATUS {time.strftime('%H:%M:%S')}")
    print("=" * 68)
    
    print("\\nREDIS QUEUE")
    print(f"  WAIT={redis_queue_stats['wait']} | ACTIVE={redis_queue_stats['active']} | DELAYED={redis_queue_stats['delayed']} | PRIORITY={redis_queue_stats['prioritized']} | WAIT_CHILD={redis_queue_stats['waiting-children']}")
    
    print("\\nGEMINI ADMISSION")
    print(f"  WAIT={GEMINI_ADMISSION_Q.qsize()}")

    print("\\nGEMINI T-SLOTS")
    for tid, state, cur_jid, start_time in gemini_pool.status():
        jid = (cur_jid or "---")[:12]
        elapsed = f"{int(now - start_time)}s" if start_time > 0 else "0s"
        print(f"  T{tid} = {state:<13} {elapsed:>3}  {jid}")

    print("\\nDOWNLOADS")
    print(f"  START_WAIT={dl_waiting}")
    print(f"  RAW_READY={dl_raw}")
    
    print("\\nWMR CHROME WORKERS")
    print(f"  QUEUE={WMR_GLOBAL_Q.qsize()}")
    for wid, state, cur_jid in wmr_status:
        jid_str = (cur_jid or "---")[:12]
        print(f"  W{wid} = {state:<13}  Job={jid_str}")

    print("\\nRESULT")
    print(f"  DONE={counters['completed']} | FAIL={counters['failed']}")
    print("=" * 68 + "\\n")
'''

text = re.sub(r'last_status_print = 0\ndef print_pipeline_status\(\):.*?(?=async def central_scheduler_loop\(\):)', status_func + '\n', text, flags=re.DOTALL)

with open('v17_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Replaced print_pipeline_status")
