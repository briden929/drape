import re

with open('v11_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_sig = 'def _click_send_button(drv):'
end_sig = 'def verify_generation_started(drv, timeout=6.0):'

start_idx = text.find(start_sig)
end_idx = text.find(end_sig)

if start_idx == -1 or end_idx == -1:
    print('Could not find send block boundaries')
    exit(1)

new_code = '''def _click_send_button(drv, tid=0, job_id=""):
    prefix = f"[T{tid}][{job_id}]" if job_id else f"[T{tid}]"
    
    root = _get_composer_root(drv, prefix)
    if not root:
        log(f"{prefix} SEND_TARGET_NOT_FOUND (no composer root)")
        return False
        
    try:
        btns = drv.execute_script("""
            var root = arguments[0];
            var cands = Array.from(root.querySelectorAll('button'));
            var res = [];
            for (var i=0; i<cands.length; i++) {
                var b = cands[i];
                if (b.offsetParent === null) continue;
                var aria = (b.getAttribute('aria-label') || '').toLowerCase();
                var testId = (b.getAttribute('data-test-id') || '').toLowerCase();
                if (aria.includes('send') || testId === 'send-button') {
                    res.push(b);
                } else if (b.querySelector('mat-icon[fonticon="arrow_upward"], mat-icon[data-mat-icon-name="arrow_upward"], mat-icon[fonticon="send"], mat-icon[data-mat-icon-name="send"]')) {
                    res.push(b);
                }
            }
            return res;
        """, root)
        
        for btn in btns:
            if btn.is_displayed() and btn.is_enabled():
                log(f"{prefix} SEND_TARGET_FOUND")
                if _exact_click(drv, btn, prefix, "SEND"):
                    return True
    except Exception as e:
        log(f"{prefix} SEND_ERROR: {e}")
        
    return False

'''

text = text[:start_idx] + new_code + text[end_idx:]

with open('v11_work.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Patched send block!')
