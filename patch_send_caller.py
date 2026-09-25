import re

with open('v11_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'if not _click_send_button(chrome_driver):'
replacement = 'if not _click_send_button(chrome_driver, tid, job_id):'

if target in text:
    text = text.replace(target, replacement)
    with open('v11_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched send usage')
else:
    print('Not found')
