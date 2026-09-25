import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

bad_newchat = """                drv.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(staging_dir)})
                curr = drv.current_url
                if 'gemini.google.com/app' not in curr:
                    drv.get('https://gemini.google.com/app')"""

good_newchat = """                drv.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(staging_dir)})
                # Rule 14: New Chat explicitly.
                open_new_chat_and_reload(drv, self.tid, job_id)"""

source = source.replace(bad_newchat, good_newchat)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(source)
