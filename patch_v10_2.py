import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''            # 4-7. Upload reference files (Robust State Machine)
            ref_paths = [str(Path(p).resolve()) for p in info["refs"] if p and os.path.exists(p)]
            expected_count = len(ref_paths)
            if expected_count > 0:
                try:
                    perform_robust_upload(chrome_driver, ref_paths, tid, job_id)
                except Exception as e:
                    _recover_stuck_tab(tid, f"SUBMISSION_EXCEPTION: {e}")
                    return'''

replacement = '''            # 4-7. Upload reference files (Robust State Machine)
            # 7. INVALID REFERENCE PATHS: Every expected reference must exist before browser submission.
            expected_refs = [p for p in info["refs"] if p]
            ref_paths = []
            for p in expected_refs:
                rp = str(Path(p).resolve())
                if not os.path.exists(rp):
                    _recover_stuck_tab(tid, f"UPLOAD_FAILED: Missing reference file {rp}")
                    return
                ref_paths.append(rp)
                
            expected_count = len(ref_paths)
            if expected_count > 0:
                try:
                    perform_robust_upload(chrome_driver, ref_paths, tid, job_id)
                except Exception as e:
                    _recover_stuck_tab(tid, f"SUBMISSION_EXCEPTION: {e}")
                    return'''

if target in text:
    text = text.replace(target, replacement)
    with open('v10_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched reference paths logic')
else:
    print('Target not found')
