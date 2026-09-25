import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\PC\Downloads\FULL_QUEUE_WORKER_V11.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

lines = code.split("\n")
print(f"Total lines: {len(lines)}")
print(f"File size: {len(code)} chars")

funcs = [
    "_get_composer_root", "_verify_element_ownership",
    "_detect_wrong_sidebar_menu", "_safe_click_element",
    "click_plus_button", "open_upload_drawer",
    "click_upload_files_in_drawer", "_click_upload_files_fallback",
    "_click_send_button", "perform_robust_upload", "_log_target_rect",
]
for n in funcs:
    found = any(f"def {n}" in l for l in lines)
    print(f"  {'✅' if found else '❌'} {n}")

# Verify no global button search in click_plus_button
cp_start = code.find("def click_plus_button")
cp_end = code.find("def is_create_image_mode", cp_start)
cp_section = code[cp_start:cp_end] if cp_start >= 0 and cp_end >= 0 else ""
has_global = "querySelectorAll('button')" in cp_section
print(f"\n  click_plus_button has global button search: {'YES (BAD)' if has_global else 'NO (GOOD)'}")

# Check call sites
print(f"  click_plus_button(drv, tid, job_id) calls: {code.count('click_plus_button(drv, tid, job_id)')}")
print(f"  _click_send_button(chrome_driver, tid, job_id) calls: {code.count('_click_send_button(chrome_driver, tid, job_id)')}")
print(f"  open_upload_drawer(drv, tid, job_id) calls: {code.count('open_upload_drawer(drv, tid, job_id)')}")
print(f"  click_upload_files_in_drawer(drv, tid, job_id) calls: {code.count('click_upload_files_in_drawer(drv, tid, job_id)')}")

# Verify V11 header
print(f"\n  V11 header present: {'V11' in code[:2000]}")
print(f"  Version is v11: {'v11.0' in code[:2000] or 'QUEUE WORKER v11.0' in code[:2000]}")
