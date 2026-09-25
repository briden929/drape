import re

with open('FULL_QUEUE_WORKER_V5_FINAL.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix comprehensive_login_check to always return False on sign-in pages
fix = '''def comprehensive_login_check(driver, page_name=""):
    url = driver.current_url.lower()
    if 'signin' in url or 'challenge/pwd' in url or 'identifier' in url:
        print("    CONCLUSION: ON SIGN-IN PAGE -> NOT LOGGED IN")
        return False
'''

# We will inject this at the very beginning of the function
content = re.sub(
    r'def comprehensive_login_check\(driver, page_name=""\):',
    fix,
    content
)

with open('FULL_QUEUE_WORKER_V6_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Created V6 script.")
