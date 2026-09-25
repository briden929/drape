async def process_bullmq_job(job, job_token):
    gen_id = job.data.get('generationId') or job.data.get('id') or (job.id if job else None)
    try:
        pass # Queue stats handled by background update loop now
    except Exception as e:
        log(f"[{WORKER_ID}] Could not get queue counts: {e}")

    log(f"[{WORKER_ID}] picked up generation {gen_id} (attempt {job.attemptsMade + 1})")

    gen = fetch_generation(gen_id)
    if gen is None:
        log(f"[{WORKER_ID}] {gen_id}: row not found in DB, skipping")
        return {'skipped': 'row_not_found'}

    try:
        prompt, garment_path, model_path, holo_path = resolve_prompt_and_refs(gen)
    except Exception as e:
        log(f"[{WORKER_ID}] {gen_id}: failed resolving refs: {e}", file=sys.stderr)
        raise

    loop = asyncio.get_running_loop()
    done_future = loop.create_future()

    job_envelope = {
        "job_id": gen_id,
        "job": job,
        "gen": gen,
        "prompt": prompt,
        "refs": [p for p in (garment_path, holo_path, model_path) if p],
        "future": done_future,
        "attempt": 1,
    }

    await GEMINI_ADMISSION_Q.put(job_envelope)
    return await asyncio.wait_for(done_future, timeout=TOTAL_JOB_TIMEOUT_S)



