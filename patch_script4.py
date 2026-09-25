import re

with open('FULL_QUEUE_WORKER_V5_FINAL.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix comprehensive_login_check to always return False on sign-in pages
fix = '''def comprehensive_login_check(driver, page_name=""):
    print(f"\\n Checking login status{f' ({page_name})' if page_name else ''}...")
    url = driver.current_url.lower()
    print(f"   Current URL: {driver.current_url[:80]}")
    if 'signin' in url or 'challenge/pwd' in url or 'identifier' in url:
        print("    CONCLUSION: ON SIGN-IN PAGE -> NOT LOGGED IN")
        return False
    
    methods = ['''

content = content.replace('def comprehensive_login_check(driver, page_name=""):\n    print(f"\\n Checking login status{f\' ({page_name})\' if page_name else \'\'}...")\n    print(f"   Current URL: {driver.current_url[:80]}")\n    methods = [', fix)

with open('FULL_QUEUE_WORKER_V6_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Created V6 script.")
