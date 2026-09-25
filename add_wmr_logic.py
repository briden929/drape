with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("""
    add('''
wmr_tab_handles = {}

def _ensure_wmr_tab(driver, resource_id):
    if not check_chrome_driver_health(driver)['alive']:
        raise RuntimeError(f'Driver for {resource_id} is dead')
        
    handle = wmr_tab_handles.get(resource_id)
    if handle:
        try:
            if handle in driver.window_handles:
                driver.switch_to.window(handle)
                return
        except Exception:
            pass
            
    log(f'[{resource_id}] Creating new logical WMR tab...')
    driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
    for h in driver.window_handles:
        driver.switch_to.window(h)
        if driver.current_url == 'about:blank' or driver.current_url.startswith('data:'):
            wmr_tab_handles[resource_id] = h
            break
            
    if resource_id not in wmr_tab_handles:
        wmr_tab_handles[resource_id] = driver.window_handles[-1]
        
    driver.switch_to.window(wmr_tab_handles[resource_id])

def _run_wmr_logic(driver, ctx: JobContext):
    resource_id = ctx.assigned_wmr_tab
    job_id = ctx.job_id
    prefix = f'[{resource_id}][{job_id}]'
    
    _ensure_wmr_tab(driver, resource_id)
    
    job_dir, incoming_dir = get_wmr_job_dir(0, job_id)  # The directory structure doesn't strictly need tab ID if isolated by job_id
    profile_id = int(resource_id.split('-')[0][1:])
    staging_dir = Path(f'/content/downloads/wmr_staging/W{profile_id}')
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    driver.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(staging_dir)})
    
    if 'pixelcut.ai' not in driver.current_url:
        driver.get('https://www.pixelcut.ai/watermark-remover')
        
    time.sleep(1)
    
    inp = _wmr_find_file_input(driver)
    if not inp:
        raise Exception('WMR_FILE_INPUT_MISSING')
        
    inp.send_keys(str(ctx.raw_path))
    ctx.transition(JobState.WMR_PROCESSING)
    log(f'{prefix} UPLOADED -> PROCESSING')
    
    status = _wmr_check_status(driver)
    if status != 'SUCCESS':
        raise Exception(f'WMR_FAILED: {status}')
        
    log(f'{prefix} RESULT_READY')
    
    files_before = set(staging_dir.iterdir()) if staging_dir.exists() else set()
    
    if not _wmr_click_download(driver):
        raise Exception('WMR_CLICK_DOWNLOAD_FAILED')
        
    ctx.transition(JobState.WMR_DOWNLOAD_CLICKED)
    
    dl_guid = None
    t1 = time.time()
    while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
        for entry in driver.get_log('performance'):
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
        log(f'{prefix} WMR_DOWNLOAD_START_EVENT guid={dl_guid}')
        ctx.wmr_download_guid = dl_guid or f'fs_fallback_{job_id}'
        ctx.transition(JobState.WMR_RESOURCE_RELEASED)
        
        download_registry[ctx.wmr_download_guid] = {
            'ctx': ctx,
            'type': 'WMR',
            'staging_dir': staging_dir,
            'files_before': files_before,
            'started_at': time.time(),
            'job_dir': job_dir,
            'incoming_dir': incoming_dir
        }
        
        def _reg():
            WMR_BROKER.release(resource_id)
        main_loop.call_soon_threadsafe(_reg)
    else:
        raise Exception('WMR_DOWNLOAD_START_FAILED')
''')
""")
