import re

with open('v9_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"            # Verify clean composer first without reloading\n            if _verify_clean_composer\(drv\):\n                log\(f\"{prefix} NEW_CHAT_VERIFIED .\"\)\n                return True[\s\S]*?raise NewChatFailed\(f\"{prefix} Failed to establish new chat\"\)"

new_code = '''            # Always reload the URL to guarantee a fresh state
            drv.get(new_url)
            time.sleep(1.0)
            
            # Verify clean composer
            if _verify_clean_composer(drv):
                log(f"{prefix} NEW_CHAT_VERIFIED")
                return new_url
            
            log(f"{prefix} COMPOSER_DIRTY (attempt {attempt})")
            
        except Exception as e:
            log(f"{prefix} NEW_CHAT_ERROR: {e}")
            time.sleep(1.0)

    raise RuntimeError(f"{prefix} Failed to establish new chat")'''

new_text = re.sub(pattern, new_code, text)
if text != new_text:
    with open('v9_work.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully patched start_new_chat')
else:
    print('Regex failed to match start_new_chat')
