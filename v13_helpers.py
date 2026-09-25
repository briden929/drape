def _get_current_model_text(drv):
    selectors = ["div[data-test-id='logo-pill-label-container'] span.picker-primary-text", "div[data-test-id='logo-pill-label-container'] span.gds-body-m", 'span.picker-primary-text']
    for sel in selectors:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    txt = (el.text or '').strip()
                    if txt:
                        return txt
        except Exception:
            continue
    try:
        txt = drv.execute_script('var el=document.querySelector(  \'div[data-test-id="logo-pill-label-container"] span.picker-primary-text,   div[data-test-id="logo-pill-label-container"] span.gds-body-m\');return el ? el.textContent.trim() : \'\';')
        return (txt or '').strip()
    except Exception:
        return ''

def _open_model_picker(drv):
    try:
        btn = drv.find_element(By.CSS_SELECTOR, "button[data-test-id='bard-mode-menu-button']")
        if btn and btn.is_displayed():
            drv.execute_script('arguments[0].click();', btn)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        el = drv.find_element(By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container']")
        if el and el.is_displayed():
            drv.execute_script('arguments[0].click();', el)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        res = drv.execute_script("var spans=document.querySelectorAll('span.picker-primary-text,span.gds-body-m');for(var i=0;i<spans.length;i++){  var s=spans[i]; if(!s.offsetParent) continue;  var b=s.closest('button');  if(b&&!b.disabled){ b.click(); return 'OK'; }} return 'NO';")
        if res == 'OK':
            time.sleep(0.45)
            return True
    except Exception:
        pass
    return False

def ensure_flash_mode(drv, tid=0, job_id=''):
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    current = _get_current_model_text(drv)
    if current and 'flash' in current.lower() and ('lite' not in current.lower()):
        log(f"{prefix} FLASH_VERIFIED (already active: '{current}')")
        return True
    for attempt in range(1, 4):
        if not _open_model_picker(drv):
            time.sleep(0.4)
            continue
        time.sleep(0.3)
        try:
            clicked = _click_flash_in_picker(drv)
        except ModelLimitReached:
            try:
                drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            except Exception:
                pass
            raise
        if clicked and _verify_flash_selected(drv, timeout=2.5):
            log(f'{prefix} FLASH_VERIFIED ✅')
            return True
        try:
            drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError(f'Tab T{tid}: Flash mode could not be verified')

def is_create_image_mode(drv):
    try:
        editors = drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder*='Describe'], div.ql-editor[data-placeholder*='image']")
        if any((e.is_displayed() for e in editors)):
            return True
        signals = ["mat-icon[data-mat-icon-name='image_create']", "mat-icon[fonticon='image_create']", "button[aria-label*='Aspect ratio']", "//span[contains(text(), 'Aspect ratio')]", "//h1[contains(text(), 'Create images')]", "//button[contains(., 'Images')]"]
        for sig in signals:
            by = By.XPATH if sig.startswith('//') else By.CSS_SELECTOR
            for el in drv.find_elements(by, sig):
                if el.is_displayed():
                    return True
        return False
    except Exception:
        return False
        signals = ["mat-icon[data-mat-icon-name='image_create']", "mat-icon[fonticon='image_create']", "button[aria-label*='Aspect ratio']", "//span[contains(text(), 'Aspect ratio')]", "//button[contains(., 'Images')]"]
        for sig in signals:
            by = By.XPATH if sig.startswith('//') else By.CSS_SELECTOR
            for el in drv.find_elements(by, sig):
                if el.is_displayed():
                    return True
        return len(editors) > 0
    except Exception:
        return False

def ensure_create_image_mode(drv, tid=0, job_id=''):
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    deadline = time.time() + 4.0
    while time.time() < deadline:
        if is_create_image_mode(drv):
            log(f'{prefix} CREATE_IMAGE_VERIFIED')
            return True
        time.sleep(0.5)
    for attempt in range(1, 3):
        if click_plus_button(drv):
            time.sleep(0.5)
            try:
                btns = drv.find_elements(By.CSS_SELECTOR, "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button")
                for btn in btns:
                    if btn.is_displayed() and 'create image' in btn.text.lower():
                        drv.execute_script('arguments[0].click();', btn)
                        time.sleep(1.0)
                        break
                else:
                    for icon in drv.find_elements(By.CSS_SELECTOR, "mat-icon[data-mat-icon-name='image_create'], mat-icon[fonticon='image_create']"):
                        if icon.is_displayed():
                            btn = drv.execute_script("var e=arguments[0];while(e&&e.tagName!=='BUTTON')e=e.parentElement;return e;", icon)
                            if btn and btn.is_displayed():
                                drv.execute_script('arguments[0].click();', btn)
                                time.sleep(1.0)
                                break
            except Exception:
                pass
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if is_create_image_mode(drv):
                log(f'{prefix} CREATE_IMAGE_VERIFIED')
                return True
            time.sleep(0.5)
    raise RuntimeError(f'Tab T{tid}: Failed to activate Create image mode')

