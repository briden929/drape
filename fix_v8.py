import re
import sys

src = 'FULL_QUEUE_WORKER_V8_FINAL.py'

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: The old WmrWorker methods
old_methods_pattern = r'    def _get_driver\(self, incoming_dir: str\):.*?    def quit_all\(self\):\n        for w in self.workers:\n            w.quit\(\)'
content = re.sub(old_methods_pattern, '', content, flags=re.DOTALL)

# Fix 2: Header changelog
new_header = """# V8 CHANGES:
#   • REMOVED all Edge/Microsoft Edge code entirely
#   • WMR runs in separate dedicated Google Chrome processes (W0-W3)
#   • WMR profiles in wmr_chrome_profiles/W0..W3 (separate from Gemini Chrome)
#   • WMR staging in wmr_staging/W0..W3 (fixed at launch, no CDP rebind needed)
#   • WMR canonical output in downloads/wmr/T{N}/{job_id}/ (T-slot ownership)
#   • LAZY Gemini tab creation: T0-T3 physical tabs created only when job arrives
#   • Physical Gemini tab CLOSED after DOWNLOAD_START_CONFIRMED (not after click)
#   • Exact attachment count validation (actual == expected, no >=)
#   • Download-start detection via .crdownload appearance before freeing tab
#   • Per-tab independent recovery: stuck T{N} only restarts T{N}
#   • Per-worker independent WMR recovery: stuck W{N} only restarts W{N}"""
content = re.sub(r'# V4 CHANGES vs V3:.*?requirements implemented', new_header, content, flags=re.DOTALL)

# Fix 3: _enqueue_edge_wmr
content = content.replace("_enqueue_edge_wmr", "_enqueue_wmr")

with open(src, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixes applied to V8.")
