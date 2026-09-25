import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''            # 10. Click Send
            if not _click_send_button(chrome_driver):
                _recover_stuck_tab(tid, "SEND_FAILED: Could not click send button")
                return

            # 11. Verify generation started
            log(f"{prefix} GENERATION_STARTING...")
            if not verify_generation_started(chrome_driver):
                _recover_stuck_tab(tid, "GEN_START_FAILED: No generation signal after Send")
                return

            info["state"] = S_GEN_WAITING
            info["next_poll"] = time.time() + 1.2
            log(f"{prefix} GENERATION_STARTED ✅ — tab in GEN_WAITING.")'''

replacement = '''            # 10. Click Send
            log(f"{prefix} SEND_REQUESTED")
            if not _click_send_button(chrome_driver):
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
            log(f"{prefix} GENERATION_STARTED ✅")'''

if target in text:
    text = text.replace(target, replacement)
    with open('v10_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched send logs')
else:
    print('Target not found')
