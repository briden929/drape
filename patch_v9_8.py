import re

with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"                # Wait for download to actually START \(\.crdownload or image file\)\n                dl_confirmed = False\n                t_dl_start = time.time\(\)\n                while time.time\(\) - t_dl_start < DOWNLOAD_START_WINDOW_S:[\s\S]*?info\[\"state\"\] = S_IDLE\n                        _free_tab\(tid\)\n                        continue"

new_code = '''                # Change state to wait for download start asynchronously
                info["t_dl_start"] = time.time()
                info["dl_confirmed"] = False
                info["cdp_ok"] = cdp_ok
                info["state"] = "DOWNLOAD_START_WAITING"
                info["incoming_dir"] = incoming_dir
                info["files_before"] = files_before
                # release lock and continue to next tab
                continue
                
        # Outside lock (or if state is already DOWNLOAD_START_WAITING)
        if info["state"] == "DOWNLOAD_START_WAITING":
            job_id = info["job_id"]
            prefix = f"[T{tid}][{job_id}]"
            incoming_dir = info["incoming_dir"]
            files_before = info["files_before"]
            cdp_ok = info.get("cdp_ok", False)
            
            dl_confirmed = False
            if incoming_dir.exists():
                cur_files = set(os.listdir(incoming_dir))
                new_files = cur_files - files_before
                if any(
                    fn.endswith('.crdownload') or
                    fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                    for fn in new_files
                ):
                    dl_confirmed = True

            if dl_confirmed or cdp_ok:
                if dl_confirmed:
                    log(f"{prefix} DOWNLOAD_START_CONFIRMED")
                
                # NOW close the physical Gemini tab — download is confirmed
                async with chrome_lock:
                    try:
                        chrome_driver.switch_to.window(info["handle"])
                        chrome_driver.close()
                    except Exception:
                        pass
                info["handle"] = None
                info["state"] = S_IDLE
                _free_tab(tid)
                continue
                
            # If still waiting and timeout exceeded
            if time.time() - info["t_dl_start"] > DOWNLOAD_START_WINDOW_S:
                log(f"{prefix} DOWNLOAD_START_FAILED — Waited {DOWNLOAD_START_WINDOW_S}s for .crdownload")
                _recover_stuck_tab(tid, "DOWNLOAD_START_TIMEOUT")
                continue'''

new_text = re.sub(pattern, new_code, text)
if text != new_text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched poll_active_tabs download start logic')
else:
    print('Regex failed')
