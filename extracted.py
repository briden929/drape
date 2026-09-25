async def poll_active_downloads():
    """
    Scan ONLY each job's private incoming_dir for the downloaded file.
    Never scans broad directories. Renames stable file to {job_id}_raw.png
    and enqueues to WmrWorkerPool.
    """
    now = time.time()
    for job_id, dinfo in list(active_downloads.items()):
        if dinfo["state"] != "DOWNLOAD_WAITING":
            continue

        incoming_dir: Path = dinfo["incoming_dir"]
        chrome_job_dir: Path = dinfo["chrome_job_dir"]
        raw_path: Path = dinfo["raw_path"]
        files_before: set = dinfo.get("files_before", set())

        # If raw_path already written (e.g. by CDP fallback), skip filesystem scan
        if raw_path.exists() and raw_path.stat().st_size >= DOWNLOAD_MIN_SIZE:
            dinfo["state"] = "CHROME_RAW_READY"
            log(f"[{job_id}] DOWNLOAD_FILE_DETECTED (direct) -> {raw_path.name}")
            _enqueue_wmr(job_id, dinfo)
            continue

        # Scan incoming dir only
        found_file = None
        if incoming_dir.exists():
            for fn in os.listdir(incoming_dir):
                if fn.endswith(('.crdownload', '.tmp', '.part', '.download')):
                    continue
                if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    continue
                if fn in files_before:
                    continue
                fp = incoming_dir / fn
                try:
                    if fp.stat().st_size >= DOWNLOAD_MIN_SIZE:
                        found_file = fp
                        break
                except Exception:
                    pass

        if found_file:
            cur_sz = found_file.stat().st_size
            if cur_sz == dinfo.get("last_size", -1):
                dinfo["stable_checks"] = dinfo.get("stable_checks", 0) + 1
                if dinfo["stable_checks"] >= DOWNLOAD_STABLE_CHECKS:
                    # Validate image
                    if validate_image_file(found_file):
                        # Rename to canonical raw name
                        raw_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.move(str(found_file), str(raw_path))
                        except Exception:
                            shutil.copy2(str(found_file), str(raw_path))
                            try: os.remove(str(found_file))
                            except Exception: pass
                        log(f"[{job_id}] DOWNLOAD_FILE_DETECTED")
                        log(f"[{job_id}] DOWNLOAD_STABLE")
                        log(f"[{job_id}] IMAGE_VALIDATED")
                        log(f"[{job_id}] RENAMED_TO_JOB_RAW")
                        dinfo["state"] = "CHROME_RAW_READY"
                        _enqueue_wmr(job_id, dinfo)
                    else:
                        log(f"[{job_id}] DOWNLOAD_FILE_INVALID (PIL check failed), waiting...")
                        dinfo["stable_checks"] = 0
            else:
                dinfo["last_size"] = cur_sz
                dinfo["stable_checks"] = 0

        elif now - dinfo["started_at"] > DOWNLOAD_TIMEOUT_S:
            log(f"[{job_id}] DOWNLOAD_TIMEOUT after {DOWNLOAD_TIMEOUT_S}s", file=sys.stderr)
            dinfo["state"] = "FAILED"
            _fail_job(job_id, dinfo["gen"], f"Download timed out after {DOWNLOAD_TIMEOUT_S}s",
                      dinfo.get("future"), dinfo.get("attempt", 1))
            active_downloads.pop(job_id, None)



def _enqueue_wmr(job_id: str, dinfo: dict):
    """Hand off the raw PNG to the WmrWorkerPool for watermark removal."""
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    dinfo["wmr_future"] = future
    active_wmr[job_id] = dinfo
    log(f"[{job_id}] WMR_QUEUE -> Chrome WmrWorkerPool")
    wmr_pool.submit(
        job_id,
        dinfo["chrome_tab_id"],
        str(dinfo["raw_path"]),
        future,
        loop
    )



async def poll_wmr_workers():
    """Check if any WMR Chrome jobs have completed and trigger finalization."""
    for job_id, dinfo in list(active_wmr.items()):
        future = dinfo.get("wmr_future")
        if future is None or not future.done():
            continue
        active_wmr.pop(job_id, None)
        if future.exception():
            ex = future.exception()
            log(f"[{job_id}] WMR_FAILED: {ex}", file=sys.stderr)
            _fail_job(job_id, dinfo["gen"], f"WMR failed: {ex}",
                      dinfo.get("future"), dinfo.get("attempt", 1))
            active_downloads.pop(job_id, None)
        else:
            clean_png, webp_path = future.result()
            log(f"[{job_id}] WMR_OUTPUT_READY -> {Path(clean_png).name}")
            asyncio.create_task(_finalize_and_clean_job(job_id, dinfo, clean_png, webp_path))