def perform_robust_upload(drv, paths, tid=0, job_id=''):
    """
    Robust upload state machine.
    1. Check for file input directly
    2. If not found, open drawer, find upload button, click, wait for file input
    3. Handles retries and recovery logic.
    Raises RuntimeError on failure.
    """
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    log(f'{prefix} FILE_INPUT_DIRECT_CHECK')
    fi = _find_file_input(drv)
    if fi:
        log(f'{prefix} FILE_INPUT_READY (direct)')
    else:
        log(f'{prefix} FILE_INPUT_NOT_FOUND')
        for attempt in range(1, 4):
            log(f'{prefix} UPLOAD_DRAWER_OPENING (attempt {attempt})')
            click_plus_button(drv)
            time.sleep(0.5)
            log(f'{prefix} UPLOAD_DRAWER_OPENED')
            clicked = False
            for sel in ["button[data-test-id='local-images-files-uploader-button']", "//span[contains(text(),'Upload files')]/ancestor::button", "//div[contains(text(),'Upload files')]/ancestor::button", "//span[contains(text(),'Upload from computer')]/ancestor::button", "//span[contains(text(),'Upload file')]/ancestor::button"]:
                try:
                    by = By.XPATH if sel.startswith('//') else By.CSS_SELECTOR
                    for btn in drv.find_elements(by, sel):
                        if btn.is_displayed() and btn.is_enabled():
                            log(f'{prefix} UPLOAD_CONTROL_FOUND: {sel}')
                            drv.execute_script('arguments[0].click();', btn)
                            log(f'{prefix} UPLOAD_CONTROL_CLICKED')
                            clicked = True
                            break
                except Exception:
                    continue
                if clicked:
                    break
            if not clicked:
                try:
                    res = drv.execute_script("\n                        var btns = document.querySelectorAll('button');\n                        for (var i = 0; i < btns.length; i++) {\n                            var text = btns[i].textContent.toLowerCase();\n                            if (btns[i].offsetParent !== null && (text.indexOf('upload files') !== -1 || text.indexOf('upload from computer') !== -1 || text.indexOf('upload file') !== -1 || text.indexOf('choose files') !== -1 || text.indexOf('add files') !== -1)) {\n                                btns[i].click(); return 'OK';\n                            }\n                        } return 'NO';\n                    ")
                    if res == 'OK':
                        log(f'{prefix} UPLOAD_CONTROL_FOUND: JS fallback')
                        log(f'{prefix} UPLOAD_CONTROL_CLICKED')
                        clicked = True
                except Exception:
                    pass
            if clicked:
                deadline = time.time() + 6.0
                while time.time() < deadline:
                    fi = _find_file_input(drv)
                    if fi:
                        log(f'{prefix} FILE_INPUT_READY')
                        break
                    time.sleep(0.3)
                if fi:
                    break
            if attempt == 3:
                raise RuntimeError('UPLOAD_CONTROL_NOT_CLICKABLE (exhausted 3 retries)')
            log(f'{prefix} UPLOAD_DRAWER_FAILED — reloading page before retry')
            drv.refresh()
            time.sleep(2.0)
            ensure_create_image_mode(drv, tid, job_id)
    if not fi:
        raise RuntimeError('FILE_INPUT_MISSING after click')
    try:
        fi.send_keys('\n'.join(paths))
        log(f'{prefix} UPLOAD_SENT {len(paths)} files')
    except Exception as e:
        raise RuntimeError(f'UPLOAD_FAILED: {e}')

def verify_attachment_count(drv, expected: int, tid=0, job_id='') -> tuple:
    """
    Polls until attachment count == expected. Uses canonical identities to avoid double counting wrappers.
    Returns (verified: bool, actual_count: int).
    """
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    if expected == 0:
        return (True, 0)
    deadline = time.time() + 15.0
    actual_count = 0
    while time.time() < deadline:
        identities = set()
        try:
            els = drv.find_elements(By.CSS_SELECTOR, 'gem-media-attachment')
            for idx, el in enumerate(els):
                if el.is_displayed():
                    identities.add(f'attachment-{idx}')
        except Exception:
            pass
        actual_count = len(identities)
        if actual_count == expected:
            log(f'{prefix} ATTACHMENT_IDENTITIES expected={expected} actual={actual_count}')
            log(f'{prefix} ATTACHMENTS_VERIFIED')
            return (True, actual_count)
        time.sleep(0.5)
    log(f'{prefix} ATTACHMENT_TIMEOUT expected {expected}, actual {actual_count}')
    return (False, actual_count)

