import re, sys

with open('v20_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Clean up any accidental duplicates
text = re.sub(r'async def update_redis_queue_stats_loop\(\):.*?(?=async def central_scheduler_loop\(\):)', '', text, flags=re.DOTALL)
text = re.sub(r'def print_pipeline_status\(\):.*?(?=async def central_scheduler_loop\(\):)', '', text, flags=re.DOTALL)
text = re.sub(r'redis_queue_stats = \{.*?\}\n', '', text, flags=re.DOTALL)

clean_functions = """
redis_queue_stats = {
    "wait": 0, "active": 0, "delayed": 0, "prioritized": 0, "waiting-children": 0,
}

async def update_redis_queue_stats_loop():
    from bullmq import Queue
    q = Queue(QUEUE_NAME, {"connection": REDIS_URL, "prefix": REDIS_KEY_PREFIX})
    try:
        while True:
            try:
                counts = await q.getJobCounts()
                redis_queue_stats.update({k: counts.get(k, 0) for k in redis_queue_stats.keys()})
            except asyncio.CancelledError:
                raise
            except Exception as e:
                import sys
                log(f"Redis stats update failed: {e}", file=sys.stderr)
            await asyncio.sleep(2.5)
    finally:
        try:
            await q.close()
        except Exception:
            pass

def _enqueue_wmr(job_id: str, dinfo: dict):
    loop = main_loop
    future = loop.create_future()
    dinfo["wmr_future"] = future
    active_wmr[job_id] = dinfo
    wmr_pool.submit_job(
        job_id,
        dinfo["tid"],
        str(dinfo["raw_path"]),
        future,
        loop
    )
    log(f"[{job_id}] WMR_QUEUE -> WMR_GLOBAL_Q")

async def poll_active_downloads():
    now = time.time()
    for job_id, dinfo in list(active_downloads.items()):
        if dinfo.get("state") != "DOWNLOAD_WAITING":
            continue
            
        incoming_dir = Path(dinfo.get("incoming_dir", ""))
        if not incoming_dir.exists():
            continue
            
        raw_ready = False
        valid_file = None
        
        for f in incoming_dir.iterdir():
            if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                size = f.stat().st_size
                if size > 1024:
                    time.sleep(0.5)
                    if size == f.stat().st_size:
                        try:
                            from PIL import Image
                            with Image.open(f) as img:
                                img.verify()
                            valid_file = f
                            raw_ready = True
                            break
                        except Exception:
                            pass
                            
        if raw_ready and valid_file:
            raw_path = Path(dinfo["chrome_job_dir"]) / f"{job_id}_raw.png"
            import shutil
            shutil.move(str(valid_file), str(raw_path))
            dinfo["raw_path"] = raw_path
            dinfo["state"] = "CHROME_RAW_READY"
            _enqueue_wmr(job_id, dinfo)
            continue
            
        if now - dinfo.get("started_at", now) > 60:
            log(f"[{job_id}] DOWNLOAD_TIMEOUT")
            _fail_job(job_id, dinfo.get("gen"), "Download timed out", dinfo.get("future"), 1)
            active_downloads.pop(job_id, None)

async def _finalize_and_clean_job(job_id, dinfo, clean_png, webp_path):
    gen = dinfo.get("gen", {})
    future = dinfo.get("future")
    try:
        log(f"[{job_id}] R2 Uploading...")
        import os
        from backend.r2 import upload_to_r2, ensure_webp
        
        if not webp_path or not os.path.exists(webp_path):
            webp_path = ensure_webp(str(clean_png))
            
        clean_url = upload_to_r2(str(clean_png), f"{job_id}_clean.png")
        webp_url = upload_to_r2(str(webp_path), f"{job_id}_clean.webp")
        
        log(f"[{job_id}] DB Updating...")
        import db
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET output_url=%s, webp_url=%s, status='COMPLETED' WHERE id=%s", (clean_url, webp_url, job_id))
            conn.commit()
        
        log(f"[{job_id}] Settling credits...")
        try:
            from backend.credits import credit_settle
            credit_settle(gen.get("user_id"), 1)
        except Exception as ce:
            log(f"[{job_id}] Credit settle failed: {ce}", file=sys.stderr)
        
        if future and not future.done():
            future.set_result(True)
            
        counters["completed"] += 1
        log(f"[{job_id}] COMPLETION SUCCESSFUL")
        
    except Exception as e:
        log(f"[{job_id}] FINALIZE FAILED: {e}")
        _fail_job(job_id, gen, str(e), future, 1)
    finally:
        active_downloads.pop(job_id, None)

def resolve_future_once(loop, future, *, result=None, exception=None):
    def resolve():
        if future.done(): return
        if exception:
            future.set_exception(exception)
        else:
            future.set_result(result)
    loop.call_soon_threadsafe(resolve)

async def poll_wmr_workers():
    for job_id, dinfo in list(active_wmr.items()):
        future = dinfo.get("wmr_future")
        if future is None or not future.done():
            continue
            
        active_wmr.pop(job_id, None)
        
        if future.exception():
            log(f"[{job_id}] WMR_FAILED: {future.exception()}")
            _fail_job(job_id, dinfo.get("gen"), str(future.exception()), dinfo.get("future"), 1)
        else:
            clean_png, webp_path = future.result()
            log(f"[{job_id}] WMR_OUTPUT_READY")
            import asyncio
            asyncio.create_task(_finalize_and_clean_job(job_id, dinfo, clean_png, webp_path))

last_status_print = 0
def print_pipeline_status():
    import time
    global last_status_print
    now = time.time()
    if now - last_status_print < 2.5: return
    last_status_print = now

    dl_waiting = sum(1 for d in active_downloads.values() if d.get("state") == "DOWNLOAD_WAITING")
    dl_raw = sum(1 for d in active_downloads.values() if d.get("state") == "CHROME_RAW_READY")
    wmr_status = wmr_pool.status()

    print("\\n====================================================================")
    print(f"PIPELINE STATUS {time.strftime('%H:%M:%S')}")
    print("====================================================================")
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
    print(f"  START_WAIT={dl_waiting}  RAW_READY={dl_raw}")
    print("\\nWMR CHROME WORKERS")
    print(f"  QUEUE={WMR_GLOBAL_Q.qsize()}")
    for wid, state, cur_jid in wmr_status:
        print(f"  W{wid} = {state:<13}  Job={(cur_jid or '---')[:12]}")
    print("\\nRESULT")
    print(f"  DONE={counters['completed']} | FAIL={counters['failed']}")
    print("====================================================================\\n")

"""
text = text.replace('async def central_scheduler_loop():', clean_functions + '\nasync def central_scheduler_loop():')

with open('v20_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Injected perfectly clean V10 functions!")
