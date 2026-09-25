import sys, re
sys.stdout.reconfigure(encoding='utf-8')
with open('v12_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_sig = 'def print_pipeline_status():'
end_sig = 'async def central_scheduler_loop():'
start_idx = text.find(start_sig)
end_idx = text.find(end_sig)

if start_idx == -1 or end_idx == -1:
    print('Could not find status print function')
    exit(1)

new_code = '''
redis_queue_stats = {"wait": 0, "active": 0, "delayed": 0, "prioritized": 0, "waiting-children": 0}

async def update_redis_queue_stats_loop():
    while True:
        try:
            q = Queue(QUEUE_NAME, {'connection': REDIS_URL, 'prefix': REDIS_KEY_PREFIX})
            counts = await q.getJobCounts()
            redis_queue_stats["wait"] = counts.get("waiting", 0)
            redis_queue_stats["active"] = counts.get("active", 0)
            redis_queue_stats["delayed"] = counts.get("delayed", 0)
            redis_queue_stats["prioritized"] = counts.get("prioritized", 0)
            redis_queue_stats["waiting-children"] = counts.get("waiting-children", 0)
            await q.close()
        except Exception:
            pass
        await asyncio.sleep(2.5)

def print_pipeline_status():
    global last_status_print
    now = time.time()
    if now - last_status_print < 15.0:
        return
    last_status_print = now

    gen_count = sum(1 for st in tab_states if st["state"] == S_GEN_WAITING)
    submit_count = sum(1 for st in tab_states if st["state"] not in [S_IDLE, S_GEN_WAITING])
    dl_waiting = sum(1 for d in active_downloads.values() if d.get("state") == "DOWNLOAD_WAITING")
    dl_raw = sum(1 for d in active_downloads.values() if d.get("state") == "CHROME_RAW_READY")
    wmr_status = wmr_pool.status()
    wmr_process = sum(1 for _, state, _ in wmr_status if state != "IDLE")

    print("\\n" + "=" * 68)
    print(f"PIPELINE STATUS {time.strftime('%H:%M:%S')}")
    print("=" * 68)
    
    print("\\nREDIS QUEUE")
    print(f"  WAIT={redis_queue_stats['wait']} | ACTIVE={redis_queue_stats['active']} | DELAYED={redis_queue_stats['delayed']} | PRIORITY={redis_queue_stats['prioritized']} | WAIT_CHILD={redis_queue_stats['waiting-children']}")
    
    print("\\nLOCAL PIPELINE")
    print(f"  SUBMIT={submit_count} | GEN={gen_count} | DL_WAIT={dl_waiting} | RAW_READY={dl_raw} | WMR_QUEUE={job_queue.qsize()}")
    print(f"  WMR_PROCESS={wmr_process} | DONE={counters['completed']} | FAIL={counters['failed']}")
    
    print("\\nGEMINI")
    for tid in range(MAX_CONCURRENT_TABS):
        st = tab_states[tid]
        jid = (st["job_id"] or "---")[:12]
        elapsed = f"{int(now - st['start_time'])}s" if st["start_time"] > 0 else "0s"
        print(f"  T{tid} = {st['state']:<13} {elapsed:>3}  {jid}")

    print("\\nWMR")
    for wid, state, cur_jid in wmr_status:
        jid_str = (cur_jid or "---")[:12]
        print(f"  W{wid} = {state:<13} Job={jid_str}")

    if active_downloads:
        print("\\nDOWNLOADS")
        for jid, dinfo in list(active_downloads.items()):
            state_str = dinfo.get('state','?')
            print(f"  {jid[:12]} = {state_str} {now - dinfo['started_at']:.1f}s")
            
    print("=" * 68 + "\\n")

'''

text = text[:start_idx] + new_code + text[end_idx:]

with open('v12_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Patched status loop')
