with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("""
    add('''
async def poll_active_downloads():
    while True:
        try:
            completed_guids = []
            for guid, dinfo in list(download_registry.items()):
                ctx = dinfo['ctx']
                prefix = f"[JOB {ctx.job_id}]"
                
                staging_dir = dinfo['staging_dir']
                files_before = dinfo['files_before']
                
                if not staging_dir.exists():
                    continue
                    
                cur = set(staging_dir.iterdir())
                new_files = cur - files_before
                
                crdownloads = [f for f in new_files if f.name.endswith('.crdownload')]
                if crdownloads:
                    continue
                    
                final_files = [f for f in new_files if f.name.endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                if not final_files:
                    if time.time() - dinfo['started_at'] > DOWNLOAD_TIMEOUT_S:
                        log(f"{prefix} DOWNLOAD_TIMEOUT")
                        ctx.error_message = "Download timeout"
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                        completed_guids.append(guid)
                    continue
                    
                # Download complete!
                dl_file = final_files[0]
                
                # Stabilize size
                sz1 = dl_file.stat().st_size
                await asyncio.sleep(0.5)
                sz2 = dl_file.stat().st_size
                if sz1 != sz2:
                    continue
                    
                if dinfo['type'] == 'GEMINI':
                    import shutil
                    raw_path = dinfo['job_dir'] / f"{ctx.job_id}_raw{dl_file.suffix}"
                    shutil.move(str(dl_file), str(raw_path))
                    ctx.raw_path = raw_path
                    log(f"{prefix} RAW_DOWNLOAD_COMPLETE: {raw_path.name}")
                    
                    try:
                        valid, msg = validate_image_file(str(raw_path), 512, 1024)
                        if not valid:
                            raise Exception(f"Invalid raw image: {msg}")
                        ctx.transition(JobState.RAW_READY)
                    except Exception as e:
                        ctx.error_message = str(e)
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                        
                elif dinfo['type'] == 'WMR':
                    import shutil
                    clean_path = dinfo['job_dir'] / f"{ctx.job_id}_clean{dl_file.suffix}"
                    shutil.move(str(dl_file), str(clean_path))
                    ctx.clean_path = clean_path
                    log(f"{prefix} CLEAN_DOWNLOAD_COMPLETE: {clean_path.name}")
                    
                    try:
                        valid, msg = validate_image_file(str(clean_path), 512, 1024)
                        if not valid:
                            raise Exception(f"Invalid clean image: {msg}")
                        ctx.transition(JobState.CLEAN_READY)
                    except Exception as e:
                        ctx.error_message = str(e)
                        ctx.transition(JobState.FAILED)
                        resolve_future_once(main_loop, ctx.future, None, is_exception=True)
                        
                completed_guids.append(guid)
                
            for g in completed_guids:
                del download_registry[g]
                
        except Exception as e:
            traceback.print_exc()
        await asyncio.sleep(1.0)
''')
""")
