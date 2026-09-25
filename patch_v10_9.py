import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''def _wmr_wait_for_new_file(incoming_dir: Path, files_before: set, timeout=30) -> Path | None:
    """Wait for a new stable image file to appear in incoming_dir."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        for fn in os.listdir(incoming_dir):
            if fn.endswith(('.crdownload', '.tmp', '.part', '.download')):
                continue
            if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                continue
            if fn in files_before:
                continue
            fp = incoming_dir / fn
            try:
                if fp.stat().st_size >= DOWNLOAD_MIN_SIZE:
                    return fp
            except Exception:
                pass
        time.sleep(0.4)
    return None'''

replacement = '''def _wmr_wait_for_new_file(incoming_dir: Path, files_before: set, timeout=30) -> Path | None:
    """Wait for a new stable image file to appear in incoming_dir."""
    t0 = time.time()
    last_size = -1
    stable_checks = 0
    candidate = None
    
    while time.time() - t0 < timeout:
        if candidate is None:
            for fn in os.listdir(incoming_dir):
                if fn.endswith(('.crdownload', '.tmp', '.part', '.download')):
                    continue
                if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    continue
                if fn in files_before:
                    continue
                fp = incoming_dir / fn
                try:
                    if fp.stat().st_size >= DOWNLOAD_MIN_SIZE:
                        candidate = fp
                        break
                except Exception:
                    pass
                    
        if candidate:
            try:
                sz = candidate.stat().st_size
                if sz == last_size:
                    stable_checks += 1
                    if stable_checks >= DOWNLOAD_STABLE_CHECKS:
                        if validate_image_file(candidate):
                            return candidate
                        else:
                            # Not valid, keep looking
                            candidate = None
                            stable_checks = 0
                            last_size = -1
                else:
                    last_size = sz
                    stable_checks = 0
            except Exception:
                pass
                
        time.sleep(0.5)
    return None'''

if target in text:
    text = text.replace(target, replacement)
    with open('v10_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched wmr stable size')
else:
    print('Target not found')
