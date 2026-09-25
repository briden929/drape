import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''            # Verify clean composer first without reloading
            if _verify_clean_composer(drv):
                log(f"{prefix} NEW_CHAT_VERIFIED ✅")
                return True
                
            # If not clean, reload the exact new URL for a clean state
            log(f"{prefix} COMPOSER NOT CLEAN — RELOADING")'''

replacement = '''            # Always reload the exact new URL to guarantee a clean state
            log(f"{prefix} RELOADING NEW CHAT URL")'''

if target in text:
    text = text.replace(target, replacement)
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched NEW_CHAT_VERIFIED')
else:
    print('Target not found')