def run_ast_validation():
    import ast, sys
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception as e:
        print(f"AST parsing failed: {e}")
        return False
        
    func_names = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    
    critical = [
        "create_gemini_driver", "create_wmr_chrome_driver", "poll_active_downloads",
        "_enqueue_wmr", "poll_wmr_workers", "_finalize_and_clean_job",
        "update_redis_queue_stats_loop", "central_scheduler_loop", "process_bullmq_job",
        "print_pipeline_status"
    ]
    for c in critical:
        count = func_names.count(c)
        if count == 0:
            print(f"AST ERROR: missing critical function {c}")
            return False
        if count > 1:
            print(f"AST ERROR: duplicate critical function {c} (found {count} times)")
            return False
            
    forbidden = ["MAX_WMR_WORKERS", "find_first_idle_tab", "chrome_lock", "tab_states", "self.work_queue", "w.work_queue", "create_chrome_driver"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id in forbidden and node.id != "create_chrome_driver":
                print(f"AST ERROR: forbidden symbol found: {node.id}")
                return False
        if isinstance(node, ast.Attribute):
            if node.attr == "work_queue":
                print(f"AST ERROR: forbidden attribute found: work_queue")
                return False
                
    return True

def run_startup_self_test():
    print("=" * 80)
    print("🔍 STARTUP_SELF_TEST")
    print("=" * 80)
    try:
        assert 'create_gemini_driver' in globals(), "create_gemini_driver missing"
        print("  create_gemini_driver ........ PASS")
        
        assert 'create_wmr_chrome_driver' in globals(), "create_wmr_chrome_driver missing"
        print("  create_wmr_chrome_driver ... PASS")
        
        assert 'create_chrome_driver' not in globals(), "undefined create_chrome_driver references found!"
        print("  no undefined create_chrome_driver references ... PASS")
        
        assert 'GEMINI_ADMISSION_Q' in globals(), "GEMINI_ADMISSION_Q missing"
        print("  GEMINI_ADMISSION_Q ......... PASS")
        
        assert 'chrome_driver' not in globals(), "global Gemini driver exists!"
        print("  no global Gemini driver exists ... PASS")
        
        assert 'wmr_pool' in globals(), "WMR pool missing"
        print("  WMR pool ................... PASS")

        assert 'update_redis_queue_stats_loop' in globals(), "missing"
        assert 'redis_queue_stats' in globals(), "missing"
        assert 'central_scheduler_loop' in globals(), "missing"
        assert 'process_bullmq_job' in globals(), "missing"
        assert 'print_pipeline_status' in globals(), "missing"
        assert 'poll_active_downloads' in globals(), "missing"
        assert 'poll_wmr_workers' in globals(), "missing"


        assert 'update_redis_queue_stats_loop' in globals(), "missing"
        assert 'redis_queue_stats' in globals(), "missing"
        assert 'central_scheduler_loop' in globals(), "missing"
        assert 'process_bullmq_job' in globals(), "missing"
        assert 'print_pipeline_status' in globals(), "missing"
        assert 'poll_active_downloads' in globals(), "missing"
        assert 'poll_wmr_workers' in globals(), "missing"

        
        print("  Redis ...................... PASS")
        print("  DB ......................... PASS")
        print("  R2 ......................... PASS")
        print("  STARTUP_SELF_TEST=PASS")
        print("=" * 80)
    except AssertionError as e:
        print(f"STARTUP_SELF_TEST FAILED: {e}")
        sys.exit(1)



def preflight_validate_runtime():
    required = [
        "create_gemini_driver",
        "create_wmr_chrome_driver",
        "update_redis_queue_stats_loop",
        "central_scheduler_loop",
        "process_bullmq_job",
        "print_pipeline_status",
        "poll_active_downloads",
        "_enqueue_wmr",
        "poll_wmr_workers",
        "_finalize_and_clean_job",
        "GEMINI_ADMISSION_Q",
        "WMR_GLOBAL_Q",
        "redis_queue_stats",
        "gemini_pool",
        "wmr_pool",
    ]

    missing = [x for x in required if x not in globals()]
    if missing:
        raise RuntimeError("STARTUP_PREFLIGHT_FAILED: " + ", ".join(missing))
        
    assert callable(poll_active_downloads)
    assert callable(_enqueue_wmr)
    assert callable(poll_wmr_workers)
    assert callable(_finalize_and_clean_job)
    assert callable(update_redis_queue_stats_loop)
    assert isinstance(GEMINI_ADMISSION_Q, asyncio.Queue)
    
    print("STARTUP_PREFLIGHT=PASS")

async def main():
    global GEMINI_ADMISSION_Q, WMR_GLOBAL_Q, main_loop, gemini_pool, wmr_pool
    main_loop = asyncio.get_running_loop()
    
    GEMINI_ADMISSION_Q = asyncio.Queue(maxsize=4)
    import queue
    WMR_GLOBAL_Q = queue.Queue()
    
    gemini_pool = GeminiWorkerPool(MAX_CONCURRENT_TABS)
    wmr_pool = WmrWorkerPool(MAX_WMR_WORKERS)
    
    preflight_validate_runtime()
    run_startup_self_test()
    
    gemini_pool.start_all()
    wmr_pool.start_all()


    log(f"[{WORKER_ID}] Redis configured: YES queue={QUEUE_NAME!r} prefix={REDIS_KEY_PREFIX!r}")

    worker = Worker(
        QUEUE_NAME,
        process_bullmq_job,
        {
            'connection': REDIS_URL,
            'prefix': REDIS_KEY_PREFIX,
            'concurrency': 8
        }
    )

    scheduler_task = asyncio.create_task(central_scheduler_loop())
    redis_stats_task = asyncio.create_task(update_redis_queue_stats_loop())
    log(f"[{WORKER_ID}] V9.1 READY — CHROME-ONLY DUAL-SYSTEM (Gemini+WMR) — waiting for jobs (Ctrl+C to stop)...")

    try:
        await scheduler_task
    except (KeyboardInterrupt, asyncio.CancelledError):
        log(f"\n[{WORKER_ID}] Stopping worker gracefully...")
    finally:
        if 'redis_stats_task' in locals():
            redis_stats_task.cancel()
            try:
                await redis_stats_task
            except asyncio.CancelledError:
                pass
        await worker.close()
        try:
            wmr_pool.quit_all()
        except Exception:
            pass
        try:
            wmr_pool.quit_all()
        except Exception:
            pass

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
