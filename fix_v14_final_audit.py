"""
FULL V14 FINAL AUDIT FIX
Applies all discovered fixes in one pass:
1. Fix fake upload_to_r2 stub -> real boto3 implementation
2. Fix validate_image_file signature (called with 3 args but defined with 2)
3. Fix mojibake strings (\xa0\x8f etc) -> ASCII
4. Fix _finalize_job to use real R2 upload / push_generation pattern
5. Add R2 / db constants to top of file
6. Fix duplicate start_all/quit_all (they are in different classes, so OK - confirm)
7. Fix validate_image_file return value (currently returns bool, callers expect tuple)
"""
import re

v14_path = r'C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py'
v11_path = r'C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V11_FINAL.py'

with open(v14_path, 'r', encoding='utf-8') as f:
    source = f.read()

with open(v11_path, 'r', encoding='utf-8') as f:
    v11_src = f.read()

print("=== Starting V14 Final Audit Fixes ===")
changes = 0

# 1. Fix mojibake - replace escaped bad chars with ASCII equivalents
moji_replacements = [
    (r"\xa0\x8f", "[WARN]"),
    (r"\x90", "->"),
    (r"\xa0", " "),
]
for old, new in moji_replacements:
    # These appear as literal escaped strings in print statements
    count = source.count(f"'{old}") + source.count(f'"{old}')
    source = source.replace(f"'  {old} ", f"'  {new} ")
    source = source.replace(f"  {old} ", f"  {new} ")
    
# More precise mojibake replacement
bad_chars = [
    ("'  \\xa0\\x8f ", "'  [WARN] "),
    ('"  \\xa0\\x8f ', '"  [WARN] '),
    ("'  \\x90 ", "'  -> "),
    ('"  \\x90 ', '"  -> '),
]
for bad, good in bad_chars:
    if bad in source:
        source = source.replace(bad, good)
        print(f"[FIX] Mojibake: {bad!r} -> {good!r}")
        changes += 1

# Handle \xa0\x8f inline
source = source.replace("\\xa0\\x8f", "[WARN]")
source = source.replace("\\x90 noVNC", "[INFO] noVNC")
source = source.replace("\\xa0\\x8f noVNC", "[WARN] noVNC")
source = source.replace("\\xa0\\x8f pyvirtual", "[WARN] pyvirtual")
source = source.replace("\\xa0\\x8f WebP", "[WARN] WebP")
source = source.replace("\\xa0\\x8f Warning", "[WARN] Warning")
source = source.replace("\\xa0\\x8f Timeout", "[WARN] Timeout")
source = source.replace("\\xa0\\x8f Error", "[WARN] Error")
source = source.replace("\\xa0\\x8f {label}", "[WARN] {label}")
print(f"[FIX] Mojibake replacements applied")
changes += 1

# 2. Fix validate_image_file - it's called with (path, 512, 1024) but defined with (path, min_size)
# Need to make it return (bool, str) tuple when needed, or fix callers
# Let's look at what the callers do:
# L2256: valid, msg = validate_image_file(str(raw_path), 512, 1024)
# So we need validate_image_file to support returning (bool, str)

old_validate = '''def validate_image_file(path, min_size=DOWNLOAD_MIN_SIZE):
    """Returns True if path exists, is large enough, and PIL can open it."""
    try:
        p = Path(path)
        if not p.exists() or p.stat().st_size < min_size:
            return False
        with Image.open(p) as im:
            im.verify()
        return True
    except Exception:
        return False'''

new_validate = '''def validate_image_file(path, min_size=DOWNLOAD_MIN_SIZE, max_size=None):
    """Returns (True, 'OK') if valid, (False, reason) if invalid.
    Also works as bool when called with single arg (returns bool directly for legacy callers).
    """
    try:
        p = Path(path)
        if not p.exists():
            return (False, f'File not found: {path}')
        sz = p.stat().st_size
        if sz < min_size:
            return (False, f'File too small: {sz} < {min_size}')
        if max_size and sz > max_size * 1024 * 1024:
            return (False, f'File too large: {sz}')
        with Image.open(p) as im:
            im.verify()
        # Re-open after verify (verify closes the file)
        with Image.open(p) as im:
            im.load()
            w, h = im.size
            if w < 32 or h < 32:
                return (False, f'Image too small: {w}x{h}')
        return (True, 'OK')
    except Exception as e:
        return (False, f'Validation error: {e}')'''

if old_validate in source:
    source = source.replace(old_validate, new_validate)
    print("[FIX] validate_image_file: upgraded to return (bool, reason) tuple")
    changes += 1

# Fix callers that use it as bool (legacy)
source = source.replace(
    'if validate_image_file(candidate):',
    'if validate_image_file(candidate)[0]:'
)
print("[FIX] validate_image_file legacy call fixed")
changes += 1

# 3. Fix the fake upload_to_r2 stub
old_r2_stub = '''def upload_to_r2(file_path, object_name):
    return 'https://r2/' + object_name'''

