async def _submit_job_to_tab(tid: int):
    """
    Full strict submission pipeline:
    new chat -> flash -> create image -> drawer -> file input -> upload -> verify count
    -> inject prompt -> send -> verify generation started
    Any failure recovers the tab immediately. No silent continues.
    """
    info = tab_states[tid]
    job_id = info['job_id']
    prefix = f'[T{tid}][{job_id}]'
    if info['handle'] is None:
        try:
            info['handle'] = _create_gemini_tab(tid)
            log(f'{prefix} [T{tid}] IDLE (first use — physical tab created)')
        except Exception as e:
            log(f'{prefix} LAZY_TAB_CREATE_FAILED: {e}', file=sys.stderr)
            _recover_stuck_tab(tid, f'LAZY_TAB_CREATE_FAILED: {e}')
            return
    try:
        async with chrome_lock:
            chrome_driver.switch_to.window(info['handle'])
            info['state'] = S_NEW_CHAT
            log(f'{prefix} NEW_CHAT_START')
            try:
                new_chat_url = open_new_chat_and_reload(chrome_driver, tid, job_id)
                log(f'{prefix} NEW_CHAT_VERIFIED -> {new_chat_url}')
            except NewChatFailed as e:
                _recover_stuck_tab(tid, str(e))
                return
            info['state'] = S_SUBMITTING
            try:
                ensure_flash_mode(chrome_driver, tid, job_id)
            except ModelLimitReached:
                _recover_stuck_tab(tid, 'FLASH_FAILED: ModelLimitReached')
                return
            except Exception as e:
                _recover_stuck_tab(tid, f'FLASH_FAILED: {e}')
                return
            try:
                ensure_create_image_mode(chrome_driver, tid, job_id)
            except Exception as e:
                _recover_stuck_tab(tid, f'CREATE_IMAGE_FAILED: {e}')
                return
            if not open_upload_drawer(chrome_driver, tid, job_id):
                _recover_stuck_tab(tid, 'DRAWER_FAILED: Could not open upload drawer')
                return
            if not click_upload_files_in_drawer(chrome_driver):
                raise RuntimeError(f'{prefix} DRAWER_FAILED: Could not click Upload files in drawer')
            time.sleep(0.1)
            try:
                fi = find_file_input_strict(chrome_driver, tid, job_id)
            except FileInputMissing as e:
                _recover_stuck_tab(tid, f'FILE_INPUT_MISSING: {e}')
                return
            ref_paths = [str(Path(p).resolve()) for p in info['refs'] if p and os.path.exists(p)]
            expected_count = len(ref_paths)
            try:
                fi.send_keys('\n'.join(ref_paths))
                log(f'{prefix} UPLOAD_SENT {expected_count} files')
            except Exception as e:
                _recover_stuck_tab(tid, f'UPLOAD_FAILED: {e}')
                return
            verified, actual = verify_attachment_count(chrome_driver, expected_count, tid, job_id)
            if not verified:
                _recover_stuck_tab(tid, f'ATTACHMENT_MISMATCH: expected {expected_count}, got {actual}')
                return
            try:
                _inject_prompt_atomic(chrome_driver, info['prompt'], tid, job_id)
            except PromptFailed as e:
                _recover_stuck_tab(tid, f'PROMPT_FAILED: {e}')
                return
            info['urls_before'] = snapshot_urls(chrome_driver)
            info['chat_urls'] = set()
            if not _click_send_button(chrome_driver):
                _recover_stuck_tab(tid, 'SEND_FAILED: Could not click send button')
                return
            log(f'{prefix} GENERATION_STARTING...')
            if not verify_generation_started(chrome_driver):
                _recover_stuck_tab(tid, 'GEN_START_FAILED: No generation signal after Send')
                return
            info['state'] = S_GEN_WAITING
            info['next_poll'] = time.time() + 1.2
            log(f'{prefix} GENERATION_STARTED ✅ — tab in GEN_WAITING.')
    except Exception as e:
        log(f'{prefix} SUBMISSION_EXCEPTION: {e}', file=sys.stderr)
        _recover_stuck_tab(tid, f'SUBMISSION_EXCEPTION: {e}')