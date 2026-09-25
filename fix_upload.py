import os
import re

FINAL = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_FINAL.py"

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

upload_block = """            if not open_upload_drawer(self.driver, tid_int, ctx.job_id):
                raise Exception("DRAWER_FAILED: Could not open upload drawer")
            if not click_upload_files_in_drawer(self.driver):
                raise Exception("DRAWER_FAILED: Could not click Upload files in drawer")
            time.sleep(0.1)
            fi = find_file_input_strict(self.driver, tid_int, ctx.job_id)
            fi.send_keys('\\n'.join(ref_paths))"""

text = text.replace('            perform_robust_upload(self.driver, ref_paths, tid_int, ctx.job_id)', upload_block)

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