async def _finalize_and_clean_job(job_id: str, dinfo: dict, clean_png: str, webp_path: str):
    """
    Final pipeline:
    WMR clean PNG -> validate -> copy to final_output -> WebP -> R2 -> DB -> Credits -> COMPLETE.
    Credits settled ONLY after R2 upload succeeds.
    """
    gen = dinfo["gen"]
    prompt = dinfo["prompt"]
    chrome_tab_id = dinfo["chrome_tab_id"]
    result_future = dinfo.get("future")

    try:
        # 1. Validate Edge output
        if not validate_image_file(clean_png):
            raise RuntimeError(f"WMR clean PNG invalid: {clean_png}")

        # 2. Copy to final_output
        final_dir = get_final_output_dir(chrome_tab_id, job_id)
        final_ext = Path(clean_png).suffix or '.png'
        final_png = final_dir / f'{job_id}_final{final_ext}'
        shutil.copy2(clean_png, str(final_png))
        log(f"[{job_id}] FINAL_OUTPUT_READY -> {final_png.name}")

        # 3. WebP validation
        final_webp = None
        if webp_path and os.path.exists(webp_path):
            final_webp_path = final_dir / f'{job_id}_final.webp'
            shutil.copy2(webp_path, str(final_webp_path))
            final_webp = str(final_webp_path)
            log(f"[{job_id}] WEBP_READY -> {final_webp_path.name}")

        # 4. R2 upload
        log(f"[{job_id}] R2_UPLOAD -> bucket={R2_BUCKET_NAME}")
        result = sys.modules['fashion_studio'].push_generation(
            image_path=str(final_png),
            prompt=prompt,
            user_id=gen['user_id'],
            gen_id=job_id,
            webp_path=final_webp,
            force=True,
            params=gen.get('params') or {}
        )
        log(f"[{job_id}] R2_UPLOAD_DONE -> {result.get('output_url')}")

        # 5. Credits settle (ONLY after R2 success)
        sys.modules['credits'].settle_look(job_id)
        log(f"[{job_id}] COMPLETE ✅  output_url={result.get('output_url')}")

        counters["completed"] += 1
        if result_future and not result_future.done():
            result_future.set_result(result)

    except Exception as e:
        log(f"[{job_id}] FINALIZATION_FAILED: {e}", file=sys.stderr)
        _fail_job(job_id, gen, str(e)[:500], result_future, dinfo.get("attempt", 1))
    finally:
        active_downloads.pop(job_id, None)

async def assign_jobs_to_idle_tabs():
    """Assign queued jobs to idle Chrome tabs (strict lowest-ID priority)."""
    while not job_queue.empty():
        tid = find_first_idle_tab()
        if tid is None:
            break
        job_envelope = await job_queue.get()
        info = tab_states[tid]
        info["state"] = S_SUBMITTING
        info["job"] = job_envelope["job"]
        info["job_id"] = job_envelope["job_id"]
        info["gen"] = job_envelope["gen"]
        info["prompt"] = job_envelope["prompt"]
        info["refs"] = job_envelope["refs"]
        info["future"] = job_envelope["future"]
        info["attempt"] = job_envelope.get("attempt", 1)
        info["download_started"] = False
        info["stuck_polls"] = 0
        info["start_time"] = time.time()
        log(f"[T{tid}][{info['job_id']}] ASSIGNED (attempt {info['attempt']}) -> submitting...")
        asyncio.create_task(_submit_job_to_tab(tid))

