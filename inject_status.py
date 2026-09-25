with open('v14_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

status_func = '''
# ============================================================================
# COMPACT PIPELINE STATUS
# ============================================================================
last_status_print = 0
def print_pipeline_status():
    global last_status_print
    now = time.time()
    if now - last_status_print < 2.5:
        return
    last_status_print = now

    submit_count = sum(1 for w in gemini_pool.workers if w.state not in [S_IDLE, S_GEN_WAITING])
    gen_count = sum(1 for w in gemini_pool.workers if w.state == S_GEN_WAITING)
    
    dl_waiting = sum(1 for d in active_downloads.values() if d.get("state") == "DOWNLOAD_WAITING")
    dl_raw = sum(1 for d in active_downloads.values() if d.get("state") == "CHROME_RAW_READY")
    
    wmr_status = wmr_pool.status()
    wmr_process = sum(1 for _, state, _ in wmr_status if state != "IDLE")

    print("\\n" + "=" * 60)
    print(f"PIPELINE {time.strftime('%H:%M:%S')}")
    print("\\nREDIS")
    print(f"  WAIT={redis_queue_stats['wait']} ACTIVE={redis_queue_stats['active']} DELAYED={redis_queue_stats['delayed']} PRIORITY={redis_queue_stats['prioritized']}")
    
    print("\\nGEMINI ADMISSION")
    print(f"  WAIT={GEMINI_ADMISSION_Q.qsize()}")
    
    print("\\nGEMINI")
    for tid, state, cur_jid, start_time in gemini_pool.status():
        jid = (cur_jid or "---")[:12]
        elapsed = f"{int(now - start_time)}s" if start_time > 0 else "0s"
        print(f"  T{tid}={state:<13} {elapsed:>3} {jid}")

    print("\\nDOWNLOAD")
    print(f"  START_WAIT={dl_waiting}")
    print(f"  RAW_READY={dl_raw}")
    
    print("\\nWMR")
    print(f"  QUEUE={WMR_GLOBAL_Q.qsize()}")
    for wid, state, cur_jid in wmr_status:
        jid_str = (cur_jid or "---")[:12]
        print(f"  W{wid}={state:<13} Job={jid_str}")

    print("\\nRESULT")
    print(f"  DONE={counters['completed']} FAIL={counters['failed']}")
    print("=" * 60 + "\\n")
'''

text = text.replace('async def central_scheduler_loop():', status_func + '\nasync def central_scheduler_loop():')

with open('v14_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Injected status func")
