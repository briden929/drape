import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''async def poll_active_tabs():
    """Poll all generating Chrome tabs for image detection. Strictly independent per-tab."""
    now = time.time()
    for tid in range(MAX_CONCURRENT_TABS):
        info = tab_states[tid]
        if info["state"] != S_GEN_WAITING:
            continue'''

replacement = '''async def poll_active_tabs():
    """Poll all generating Chrome tabs for image detection. Strictly independent per-tab."""
    now = time.time()
    for tid in range(MAX_CONCURRENT_TABS):
        info = tab_states[tid]
        
        if info["state"] == "DOWNLOAD_START_WAITING":
            dinfo = info["dinfo"]
            incoming_dir = dinfo["incoming_dir"]
            files_before = dinfo["files_before"]
            cdp_ok = info.get("cdp_ok", False)
            job_id = info["job_id"]
            prefix = f"[T{tid}][{job_id}]"

            dl_confirmed = False
            if incoming_dir.exists():
                cur_files = set(os.listdir(incoming_dir))
                new_files = cur_files - files_before
                if any(
                    fn.endswith('.crdownload') or
                    fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                    for fn in new_files
                ):
                    dl_confirmed = True

            if dl_confirmed or cdp_ok:
                if dl_confirmed:
                    log(f"{prefix} DOWNLOAD_START_CONFIRMED")
                
                # NOW close the physical Gemini tab
                async with chrome_lock:
                    try:
                        chrome_driver.switch_to.window(info["handle"])
                        chrome_driver.close()
                    except Exception:
                        pass
                log(f"{prefix} PHYSICAL_TAB_CLOSED")
                info["handle"] = None
                
                # Advance download state
                dinfo["state"] = "DOWNLOAD_WAITING"
                
                _free_tab(tid, job_id)
                log(f"{prefix} [T{tid}] IDLE")
                
                if cdp_ok:
                    _enqueue_wmr(job_id, dinfo)
                    
                if not job_queue.empty():
                    asyncio.create_task(assign_jobs_to_idle_tabs())
                continue
                
            if now - info["t_dl_start"] > DOWNLOAD_START_WINDOW_S:
                log(f"{prefix} DOWNLOAD_START_FAILED — Waited {DOWNLOAD_START_WINDOW_S}s for .crdownload")
                _recover_stuck_tab(tid, "DOWNLOAD_START_TIMEOUT")
            continue

        if info["state"] != S_GEN_WAITING:
            continue'''

if target in text:
    text = text.replace(target, replacement)
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched poll_active_tabs start')
else:
    print('Target not found')