async def _submit_job_to_tab(tid: int):
    """
    Full strict submission pipeline:
    new chat -> flash -> create image -> drawer -> file input -> upload -> verify count
    -> inject prompt -> send -> verify generation started
    Any failure recovers the tab immediately. No silent continues.
    """
    info = tab_states[tid]
    job_id = info["job_id"]
    prefix = f"[T{tid}][{job_id}]"

    # LAZY TAB CREATION: create physical Chrome tab only when job is assigned
    if info["handle"] is None:
        try:
            info["handle"] = _create_gemini_tab(tid)
            log(f"{prefix} [T{tid}] IDLE (first use — physical tab created)")
        except Exception as e:
            log(f"{prefix} LAZY_TAB_CREATE_FAILED: {e}", file=sys.stderr)
            _recover_stuck_tab(tid, f"LAZY_TAB_CREATE_FAILED: {e}")
            return

    try:
        async with chrome_lock:
            chrome_driver.switch_to.window(info["handle"])
            
            # Setup isolated download directory for this job early
            chrome_job_dir, incoming_dir = get_chrome_job_dir(tid, job_id)
            set_tab_download_dir(chrome_driver, str(incoming_dir))

            # 1. Open verified new Gemini chat
            info["state"] = S_NEW_CHAT
            log(f"{prefix} NEW_CHAT_START")
            try:
                new_chat_url = open_new_chat_and_reload(chrome_driver, tid, job_id)
                log(f"{prefix} NEW_CHAT_VERIFIED -> {new_chat_url}")
            except NewChatFailed as e:
                _recover_stuck_tab(tid, str(e))
                return

            # 2. Flash mode
            info["state"] = S_SUBMITTING
            try:
                ensure_flash_mode(chrome_driver, tid, job_id)
            except ModelLimitReached:
                _recover_stuck_tab(tid, "FLASH_FAILED: ModelLimitReached")
                return
            except Exception as e:
                _recover_stuck_tab(tid, f"FLASH_FAILED: {e}")
                return

            # 3. Create Image mode
            try:
                ensure_create_image_mode(chrome_driver, tid, job_id)
            except Exception as e:
                _recover_stuck_tab(tid, f"CREATE_IMAGE_FAILED: {e}")
                return

            # 4-7. Upload reference files (Robust State Machine)
            # 7. INVALID REFERENCE PATHS: Every expected reference must exist before browser submission.
            expected_refs = [p for p in info["refs"] if p]
            ref_paths = []
            for p in expected_refs:
                rp = str(Path(p).resolve())
                if not os.path.exists(rp):
                    _recover_stuck_tab(tid, f"UPLOAD_FAILED: Missing reference file {rp}")
                    return
                ref_paths.append(rp)
                
            expected_count = len(ref_paths)
            if expected_count > 0:
                try:
                    perform_robust_upload(chrome_driver, ref_paths, tid, job_id)
                except Exception as e:
                    _recover_stuck_tab(tid, f"SUBMISSION_EXCEPTION: {e}")
                    return

            # 8. Verify attachment count
            verified, actual = verify_attachment_count(chrome_driver, expected_count, tid, job_id)
            if not verified:
                _recover_stuck_tab(tid, f"ATTACHMENT_MISMATCH: expected {expected_count}, got {actual}")
                return

            # 9. Atomic prompt injection
            try:
                _inject_prompt_atomic(chrome_driver, info["prompt"], tid, job_id)
            except PromptFailed as e:
                _recover_stuck_tab(tid, f"PROMPT_FAILED: {e}")
                return

            info["urls_before"] = snapshot_urls(chrome_driver)
            info["chat_urls"] = set()

            # 10. Click Send
            log(f"{prefix} SEND_REQUESTED")
            if not _click_send_button(chrome_driver, tid, job_id):
                _recover_stuck_tab(tid, "SEND_FAILED: Could not click send button")
                return
            log(f"{prefix} SEND_CLICKED")

            # 11. Verify generation started
            log(f"{prefix} GENERATION_SIGNAL_SEARCH")
            if not verify_generation_started(chrome_driver):
                _recover_stuck_tab(tid, "GEN_START_FAILED: No generation signal after Send")
                return

            info["state"] = S_GEN_WAITING
            info["next_poll"] = time.time() + 1.2
            log(f"{prefix} GENERATION_STARTED ✅")
    except Exception as e:
        log(f"{prefix} SUBMISSION_EXCEPTION: {e}", file=sys.stderr)
        _recover_stuck_tab(tid, f"SUBMISSION_EXCEPTION: {e}")