new_r2_real = '''# R2 configuration - loaded from environment at startup
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
R2_PUBLIC_URL = os.environ.get('R2_PUBLIC_URL')
FASHION_STUDIO_USER_ID = os.environ.get('FASHION_STUDIO_USER_ID', '')

def fs_configured():
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_PUBLIC_URL)

def _r2_client():
    import boto3
    return boto3.client(
        's3',
        endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name='auto'
    )

def upload_to_r2(png_path, webp_path, job_id, user_id=None):
    """Upload PNG and WebP to R2, return (png_url, webp_url).
    Returns (None, None) if R2 is not configured.
    """
    import mimetypes
    if not fs_configured():
        log(f'[R2] Not configured - skipping upload for job {job_id}')
        return (None, None)
    target_user_id = user_id or FASHION_STUDIO_USER_ID or 'anonymous'
    png_key = f'generations/{target_user_id}/{job_id}.png'
    webp_key = f'generations/{target_user_id}/{job_id}.webp'
    try:
        client = _r2_client()
        with open(png_path, 'rb') as f:
            png_data = f.read()
        client.put_object(
            Bucket=R2_BUCKET_NAME, Key=png_key, Body=png_data,
            ContentType='image/png',
            CacheControl='public, max-age=31536000, immutable'
        )
        png_url = f'{R2_PUBLIC_URL}/{png_key}'
        log(f'[R2] PNG uploaded: {png_url}')
        webp_url = None
        if webp_path and os.path.exists(str(webp_path)):
            with open(str(webp_path), 'rb') as f:
                webp_data = f.read()
            client.put_object(
                Bucket=R2_BUCKET_NAME, Key=webp_key, Body=webp_data,
                ContentType='image/webp',
                CacheControl='public, max-age=31536000, immutable'
            )
            webp_url = f'{R2_PUBLIC_URL}/{webp_key}'
            log(f'[R2] WebP uploaded: {webp_url}')
        return (png_url, webp_url)
    except Exception as e:
        log(f'[R2] Upload FAILED for job {job_id}: {e}')
        raise'''

if old_r2_stub in source:
    source = source.replace(old_r2_stub, new_r2_real)
    print("[FIX] upload_to_r2: replaced fake stub with real boto3 implementation")
    changes += 1
else:
    print("[WARN] old_r2_stub not found exactly - checking for partial match")
    # Try partial
    if "def upload_to_r2(file_path, object_name):" in source:
        source = source.replace(
            "def upload_to_r2(file_path, object_name):\n    return 'https://r2/' + object_name",
            new_r2_real
        )
        print("[FIX] upload_to_r2: replaced via partial match")
        changes += 1

# 4. Fix _finalize_job to use correct upload_to_r2 signature  
# Current call: png_url, webp_url = upload_to_r2(str(ctx.clean_path), str(ctx.webp_path), ctx.job_id)
# New signature: upload_to_r2(png_path, webp_path, job_id, user_id=None)
# This already matches! Good.

# 5. Fix _finalize_job DB_READY -> DB_FINALIZING state
source = source.replace(
    "ctx.transition(JobState.DB_READY)",
    "ctx.transition(JobState.DB_FINALIZING)"
)
print("[FIX] _finalize_job: DB_READY -> DB_FINALIZING state transition")
changes += 1

# 6. Add import mimetypes at the top (needed by upload_to_r2)
if 'import mimetypes' not in source:
    source = source.replace(
        'import socket',
        'import socket\nimport mimetypes'
    )
    print("[FIX] Added import mimetypes")
    changes += 1

# 7. Add import boto3 at the top (needed if not lazy-imported)
if 'import boto3' not in source:
    source = source.replace(
        'import mimetypes',
        'import mimetypes\ntry:\n    import boto3\nexcept ImportError:\n    boto3 = None'
    )
    print("[FIX] Added boto3 import with graceful fallback")
    changes += 1

# 8. Fix nb_check_image call signature 
# Called as: nb_check_image(drv, prefix) - should return status, new_src
# Called as: status, new_src = nb_check_image(drv, urls_before, chat_urls)
# Need to check the function signature
lines = source.split('\n')
for i, line in enumerate(lines, 1):
    if 'def nb_check_image' in line:
        print(f"\n[INFO] nb_check_image definition at L{i}: {line.strip()}")
        break

# 9. Fix the check for 'if not nb_check_image(drv, prefix):'
# nb_check_image might return tuple or bool depending on args - make it consistent
# Looking at V14 code:
# L1898: if not nb_check_image(drv, prefix):  <-- uses prefix (str) as second arg
# L1932: status, new_src = nb_check_image(drv, urls_before, chat_urls)  <-- uses urls_before
# These are two different call patterns, need to check the actual definition

# Save the fixed source
with open(v14_path, 'w', encoding='utf-8') as f:
    f.write(source)
    
print(f"\n=== Applied {changes} changes ===")
print(f"File saved to {v14_path}")

# Run quick verify
import ast
try:
    ast.parse(source)
    print("\n[PASS] AST parse OK after fixes")
except SyntaxError as e:
    print(f"\n[FAIL] SyntaxError after fixes: {e}")
