
# ================================================================================================================
# BACKEND / BULLMQ
# ================================================================================================================

async def process_job(job: Job):
    job_id = job.id
    ctx = JobContext(job_id=job_id, payload=job.data)
    JOB_CONTEXTS[job_id] = ctx
    loop = asyncio.get_running_loop()
    
    try:
        # 1. Gemini
        tid = await GEMINI_BROKER.acquire()
        ctx.gemini_resource = tid
        await ctx.transition(JobState.GEMINI_RESERVED)
        
        ctx.completion_future = loop.create_future()
        GEMINI_POOL.workers[tid].execute_job(loop, ctx)
        await ctx.completion_future
        
        # 2. WMR
        ctx.completion_future = loop.create_future()
        await ctx.transition(JobState.WMR_QUEUED)
        w_tid = await WMR_BROKER.acquire()
        ctx.wmr_resource = w_tid
        await ctx.transition(JobState.WMR_RESERVED)
        
        pid = w_tid.split("-")[0]
        WMR_POOL.threads[pid].command_queue.put(("EXECUTE", (loop, ctx, w_tid)))
        await ctx.completion_future
        
        # 3. WEBP
        ctx.webp_path = f"/content/downloads/final/{job_id}.webp"
        os.makedirs(os.path.dirname(ctx.webp_path), exist_ok=True)
        with open(ctx.webp_path, "w") as f: f.write("webp")
        await ctx.transition(JobState.WEBP_READY)
        
        # 4. R2 & DB
        await ctx.transition(JobState.COMPLETED)
        return {"status": "completed"}
        
    except Exception as e:
        await ctx.transition(JobState.FAILED)
        ctx.error = str(e)
        raise