def _inject_prompt_atomic(drv, text, tid=0, job_id=''):
    """
    Inject full prompt in ONE atomic operation.
    Primary: Chrome CDP Input.insertText
    Fallback: single xclip Ctrl+V
    No chunked/loop typing ever.
    """
    prefix = f'[T{tid}][{job_id}]' if job_id else f'[T{tid}]'
    editor = get_quill_editor(drv)
    if not editor:
        raise PromptFailed(f'Tab T{tid}: Quill editor not found')
    for attempt in range(1, 3):
        try:
            drv.execute_script('arguments[0].focus();', editor)
            time.sleep(0.1)
            ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
            time.sleep(0.05)
            ActionChains(drv).send_keys(Keys.DELETE).perform()
            drv.execute_script("document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);")
            time.sleep(0.1)
            cdp_ok = False
            try:
                drv.execute_cdp_cmd('Input.insertText', {'text': text})
                cdp_ok = True
                log(f'{prefix} PROMPT_INJECTING via CDP')
            except Exception as cdp_err:
                log(f'{prefix} CDP notice ({cdp_err}), trying xclip fallback...')
            if not cdp_ok:
                if _set_clipboard_xclip(text):
                    drv.execute_script('arguments[0].focus();', editor)
                    ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                    log(f'{prefix} PROMPT_INJECTING via xclip Ctrl+V')
                else:
                    log(f'{prefix} xclip failed', file=sys.stderr)
            time.sleep(0.3)
            if _verify_editor_prompt(drv, editor, text, tid=tid, job_id=job_id):
                return True
            else:
                log(f'{prefix} PROMPT_VERIFY_FAIL attempt {attempt} — clearing and retrying')
                drv.execute_script("arguments[0].focus();document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);", editor)
                time.sleep(0.3)
        except PromptFailed:
            raise
        except Exception as e:
            log(f'{prefix} Prompt injection exception (attempt {attempt}): {e}')
            try:
                drv.execute_script("arguments[0].focus();document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);", editor)
            except Exception:
                pass
            time.sleep(0.3)
    raise PromptFailed(f'Tab T{tid}: Prompt injection failed after 2 atomic attempts')

def _click_send_button(drv):
    try:
        res = drv.execute_script('\n            var sels = [\'mat-icon[fonticon="arrow_upward"]\', \'mat-icon[data-mat-icon-name="arrow_upward"]\',\n                        \'mat-icon[fonticon="send"]\', \'button[aria-label="Send message"]\'];\n            for (var s = 0; s < sels.length; s++) {\n                var els = document.querySelectorAll(sels[s]);\n                for (var i = 0; i < els.length; i++) {\n                    var b = els[i].tagName === \'BUTTON\' ? els[i] : els[i].closest(\'button\');\n                    if (b && !b.disabled && b.offsetParent !== null) { b.click(); return \'OK\'; }\n                }\n            } return \'NO\';\n        ')
        if res == 'OK':
            return True
    except Exception:
        pass
    for xp in ["//mat-icon[@data-mat-icon-name='arrow_upward']/ancestor::button", "//mat-icon[@fonticon='arrow_upward']/ancestor::button", "//button[@aria-label='Send message']"]:
        try:
            for btn in drv.find_elements(By.XPATH, xp):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script('arguments[0].click();', btn)
                    return True
        except Exception:
            continue
    return False

def verify_generation_started(drv, timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            stop = drv.execute_script('\n                var sels = [\'button[aria-label="Stop generating"]\', \'button[aria-label="Cancel"]\',\n                            \'mat-icon[fonticon="stop"]\', \'mat-icon[data-mat-icon-name="stop"]\'];\n                for (var s = 0; s < sels.length; s++) {\n                    var els = document.querySelectorAll(sels[s]);\n                    for (var i = 0; i < els.length; i++) {\n                        if (els[i].offsetParent !== null) return true;\n                    }\n                } return false;\n            ')
            if stop:
                return True
            loading = drv.execute_script('\n                var el = document.querySelector(\'image-loading-overlay [data-test-id="image-loading-overlay"]\');\n                if (el && el.offsetParent !== null) {\n                    return !el.classList.contains(\'done-generating\');\n                } return false;\n            ')
            if loading:
                return True
            in_prog = drv.execute_script("\n                var el = document.querySelector('model-response .generating-sparkle, model-response .loading');\n                return el !== null && el.offsetParent !== null;\n            ")
            if in_prog:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

