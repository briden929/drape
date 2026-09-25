with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("""
    add('''
gemini_driver_lock = threading.Lock()

class GeminiWorker:
    def __init__(self, tid: int):
        self.tid = tid
        self.state = 'IDLE'
        self.current_job_id = None
        self.start_time = 0
        self.window_handle = None

    def _ensure_tab(self):
        global chrome_driver
        if not check_chrome_driver_health(chrome_driver)['alive']:
            raise RuntimeError('Global chrome_driver is dead')
            
        with gemini_driver_lock:
            if self.window_handle:
                try:
                    if self.window_handle in chrome_driver.window_handles:
                        chrome_driver.switch_to.window(self.window_handle)
                        return chrome_driver
                except Exception:
                    pass
            log(f'[T{self.tid}] Creating new logical Gemini tab...')
            chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
            for h in chrome_driver.window_handles:
                chrome_driver.switch_to.window(h)
                if chrome_driver.current_url == 'about:blank' or chrome_driver.current_url.startswith('data:'):
                    self.window_handle = h
                    break
            if not self.window_handle:
                self.window_handle = chrome_driver.window_handles[-1]
            chrome_driver.switch_to.window(self.window_handle)
            return chrome_driver

    def process_job(self, ctx: JobContext):
        t = threading.Thread(target=self._process_job_thread, args=(ctx,))
        t.start()

    def _process_job_thread(self, ctx: JobContext):
        global chrome_driver
        job_id = ctx.job_id
        future = ctx.future
        prefix = f'[T{self.tid}][{job_id}]'
        
        self.current_job_id = job_id
        self.state = 'SUBMITTING'
        self.start_time = time.time()
        
        try:
            drv = self._ensure_tab()
            
            job_dir, incoming_dir = get_chrome_job_dir(self.tid, job_id)
            staging_dir = Path(f'/content/downloads/chrome_staging/T{self.tid}')
            staging_dir.mkdir(parents=True, exist_ok=True)
            
            with gemini_driver_lock:
                drv.switch_to.window(self.window_handle)
                drv.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(staging_dir)})
                curr = drv.current_url
                if 'gemini.google.com/app' not in curr:
                    drv.get('https://gemini.google.com/app')
                else:
                    drv.get('https://gemini.google.com/app')
                    
            time.sleep(1)
            
            with gemini_driver_lock:
                drv.switch_to.window(self.window_handle)
                _ = drv.get_log('performance')
                log(f'{prefix} FRESH_BROWSER_READY')
                if not nb_check_image(drv, prefix):
                    raise Exception('COMPOSER_FAILED')
                log(f'{prefix} CLEAN_COMPOSER_VERIFIED')
                ensure_flash_mode(drv, self.tid, job_id)
                ensure_create_image_mode(drv, self.tid, job_id)
                
                refs = ctx.refs
                expected_refs = [p for p in refs if p]
                ref_paths = [str(Path(p).resolve()) for p in expected_refs]
                if ref_paths:
                    perform_robust_upload(drv, ref_paths, self.tid, job_id)
                    verified, actual = verify_attachment_count(drv, len(ref_paths), self.tid, job_id)
                    if not verified:
                        raise Exception(f'ATTACHMENT_MISMATCH: expected {len(ref_paths)}, got {actual}')
                        
                _inject_prompt_atomic(drv, ctx.prompt, self.tid, job_id)
                urls_before = snapshot_urls(drv)
                chat_urls = {u for u in urls_before if '/app/' in u}
                log(f'{prefix} SEND_REQUESTED')
                
                if not _click_send_button(drv, self.tid, job_id):
                    raise Exception('SEND_FAILED')
                log(f'{prefix} SEND_CLICKED')
                
                if not verify_generation_started(drv):
                    raise Exception('GEN_START_FAILED')
                    
            ctx.transition(JobState.GENERATING)
            self.state = 'GENERATING'
            log(f'{prefix} GENERATING')
            
            t0 = time.time()
            image_detected = False
            while time.time() - t0 < GENERATION_TIMEOUT_S:
                with gemini_driver_lock:
                    drv.switch_to.window(self.window_handle)
                    status, new_src = nb_check_image(drv, urls_before, chat_urls)
                if status == 'SUCCESS':
                    image_detected = True
                    if new_src:
                        urls_before.add(new_src)
                    break
                time.sleep(1.0)
                
            if not image_detected:
                raise Exception('GENERATION_TIMEOUT')
                
            log(f'{prefix} IMAGE_DETECTED')
            
            files_before = set(staging_dir.iterdir()) if staging_dir.exists() else set()
            
            with gemini_driver_lock:
                drv.switch_to.window(self.window_handle)
                hover_ok = _hover_and_dl_single_click(drv, urls_before, chat_urls)
            
            log(f'{prefix} DOWNLOAD_CLICKED (hover_ok={hover_ok})')
            
            ctx.transition(JobState.GEMINI_DOWNLOAD_STARTED)
            self.state = 'DOWNLOAD_START_WAIT'
            
            dl_guid = None
            t1 = time.time()
            while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                with gemini_driver_lock:
                    drv.switch_to.window(self.window_handle)
                    for entry in drv.get_log('performance'):
                        try:
                            msg = json.loads(entry['message'])['message']
                            if msg['method'] == 'Browser.downloadWillBegin':
                                dl_guid = msg['params']['guid']
                                break
                        except:
                            pass
                if dl_guid:
                    break
                time.sleep(0.1)
                
            dl_confirmed_fs = False
            t2 = time.time()
            while time.time() - t2 < DOWNLOAD_START_WINDOW_S:
                if staging_dir.exists():
                    cur = set(staging_dir.iterdir())
                    new_files = cur - files_before
                    for nf in new_files:
                        if nf.name.endswith('.crdownload') or nf.name.endswith('.png') or nf.name.endswith('.jpg') or nf.name.endswith('.webp'):
                            dl_confirmed_fs = True
                            break
                if dl_confirmed_fs:
                    break
                time.sleep(0.1)
                
            if dl_confirmed_fs:
                log(f'{prefix} DOWNLOAD_START_EVENT guid={dl_guid}')
                log(f'{prefix} DOWNLOAD_FILESYSTEM_START_CONFIRMED')
                ctx.gemini_download_guid = dl_guid or f'fs_fallback_{job_id}'
                ctx.transition(JobState.GEMINI_RESOURCE_RELEASED)
                
                download_registry[ctx.gemini_download_guid] = {
                    'ctx': ctx,
                    'type': 'GEMINI',
                    'staging_dir': staging_dir,
                    'files_before': files_before,
                    'started_at': time.time(),
                    'job_dir': job_dir,
                    'incoming_dir': incoming_dir
                }

                def _reg():
                    GEMINI_BROKER.release(self.tid)
                    self.state = 'IDLE'
                    self.current_job_id = None
                    log(f'{prefix} T_RELEASED')
                    
                main_loop.call_soon_threadsafe(_reg)
            else:
                raise Exception('DOWNLOAD_START_FAILED')
                
        except Exception as e:
            log(f'{prefix} GEMINI_FAILED: {e}')
            ctx.error_message = f'Gemini failed: {e}'
            ctx.transition(JobState.FAILED)
            resolve_future_once(main_loop, future, None, is_exception=True)

            def _rel():
                GEMINI_BROKER.release(self.tid)
                self.state = 'IDLE'
                self.current_job_id = None
            main_loop.call_soon_threadsafe(_rel)
''')
""")
