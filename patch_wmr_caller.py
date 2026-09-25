import re

with open('v12_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_sig = '                # DOWNLOAD_BUTTON_DETECTED'
end_sig = '                # Wait for download COMPLETION'

start_idx = text.find(start_sig)
end_idx = text.find(end_sig)

if start_idx == -1 or end_idx == -1:
    print('Could not find wmr click caller block boundaries')
    exit(1)

new_code = '''                # DOWNLOAD_BUTTON_DETECTED
                log(f"[WMR-W{self.worker_id}][{job_id}] DOWNLOAD_BUTTON_DETECTED")
                
                dl_started = False
                prefix = f"[WMR-W{self.worker_id}][{job_id}]"
                for click_attempt in range(1, 3):
                    if not _wmr_click_download(drv, prefix):
                        log(f"{prefix} WMR download click failed (click_attempt {click_attempt})")
                        time.sleep(1.0)
                        continue
                        
                    log(f"{prefix} DOWNLOAD_CLICKED")

                    # Detect download START (.crdownload or new image file)
                    t1 = time.time()
                    while time.time() - t1 < DOWNLOAD_START_WINDOW_S:
                        cur = set(os.listdir(self.staging_dir))
                        new_files = cur - files_before_staging
                        if any(fn.endswith('.crdownload') or fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) for fn in new_files):
                            dl_started = True
                            break
                        time.sleep(0.3)

                    if dl_started:
                        break
                        
                    log(f"{prefix} WMR_DOWNLOAD_START_FAILED (click_attempt {click_attempt}), retrying click...")
                    
                if not dl_started:
                    log(f"{prefix} Failed to start download after 2 click attempts (job attempt {attempt})")
                    continue
                    
                log(f"{prefix} WMR_DOWNLOAD_START_CONFIRMED")

'''

text = text[:start_idx] + new_code + text[end_idx:]

with open('v12_work.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Patched wmr click caller!')
