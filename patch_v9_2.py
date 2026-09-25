import re

with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"def _create_gemini_tab\(tid: int\) -> str:[\s\S]*?    return handle"
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
        time.sleep(0.2)
    if not handle:
        raise RuntimeError(f\"Tab T{tid}: Failed to create physical tab via CDP\")
    
    chrome_driver.switch_to.window(handle)
    time.sleep(1.0)
    return handle'''

new_text = re.sub(pattern, new_tab, text)
if text != new_text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched _create_gemini_tab')
else:
    print('Regex failed to match')
