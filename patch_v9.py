with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_tab = '''def _create_gemini_tab(tid: int) -> str:
    \"\"\"
    Physically create a new Chrome tab for logical slot T{tid}.
    Called lazily the first time a job is assigned to this slot.
    Returns the new window handle.
    \"\"\"
    before = set(chrome_driver.window_handles)
    if not before:
        # Very first tab — use the initial window
        chrome_driver.get(GEMINI_APP_URL)
        time.sleep(0.5)
        handle = chrome_driver.current_window_handle
    else:
        chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': GEMINI_APP_URL})
        deadline = time.time() + 5.0
        handle = None
        while time.time() < deadline:
            diff = set(chrome_driver.window_handles) - before
            if diff:
                handle = list(diff)[0]
                break
            time.sleep(0.1)
        if not handle:
            raise RuntimeError(f\"Tab T{tid}: Failed to create physical tab via CDP\")
        
        chrome_driver.switch_to.window(handle)
        time.sleep(1.0)
    return handle'''

new_tab = '''def _create_gemini_tab(tid: int) -> str:
    \"\"\"
    Physically create a new Chrome tab for logical slot T{tid}.
    Always creates a NEW tab so the anchor tab is never consumed.
    \"\"\"
    if not chrome_driver.window_handles:
        raise RuntimeError(\"BROWSER_SESSION_DEAD: No anchor window exists. Session is broken.\")
    before = set(chrome_driver.window_handles)
    chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': GEMINI_APP_URL})
    deadline = time.time() + 5.0
    handle = None
    while time.time() < deadline:
        diff = set(chrome_driver.window_handles) - before
        if diff:
            handle = list(diff)[0]
            break
        time.sleep(0.1)
    if not handle:
        raise RuntimeError(f\"Tab T{tid}: Failed to create physical tab via CDP\")
    
    chrome_driver.switch_to.window(handle)
    time.sleep(1.0)
    return handle'''

if old_tab in text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(text.replace(old_tab, new_tab))
    print('Successfully patched _create_gemini_tab')
else:
    print('Failed to find old tab creation code')