async def poll_active_tabs():
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
            continue
        if now < info["next_poll"]:
            continue

        async with chrome_lock:
            try:
                chrome_driver.switch_to.window(info["handle"])
            except Exception:
                continue

            job_id = info["job_id"]
            prefix = f"[T{tid}][{job_id}]"

            # Per-tab independent timeout
            if now - info["start_time"] > GENERATION_TIMEOUT_S:
                log(f"{prefix} HARD_TIMEOUT after {GENERATION_TIMEOUT_S}s — recovering T{tid} only.")
                _recover_stuck_tab(tid, "GENERATION_TIMEOUT")
                continue

            status, new_src = nb_check_image(chrome_driver, info["urls_before"], info["chat_urls"])

            if status == 'SUCCESS' and not info["download_started"]:
                # IMAGE DETECTED — trigger download ONCE
                info["download_started"] = True
                log(f"{prefix} IMAGE_DETECTED")

                chrome_job_dir, incoming_dir = get_chrome_job_dir(tid, job_id)
                raw_path = chrome_job_dir / f"{job_id}_raw.png"
                files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()

                # PRIMARY: hover-click download (browser native)
                hover_ok = _hover_and_dl_single_click(chrome_driver, info["urls_before"], info["chat_urls"])
                if new_src:
                    info["urls_before"].add(new_src)
                log(f"{prefix} DOWNLOAD_CLICKED (hover_ok={hover_ok})")

                # Register download watcher immediately
                download_state = "DOWNLOAD_WAITING"

                # If hover didn't work, try CDP direct fetch as immediate fallback
                cdp_ok = False
                if not hover_ok:
                    cdp_ok = _direct_fetch_cdp(chrome_driver, str(raw_path), info["urls_before"])
                    if cdp_ok:
                        log(f"{prefix} CDP_FALLBACK_CAPTURE ({raw_path.stat().st_size // 1024} KB)")
                        download_state = "CHROME_RAW_READY"

                dinfo = {
                    "job_id": job_id,
                    "chrome_tab_id": tid,
                    "job": info["job"],
                    "gen": info["gen"],
                    "prompt": info["prompt"],
                    "chrome_job_dir": chrome_job_dir,
                    "incoming_dir": incoming_dir,
                    "raw_path": raw_path,
                    "files_before": files_before,
                    "started_at": time.time(),
                    "last_size": -1,
                    "stable_checks": 0,
                    "state": download_state,
                    "future": info.get("future"),
                    "attempt": info.get("attempt", 1),
                }
                active_downloads[job_id] = dinfo

                # Change state to let poll_active_downloads watch for .crdownload
                # We do NOT wait here under the Chrome lock
                log(f"{prefix} WAITING_FOR_DOWNLOAD_START")
                info["state"] = "DOWNLOAD_START_WAITING"
                info["t_dl_start"] = time.time()
                info["cdp_ok"] = cdp_ok
                info["dinfo"] = dinfo
                
                # Check immediately if next job is queued
                if not job_queue.empty():
                    asyncio.create_task(assign_jobs_to_idle_tabs())
                continue

            elif status == 'ERROR':
                log(f"{prefix} GEMINI_ERROR detected.")
                _recover_stuck_tab(tid, "GEMINI_ERROR")
                continue

            elif status == 'REFUSED':
                log(f"{prefix} PROMPT_REFUSED by Gemini.")
                _recover_stuck_tab(tid, "PROMPT_REFUSED")
                continue

            elif status == 'LIMIT':
                log(f"{prefix} GENERATION_LIMIT reached.")
                _recover_stuck_tab(tid, "GENERATION_LIMIT")
                continue

            else:  # WAITING
                if _send_btn_enabled(chrome_driver) and not _is_gemini_processing(chrome_driver):
                    info["stuck_polls"] += 1
                    if info["stuck_polls"] >= 8:
                        log(f"{prefix} SOFT_STUCK detected (8 consecutive stuck polls) — recovering T{tid} only.")
                        _recover_stuck_tab(tid, "SOFT_STUCK")
                        continue
                else:
                    info["stuck_polls"] = 0

                info["next_poll"] = now + 0.5  # SUPER FAST POLLING

