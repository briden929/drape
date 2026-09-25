import re
with open('gemini_process_job.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('hover_ok = _hover_and_dl_single_click(drv, urls_before, chat_urls)', 'files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()\n        hover_ok = _hover_and_dl_single_click(drv, urls_before, chat_urls)')
text = text.replace('        files_before = set(os.listdir(incoming_dir)) if incoming_dir.exists() else set()\n', '')

# Also fix tracking window handles
text = text.replace('info["handle"] = _create_gemini_tab(tid)', 'drv.execute_script("window.open(\'about:blank\', \'_blank\');")\n        drv.switch_to.window(drv.window_handles[-1])\n        self.current_window_handle = drv.current_window_handle')
text = text.replace('drv.switch_to.window(info["handle"])', '# window tracked by finally')
text = text.replace('drv.close()', '')

with open('gemini_process_job.py', 'w', encoding='utf-8') as f:
    f.write(text)
