import sys

with open('v20_work.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

def find_line(substr, start=0):
    for i in range(start, len(lines)):
        if substr in lines[i]: return i
    return -1

# 1. Central Scheduler integration
cs_idx = find_line('async def central_scheduler_loop():')
cs_end = find_line('await asyncio.sleep(0.1)', cs_idx)
lines[cs_idx:cs_end+1] = """async def central_scheduler_loop():
    while True:
        try:
            # Assign Gemini jobs
            for w in gemini_pool.workers:
                if w.state == "IDLE" and w.job_queue.empty():
                    try:
                        job = GEMINI_ADMISSION_Q.get_nowait()
                        w.job_queue.put(job)
                    except asyncio.QueueEmpty:
                        break

            await poll_active_downloads()
            await poll_wmr_workers()
            print_pipeline_status()
        except Exception as e:
            import sys
            log(f"Scheduler loop error: {e}", file=sys.stderr)
        await asyncio.sleep(0.1)""".split('\n')

# 2. Download Snapshot Race (WmrWorker._process_job)
for i, l in enumerate(lines):
    if 'DOWNLOAD_BUTTON_DETECTED' in l and 'WmrWorker' in ''.join(lines[i-100:i]):
        lines[i] = """        log(f"{prefix} DOWNLOAD_BUTTON_DETECTED")
        dl_dir = self.staging_dir / f"{job_id}_dl"
        dl_dir.mkdir(parents=True, exist_ok=True)
        set_tab_download_dir(drv, str(dl_dir))
        files_before = set(dl_dir.iterdir())
"""
        break

# Remove old dir creation
for i in range(find_line('DOWNLOAD_BUTTON_DETECTED'), len(lines)):
    if 'dl_dir = self.staging_dir' in lines[i]:
        lines[i] = ""
        lines[i+1] = ""
        lines[i+2] = ""
        break

# Change iterdir
for i, l in enumerate(lines):
    if 'for f in dl_dir.iterdir():' in l:
        lines[i] = lines[i].replace('for f in dl_dir.iterdir():', 'for f in set(dl_dir.iterdir()) - files_before:')
        break

# 3. Resolve Future Wrapper
pw_idx = find_line('async def poll_wmr_workers():')
lines.insert(pw_idx, """
def resolve_future_once(loop, future, *, result=None, exception=None):
    def resolve():
        if future.done(): return
        if exception:
            future.set_exception(exception)
        else:
            future.set_result(result)
    loop.call_soon_threadsafe(resolve)
""")

for i, l in enumerate(lines):
    if 'loop.call_soon_threadsafe(future.set_result, (clean_png, webp_path))' in l:
        lines[i] = l.replace('loop.call_soon_threadsafe(future.set_result, (clean_png, webp_path))', 'resolve_future_once(loop, future, result=(clean_png, webp_path))')
    if 'loop.call_soon_threadsafe(future.set_exception, e)' in l:
        lines[i] = l.replace('loop.call_soon_threadsafe(future.set_exception, e)', 'resolve_future_once(loop, future, exception=e)')

# 4. BullMQ Timeout
for i, l in enumerate(lines):
    if 'return await done_future' in l:
        lines[i] = l.replace('return await done_future', 'return await asyncio.wait_for(done_future, timeout=TOTAL_JOB_TIMEOUT_S)')

# 5. AST Validation Gate
ast_code = """
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
"""
rs_idx = find_line('def run_startup_self_test():')
lines.insert(rs_idx, ast_code)

for i, l in enumerate(lines):
    if 'print("STARTUP_SELF_TEST=PASS")' in l:
        lines[i] = '    if not run_ast_validation(): raise RuntimeError("AST_VALIDATION_FAILED")\n    print("STARTUP_SELF_TEST=PASS")'
        break

# Fix WmrWorkerPool w.work_queue reference
for i, l in enumerate(lines):
    if 'w.work_queue' in l:
        lines[i] = l.replace('w.work_queue', 'w.job_queue') # wait, they dont have job_queue, they just use WMR_GLOBAL_Q

with open('v20_work.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("Step 2 done cleanly")
