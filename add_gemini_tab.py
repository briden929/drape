with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("""
    add('''
gemini_driver_lock = threading.Lock()

def _ensure_gemini_tab(tid, window_handle):
    global chrome_driver
    if not check_chrome_driver_health(chrome_driver)['alive']:
        raise RuntimeError('Global chrome_driver is dead')
        
    with gemini_driver_lock:
        if window_handle:
            try:
                if window_handle in chrome_driver.window_handles:
                    chrome_driver.switch_to.window(window_handle)
                    return window_handle
            except Exception:
                pass
                
        log(f'[T{tid}] Creating new logical Gemini tab...')
        chrome_driver.execute_cdp_cmd('Target.createTarget', {'url': 'about:blank'})
        for h in chrome_driver.window_handles:
            chrome_driver.switch_to.window(h)
            if chrome_driver.current_url == 'about:blank' or chrome_driver.current_url.startswith('data:'):
                return h
                
        return chrome_driver.window_handles[-1]
''')
""")
