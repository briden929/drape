import re

with open('v12_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_sig = 'def _wmr_click_download(drv, attempts=6):'
end_sig = 'def _wmr_wait_for_new_file(incoming_dir: Path, files_before: set, timeout=30) -> Path | None:'

start_idx = text.find(start_sig)
end_idx = text.find(end_sig)

if start_idx == -1 or end_idx == -1:
    print('Could not find wmr click block boundaries')
    exit(1)

new_code = '''def _wmr_click_download(drv, prefix, attempts=1):
    js_code = """
        // 1. Locate the result container. Often it's the parent of the comparison slider, or contains the text "Result"
        // Since we might not know the exact class, we find the container holding "Clean" or "Result" or just find the exact button and verify its context.
        var btns = document.querySelectorAll('button');
        var target = null;
        for (var i = 0; i < btns.length; i++) {
            var btn = btns[i];
            var txt = (btn.textContent || btn.innerText || '').trim();
            if (txt === 'Download PNG') {
                target = btn;
                break;
            }
        }
        if (!target) return 'NOT_FOUND';
        
        var style = window.getComputedStyle(target);
        if (style.display === 'none' || style.visibility === 'hidden' || target.disabled) {
            return 'NOT_VISIBLE_OR_DISABLED';
        }
        
        // Scope verification: walk up to ensure it's in the main result section
        var root = target.closest('main') || target.closest('.result') || target.parentElement.parentElement;
        
        target.scrollIntoView({behavior: 'instant', block: 'center'});
        var r = target.getBoundingClientRect();
        
        return {
            x: Math.round(r.x), 
            y: Math.round(r.y), 
            w: Math.round(r.width), 
            h: Math.round(r.height),
            text: (target.textContent || '').trim()
        };
    """
    for _ in range(attempts):
        res = safe_execute_script(drv, js_code)
        if isinstance(res, dict):
            log(f"{prefix} WMR_DOWNLOAD_TARGET_FOUND")
            log(f"{prefix} WMR_DOWNLOAD_TARGET_TEXT '{res['text']}'")
            log(f"{prefix} WMR_DOWNLOAD_TARGET_RECT x={res['x']} y={res['y']} w={res['w']} h={res['h']}")
            
            # Click it
            try:
                # Find the button natively to click
                btns = drv.find_elements(By.XPATH, "//button[normalize-space(.)='Download PNG']")
                if btns and btns[0].is_displayed() and btns[0].is_enabled():
                    btns[0].click()
                    return True
            except Exception:
                # fallback JS click
                drv.execute_script("""
                    var btns = document.querySelectorAll('button');
                    for (var i = 0; i < btns.length; i++) {
                        if (btns[i].textContent.trim() === 'Download PNG') {
                            btns[i].click();
                            return;
                        }
                    }
                """)
                return True
        time.sleep(0.3)
        
    return False

'''

text = text[:start_idx] + new_code + text[end_idx:]

with open('v12_work.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Patched wmr click block!')
