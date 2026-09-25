# Full forensic audit of V14
import ast
import re

v14_path = r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py"
with open(v14_path, 'r', encoding='utf-8', errors='replace') as f:
    source = f.read()

# 1. Python syntax check  
print("=== TEST 1: py_compile ===")
try:
    ast.parse(source)
    print("PASS - AST parse OK")
except SyntaxError as e:
    print(f"FAIL - SyntaxError: {e}")

# 2. Mojibake scan
print("\n=== TEST 2: Mojibake scan ===")
moji_patterns = ['\xa0\x8f', '\xc2\xa0', '\xc2\x8f', '\xc3\xa2', '\xc3\x90', 
                  'â', 'ð', 'Â', '\ufffd']
lines = source.split('\n')
moji_found = []
for i, line in enumerate(lines, 1):
    for pat in moji_patterns:
        if pat in line:
            moji_found.append(f"L{i}: {line.strip()[:80]}")
            break

if moji_found:
    print(f"FAIL - {len(moji_found)} mojibake lines found:")
    for m in moji_found[:20]:
        print(f"  {m}")
else:
    print("PASS - No mojibake found")

# 3. Edge references
print("\n=== TEST 3: Edge scan ===")
edge_patterns = ['msedge', 'EdgeOptions', 'microsoft-edge', 'edgedriver']
edge_found = []
for i, line in enumerate(lines, 1):
    for pat in edge_patterns:
        if pat.lower() in line.lower():
            edge_found.append(f"L{i}: {line.strip()[:80]}")
            break
if edge_found:
    print(f"FAIL - Edge references found:")
    for e in edge_found:
        print(f"  {e}")
else:
    print("PASS - No Edge references")

# 4. Duplicate function definitions
print("\n=== TEST 4: Duplicate definitions ===")
tree = ast.parse(source)
defs = {}
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        name = node.name
        if name not in defs:
            defs[name] = []
        defs[name].append(node.lineno)
dups = {k: v for k, v in defs.items() if len(v) > 1}
if dups:
    print(f"FAIL - Duplicate definitions:")
    for k, v in dups.items():
        print(f"  {k} at lines {v}")
else:
    print("PASS - No duplicate definitions")

# 5. Check asyncio main
print("\n=== TEST 5: asyncio/Colab pattern ===")
has_run = 'asyncio.run(main())' in source
has_await_main = 'async def main():' in source
has_get_running = 'asyncio.get_running_loop()' in source
has_run_worker = 'def run_worker():' in source
has_is_notebook = 'is_running_in_notebook' in source

print(f"  asyncio.run(main()) at top-level: {has_run}")
print(f"  async def main(): {has_await_main}")
print(f"  asyncio.get_running_loop() in main: {has_get_running}")
print(f"  def run_worker(): {has_run_worker}")
print(f"  is_running_in_notebook(): {has_is_notebook}")

if has_await_main and has_get_running and has_run_worker and has_is_notebook:
    print("PASS - Correct dual-mode asyncio pattern")
else:
    print("FAIL - Asyncio pattern needs fixing")

# 6. Tuple unpacking
print("\n=== TEST 6: Tuple unpacking ===")
bad_calls = []
for i, line in enumerate(lines, 1):
    # Look for single assignment to get_chrome_job_dir or get_wmr_job_dir
    if re.search(r'^\s+\w+\s*=\s*(get_chrome_job_dir|get_wmr_job_dir)\(', line):
        bad_calls.append(f"L{i}: {line.strip()[:80]}")
    
if bad_calls:
    print(f"FAIL - Incorrect single assignments (missing tuple unpack):")
    for b in bad_calls:
        print(f"  {b}")
else:
    print("PASS - All job dir calls properly unpacked (or none found)")

# 7. Check key function definitions
print("\n=== TEST 7: Critical function presence ===")
required = ['resolve_future_once', 'FirstFreeBroker', 'GeminiWorker', 
            'GeminiWorkerPool', 'WmrDriverThread', 'WmrWorkerPool',
            'poll_active_downloads', 'process_job_pipeline', 'process_bullmq_job',
            'startup_preflight', 'main', 'run_worker', 'is_running_in_notebook',
            'comprehensive_login_check', 'handle_google_login_fast',
            '_wmr_find_file_input', '_wmr_check_status', '_wmr_click_download',
            'validate_image_file', 'convert_to_webp', 'upload_to_r2',
            'nb_check_image', '_hover_and_dl_single_click',
            'ensure_flash_mode', 'ensure_create_image_mode', 'perform_robust_upload',
            'verify_attachment_count', '_inject_prompt_atomic', '_click_send_button',
            'verify_generation_started', 'snapshot_urls']
            
missing = []
for name in required:
    if not re.search(rf'\b(def|class)\s+{re.escape(name)}\b', source):
        missing.append(name)
        
if missing:
    print(f"FAIL - Missing functions/classes: {missing}")
else:
    print(f"PASS - All {len(required)} required functions present")

# 8. Check REDIS_TUNNEL_URL in main
print("\n=== TEST 8: Redis config ===")
if "os.environ.get('REDIS_TUNNEL_URL')" in source or 'os.environ.get("REDIS_TUNNEL_URL")' in source:
    print("PASS - REDIS_TUNNEL_URL from env")
else:
    print("FAIL - REDIS_TUNNEL_URL not from env")

# Count total lines
total_lines = len(lines)
print(f"\n=== Summary: {total_lines} lines total ===")