def _recover_stuck_tab(tid: int, reason: str):
    """
    Per-tab only recovery. Never affects other tabs.
    Requeues job if retry budget remains, otherwise fails it.
    Creates a new Gemini chat URL and leaves tab as IDLE.
    """
    info = tab_states[tid]
    job_id = info["job_id"] or "unknown"
    gen = info["gen"]
    future = info.get("future")
    attempt = info.get("attempt", 1)
    prefix = f"[T{tid}][{job_id}]"

    log(f"{prefix} RECOVERING tab T{tid}: {reason}")

    # Save debug artifacts
    try:
        if info.get("handle"):
            chrome_driver.switch_to.window(info["handle"])
            debug_dir = Path("debug") / job_id
            debug_dir.mkdir(parents=True, exist_ok=True)
            chrome_driver.save_screenshot(str(debug_dir / "error.png"))
            with open(debug_dir / "url.txt", "w", encoding="utf-8") as df: df.write(chrome_driver.current_url)
            with open(debug_dir / "body.txt", "w", encoding="utf-8") as df: df.write(chrome_driver.find_element(By.TAG_NAME, "body").text)
            with open(debug_dir / "page.html", "w", encoding="utf-8") as df: df.write(chrome_driver.page_source)
            
            # Additional DOM geometry dump requested by user
            import json
            geom = chrome_driver.execute_script("""
                var out = {url: window.location.href, buttons: [], inputs: [], menus: []};
                var els = document.querySelectorAll('button, input, [role="menuitem"], [role="dialog"], .cdk-overlay-pane');
                els.forEach(function(el) {
                    var r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) return;
                    var cx = r.x + r.width/2;
                    var cy = r.y + r.height/2;
                    var topEl = document.elementFromPoint(cx, cy);
                    var topTag = topEl ? topEl.tagName : 'NONE';
                    var topClass = topEl ? topEl.className : '';
                    out.buttons.push({
                        tag: el.tagName,
                        text: (el.innerText || '').slice(0, 30),
                        aria: el.getAttribute('aria-label'),
                        rect: {x: r.x, y: r.y, w: r.width, h: r.height},
                        topElement: topTag + '.' + topClass
                    });
                });
                return out;
            """)
            with open(debug_dir / "geom.json", "w", encoding="utf-8") as df: json.dump(geom, df, indent=2)
    except Exception:
        pass

    # Close the stuck physical tab entirely — fresh tab created for next job
    try:
        if info.get("handle"):
            chrome_driver.switch_to.window(info["handle"])
            chrome_driver.close()
    except Exception:
        pass
    info["handle"] = None  # will be re-created lazily for next job

    # Capture job data BEFORE clearing tab
    saved_job = info.get("job")
    saved_gen = gen
    saved_prompt = info.get("prompt")
    saved_refs = info.get("refs", [])

    # Clear tab state
    info["state"] = S_IDLE
    info["job"] = None
    info["job_id"] = None
    info["gen"] = None
    info["prompt"] = None
    info["refs"] = []
    info["target_src"] = None
    info["download_started"] = False
    info["stuck_polls"] = 0
    info["start_time"] = 0.0
    info["future"] = None
    info["urls_before"] = set()
    info["chat_urls"] = set()

    # Let BullMQ handle retries. We just fail the internal envelope future.
    if saved_job is not None:
        log(f"{prefix} BROWSER_UI_ERROR ({reason}) — failing internal job to let BullMQ retry.", file=sys.stderr)
        _fail_job(job_id, saved_gen, reason, future, attempt)

    log(f"{prefix} TAB_T{tid}_RECOVERED — ready for next job.")
    if not job_queue.empty():
        asyncio.create_task(assign_jobs_to_idle_tabs())


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

    print("\n" + "=" * 68)
    print(f"PIPELINE STATUS {time.strftime('%H:%M:%S')}")
    print("=" * 68)
    
    print("\nREDIS QUEUE")
    print(f"  WAIT={redis_queue_stats['wait']} | ACTIVE={redis_queue_stats['active']} | DELAYED={redis_queue_stats['delayed']} | PRIORITY={redis_queue_stats['prioritized']} | WAIT_CHILD={redis_queue_stats['waiting-children']}")
    
    print("\nLOCAL PIPELINE")
    print(f"  SUBMIT={submit_count} | GEN={gen_count} | DL_WAIT={dl_waiting} | RAW_READY={dl_raw} | WMR_QUEUE={job_queue.qsize()}")
    print(f"  WMR_PROCESS={wmr_process} | DONE={counters['completed']} | FAIL={counters['failed']}")
    
    print("\nGEMINI")
    for tid in range(MAX_CONCURRENT_TABS):
        st = tab_states[tid]
        jid = (st["job_id"] or "---")[:12]
        elapsed = f"{int(now - st['start_time'])}s" if st["start_time"] > 0 else "0s"
        print(f"  T{tid} = {st['state']:<13} {elapsed:>3}  {jid}")

    print("\nWMR")
    for wid, state, cur_jid in wmr_status:
        jid_str = (cur_jid or "---")[:12]
        print(f"  W{wid} = {state:<13} Job={jid_str}")

    if active_downloads:
        print("\nDOWNLOADS")
        for jid, dinfo in list(active_downloads.items()):
            state_str = dinfo.get('state','?')
            print(f"  {jid[:12]} = {state_str} {now - dinfo['started_at']:.1f}s")
            
    print("=" * 68 + "\n")



