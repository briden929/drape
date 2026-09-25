import re

with open('v12_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('self.state = "PROCESSING"', 'self.state = "UPLOADING"')
text = text.replace('log(f"[WMR-W{self.worker_id}][{job_id}] WMR_PROCESSING")', 'self.state = "PROCESSING"; log(f"[WMR-W{self.worker_id}][{job_id}] WMR_PROCESSING")')
text = text.replace('log(f"{prefix} DOWNLOAD_BUTTON_DETECTED")', 'self.state = "WAIT_DOWNLOAD"; log(f"{prefix} DOWNLOAD_BUTTON_DETECTED")')
text = text.replace('log(f"{prefix} DOWNLOAD_CLICKED")', 'self.state = "DOWNLOADING"; log(f"{prefix} DOWNLOAD_CLICKED")')
text = text.replace('found = _wmr_wait_for_new_file(self.staging_dir, files_before_staging, timeout=60)', 'self.state = "VALIDATING"; found = _wmr_wait_for_new_file(self.staging_dir, files_before_staging, timeout=60)')
text = text.replace('log(f"{prefix} WMR_COMPLETE -> ', 'self.state = "FINALIZING"; log(f"{prefix} WMR_COMPLETE -> ')

with open('v12_work.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated WMR states')
