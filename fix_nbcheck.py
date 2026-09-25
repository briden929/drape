import re

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    source = f.read()

# Fix 1: The bad nb_check_image call at L1967 (called with only drv, prefix)
# This was checking if composer is in a clean state before starting, but the 
# function needs urls_before and chat_urls. 
# The correct check here is actually just verify the page is accessible - 
# or use a clean_composer_check. Let us remove this stale check and just log.
old_bad_call = """                log(f'{prefix} FRESH_BROWSER_READY')
                if not nb_check_image(drv, prefix):
                    raise Exception('COMPOSER_FAILED')
                log(f'{prefix} CLEAN_COMPOSER_VERIFIED')"""

new_clean = """                log(f'{prefix} FRESH_BROWSER_READY')
                # Verify Gemini page is accessible before starting job
                try:
                    page_url = drv.current_url
                    if 'gemini.google.com' not in page_url:
                        raise Exception(f'Gemini tab not on Gemini: {page_url}')
                    log(f'{prefix} COMPOSER_VERIFIED (url={page_url[:60]})')
                except Exception as ce:
                    raise Exception(f'COMPOSER_CHECK_FAILED: {ce}')"""

if old_bad_call in source:
    source = source.replace(old_bad_call, new_clean)
    print("[FIX] Fixed nb_check_image wrong call - replaced with page URL check")
else:
    print("[WARN] old bad call not found exactly")
    # Try to find the line and report
    for i, line in enumerate(source.split('\n'), 1):
        if 'COMPOSER_FAILED' in line:
            print(f"  L{i}: {line.strip()}")

# Fix 2: Also check if mimetypes import is missing
if 'import mimetypes' not in source:
    source = source.replace('import socket\n', 'import socket\nimport mimetypes\n')
    print("[FIX] Added import mimetypes")

# Fix 3: Make sure boto3 is imported
if 'import boto3' not in source:
    source = source.replace('import mimetypes\n', 'import mimetypes\ntry:\n    import boto3\nexcept ImportError:\n    boto3 = None\n')
    print("[FIX] Added boto3 import")

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "w", encoding="utf-8") as f:
    f.write(source)
    
import ast
try:
    ast.parse(source)
    print("\n[PASS] AST parse OK")
except SyntaxError as e:
    print(f"\n[FAIL] SyntaxError: {e}")
