import re
import sys

src = 'FULL_QUEUE_WORKER_V8_FINAL.py'
dst = 'FULL_QUEUE_WORKER_V8_FINAL.py'

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: The header changelog
old_header = """# V4 CHANGES vs V3:
#   • open_new_chat_and_reload(): URL-verified new chat + confirmation dialog
#   • WmrWorkerPool: 4 independent Edge drivers, each with own profile/dir
#   • Job-specific directories: chrome/T{N}/{job_id}/incoming/, edge/, final_output/
#   • Download watcher scans ONLY job-specific incoming/ dir (no broad fallback)
#   • Hover-click is PRIMARY download method; CDP is fallback after 15s
#   • _free_tab() never touches active_downloads — full resource separation
#   • _recover_stuck_tab() per-tab only, supports requeue with retry budget
#   • File input missing = hard stop (no silent continue)
#   • Finalization: Edge PNG → final_output → WebP → R2 → DB → Credits
#   • All 49 architecture requirements implemented"""

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

if old_header in content:
    content = content.replace(old_header, new_header)
else:
    content = re.sub(r'# V4 CHANGES vs V3:.*?requirements implemented', new_header, content, flags=re.DOTALL)

# Fix 2: Remove the entire WmrWorker and WmrWorkerPool and edge_pool initialization
# BUT, we might already have the new class! If we just ran patch_v8.py, it inserted the new class but left the old methods.
# The cleanest way: let's do this from V7 as base and do BOTH scripts properly.
