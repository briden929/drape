with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("""
    add('''
class GeminiWorkerPool:
    def __init__(self, max_workers: int=GEMINI_WORKERS):
        self.max_workers = max_workers
        self.workers = {i: GeminiWorker(i) for i in range(max_workers)}

    def start_all(self):
        for i in range(self.max_workers):
            GEMINI_BROKER.release(i)
            
def _finalize_job(ctx: JobContext):
    # WebP
    webp_path = convert_to_webp(str(ctx.clean_path))
    if not webp_path:
        raise Exception("WebP conversion failed")
    ctx.webp_path = Path(webp_path)
    ctx.transition(JobState.WEBP_READY)
    
    # R2
    png_url, webp_url = upload_to_r2(str(ctx.clean_path), str(ctx.webp_path), ctx.job_id)
    if not png_url:
        raise Exception("R2 Upload failed")
    ctx.r2_png_url = png_url
    ctx.r2_webp_url = webp_url
    ctx.transition(JobState.R2_READY)
    
    # DB
    db_success = False
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET output_url = %s, webp_url = %s, status = 'completed', updated_at = NOW() WHERE id = %s",
                           (ctx.r2_png_url, ctx.r2_webp_url, ctx.generation_id))
        db_success = True
    except Exception as e:
        log(f"DB Error: {e}")
        # Retry DB once
        time.sleep(1)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE generations SET output_url = %s, webp_url = %s, status = 'completed', updated_at = NOW() WHERE id = %s",
                           (ctx.r2_png_url, ctx.r2_webp_url, ctx.generation_id))
        db_success = True
        
    ctx.transition(JobState.DB_READY)
    
    # Credits
    try:
        credits.settle(ctx.user_id, ctx.generation_id)
    except Exception as e:
        log(f"Credits settle warning: {e}")
        
    final_dir = get_final_output_dir(0, ctx.job_id)
    import shutil
    shutil.copy(str(ctx.clean_path), str(final_dir / f"{ctx.job_id}_final.png"))

async def process_job_pipeline(ctx: JobContext):
    ctx.transition(JobState.QUEUED)
    while True:
        tid = GEMINI_BROKER.acquire()
        if tid is not None:
            ctx.assigned_tid = tid
            break
        await asyncio.sleep(0.5)
        
    ctx.transition(JobState.GEMINI_ASSIGNED)
    gemini_pool.workers[ctx.assigned_tid].process_job(ctx)
    
    while ctx.state not in (JobState.RAW_READY, JobState.FAILED):
        await asyncio.sleep(0.5)
        
    if ctx.state == JobState.FAILED:
        return
        
    ctx.transition(JobState.WMR_QUEUED)
    while True:
        wid = WMR_BROKER.acquire()
        if wid is not None:
            ctx.assigned_wmr_tab = wid
            break
        await asyncio.sleep(0.5)
        
    ctx.transition(JobState.WMR_ASSIGNED)
    
    # Fire and forget into the thread
    await wmr_pool.execute_async(ctx.assigned_wmr_tab, _run_wmr_logic, ctx)
    
    while ctx.state not in (JobState.CLEAN_READY, JobState.FAILED):
        await asyncio.sleep(0.5)
        
    if ctx.state == JobState.FAILED:
        return
        
    try:
        await asyncio.to_thread(_finalize_job, ctx)
        ctx.transition(JobState.COMPLETED)
        resolve_future_once(main_loop, ctx.future, ctx)
    except Exception as e:
        ctx.error_message = str(e)
        ctx.transition(JobState.FAILED)
        resolve_future_once(main_loop, ctx.future, None, is_exception=True)

async def process_bullmq_job(job):
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    
    ctx = JobContext(job.data, fut)
    job_contexts[ctx.job_id] = ctx
    
    # Start pipeline asynchronously
    asyncio.create_task(process_job_pipeline(ctx))
    
    # Wait for the future
    try:
        res = await asyncio.wait_for(fut, timeout=TOTAL_JOB_TIMEOUT_S)
        return {"status": "success", "job_id": ctx.job_id}
    except asyncio.TimeoutError:
        ctx.error_message = "Global Job Timeout"
        ctx.transition(JobState.FAILED)
        raise Exception("Job timeout")
    except Exception as e:
        raise
''')
""")
