import re, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('v16_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Redis Stats Loop
redis_stats_code = '''
redis_queue_stats = {
    "wait": 0,
    "active": 0,
    "delayed": 0,
    "prioritized": 0,
    "waiting-children": 0,
}

async def update_redis_queue_stats_loop():
    from bullmq import Queue
    q = Queue(
        QUEUE_NAME,
        {
            "connection": REDIS_URL,
            "prefix": REDIS_KEY_PREFIX,
        }
    )

    try:
        while True:
            try:
                counts = await q.getJobCounts()

                redis_queue_stats["wait"] = counts.get("waiting", 0)
                redis_queue_stats["active"] = counts.get("active", 0)
                redis_queue_stats["delayed"] = counts.get("delayed", 0)
                redis_queue_stats["prioritized"] = counts.get("prioritized", 0)
                redis_queue_stats["waiting-children"] = counts.get("waiting-children", 0)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                log(f"Redis stats update failed: {e}", file=sys.stderr)

            await asyncio.sleep(2.5)

    finally:
        try:
            await q.close()
        except Exception:
            pass
'''
text = re.sub(r'(# ============================================================================\n# COMPACT PIPELINE STATUS)', redis_stats_code + r'\n\1', text)

# 2. GEMINI_ADMISSION_Q definition at top
text = text.replace('GEMINI_ADMISSION_Q = queue.Queue(maxsize=4)', 'GEMINI_ADMISSION_Q = None # Will be initialized in main()')

# 3. GeminiWorker._run_loop update
new_gemini_run_loop = '''    def _run_loop(self):
        while True:
            try:
                future = asyncio.run_coroutine_threadsafe(GEMINI_ADMISSION_Q.get(), main_loop)
                item = future.result()
            except Exception as e:
                log(f"[T{self.tid}] GEMINI ADMISSION GET FAILED: {e}")
                import time
                time.sleep(1)
                continue
                
            if item is None: break
            self.current_job_id = item["job_id"]
            self.state = "SUBMITTING"
            self.start_time = time.time()
            
            try:
                self._process_job(item)
            except Exception as e:
                log(f"[T{self.tid}][{self.current_job_id}] GEMINI_FAILED: {e}")
                _fail_job(self.current_job_id, item.get("gen"), f"Gemini failed: {e}", item.get("future"), 1)
            finally:
                self.state = "IDLE"
                self.current_job_id = None
                self.start_time = 0
                try:
                    main_loop.call_soon_threadsafe(GEMINI_ADMISSION_Q.task_done)
                except Exception:
                    pass
'''
# We only want to replace _run_loop in GeminiWorker
start_idx = text.find('class GeminiWorker:')
end_idx = text.find('    def _process_job(self, item):', start_idx)
orig_run_loop = text[start_idx:end_idx]
orig_run_loop_actual = orig_run_loop[orig_run_loop.find('    def _run_loop(self):'):]
text = text[:start_idx + orig_run_loop.find('    def _run_loop(self):')] + new_gemini_run_loop + text[end_idx:]

# 4. process_bullmq_job
text = text.replace('await asyncio.to_thread(GEMINI_ADMISSION_Q.put, job_envelope)', 'await GEMINI_ADMISSION_Q.put(job_envelope)')

# 5. Main loop init & Preflight
main_init = '''
def preflight_validate_runtime():
    required = [
        "create_gemini_driver",
        "create_wmr_chrome_driver",
        "update_redis_queue_stats_loop",
        "central_scheduler_loop",
        "process_bullmq_job",
        "print_pipeline_status",
        "poll_active_downloads",
        "poll_wmr_workers",
        "GEMINI_ADMISSION_Q",
        "WMR_GLOBAL_Q",
        "redis_queue_stats",
        "gemini_pool",
        "wmr_pool",
    ]

    missing = [x for x in required if x not in globals()]
    if missing:
        raise RuntimeError("STARTUP_PREFLIGHT_FAILED: " + ", ".join(missing))
    print("STARTUP_PREFLIGHT=PASS")

async def main():
    global GEMINI_ADMISSION_Q, main_loop
    main_loop = asyncio.get_running_loop()
    GEMINI_ADMISSION_Q = asyncio.Queue(maxsize=4)
    
    preflight_validate_runtime()
    run_startup_self_test()
'''
text = re.sub(r'async def main\(\):.*?(?=    log\(f"\[\{WORKER_ID\}\])', main_init + '\n', text, flags=re.DOTALL)

# 6. Self-test update
new_checks = '''
        assert 'update_redis_queue_stats_loop' in globals(), "missing"
        assert 'redis_queue_stats' in globals(), "missing"
        assert 'central_scheduler_loop' in globals(), "missing"
        assert 'process_bullmq_job' in globals(), "missing"
        assert 'print_pipeline_status' in globals(), "missing"
        assert 'poll_active_downloads' in globals(), "missing"
        assert 'poll_wmr_workers' in globals(), "missing"
'''
text = re.sub(r'(print\("  WMR pool \.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.\. PASS"\))', r'\1\n' + new_checks, text)

# 7. WMR Strict Click Download
# The user said: Current _wmr_check_status() accepts: Download PNG, Save. REMOVE generic Save. Only: exact "Download PNG" inside the verified WMR result area.
# Wait, let's find `_wmr_check_status` and `_wmr_click_download`
wmr_check = '''def _wmr_check_status(drv: webdriver.Chrome):
    try:
        # Strict targeting: must be inside the results container
        js = """
        var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
        if (!res) return null;
        var btns = res.querySelectorAll('button, a');
        for (var i=0; i<btns.length; i++) {
            var t = (btns[i].textContent || '').toLowerCase().trim();
            if (t === 'download png') {
                return 'READY';
            }
        }
        return 'PROCESSING';
        """
        return safe_execute_script(drv, js)
    except:
        return None
'''
text = re.sub(r'def _wmr_check_status\(.*?return None\n', wmr_check, text, flags=re.DOTALL)

wmr_click = '''def _wmr_click_download(drv: webdriver.Chrome, job_id: str, prefix: str) -> bool:
    try:
        js = """
        var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
        if (!res) return false;
        var btns = res.querySelectorAll('button, a');
        for (var i=0; i<btns.length; i++) {
            var t = (btns[i].textContent || '').toLowerCase().trim();
            if (t === 'download png') {
                btns[i].click();
                return true;
            }
        }
        return false;
        """
        return safe_execute_script(drv, js)
    except:
        return False
'''
text = re.sub(r'def _wmr_click_download\(.*?return False\n', wmr_click, text, flags=re.DOTALL)

with open('v16_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Applied all fixes")
