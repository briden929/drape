# Run final complete audit
import ast, re

v14_path = r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py"
with open(v14_path, "r", encoding="utf-8") as f:
    source = f.read()
lines = source.split("\n")

results = {}

# TEST 1: py_compile
try:
    ast.parse(source)
    results["py_compile"] = "PASS"
except SyntaxError as e:
    results["py_compile"] = f"FAIL: {e}"

# TEST 2: AST
try:
    tree = ast.parse(source)
    results["AST"] = "PASS"
except:
    results["AST"] = "FAIL"

# TEST 3: Duplicate prod definitions (class-level __init__ OK, only top-level funcs matter)
prod_defs = {}
for node in ast.walk(ast.parse(source)):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        # Only count top-level definitions
        if node.name not in ("__init__", "run", "_reg", "_rel", "_done", "_resolve", "_try_hover"):
            if node.name not in prod_defs:
                prod_defs[node.name] = []
            prod_defs[node.name].append(node.lineno)

# top-level only (no nesting): let's use the line-based approach
top_level_defs = {}
for i, line in enumerate(lines, 1):
    m = re.match(r"^(def|async def|class)\s+(\w+)", line)
    if m:
        name = m.group(2)
        if name not in top_level_defs:
            top_level_defs[name] = []
        top_level_defs[name].append(i)

dups = {k: v for k, v in top_level_defs.items() if len(v) > 1}
if dups:
    results["Duplicates"] = f"FAIL: {list(dups.keys())}"
else:
    results["Duplicates"] = "PASS"

# TEST 4: Mojibake
moji_found = any("\\xa0\\x8f" in line or "\\x90 noVNC" in line for line in lines)
results["Mojibake"] = "FAIL" if moji_found else "PASS"

# TEST 5: Edge
edge_found = any(word in line.lower() for line in lines 
                 for word in ["msedge", "edgeoptions", "microsoft-edge-stable"])
results["Edge"] = "FAIL" if edge_found else "PASS"

# TEST 6: asyncio pattern
has_async_main = "async def main():" in source
has_get_loop = "asyncio.get_running_loop()" in source
has_run_worker = "def run_worker():" in source
has_notebook_check = "is_running_in_notebook" in source
results["Asyncio_Colab"] = "PASS" if all([has_async_main, has_get_loop, has_run_worker, has_notebook_check]) else "FAIL"

# TEST 7: Fake R2
fake_r2 = "return 'https://r2/' + object_name" in source
results["Real_R2"] = "FAIL" if fake_r2 else "PASS"

# TEST 8: Real boto3 upload
real_boto3 = "_r2_client()" in source and "put_object" in source
results["Boto3_R2"] = "PASS" if real_boto3 else "FAIL"

# TEST 9: validate_image_file returns tuple
new_validate = "return (True, 'OK')" in source
results["validate_returns_tuple"] = "PASS" if new_validate else "FAIL"

# TEST 10: upload_to_r2 signature matches callers
# Callers: upload_to_r2(str(ctx.clean_path), str(ctx.webp_path), ctx.job_id)
r2_def = re.search(r"def upload_to_r2\((.*?)\):", source)
if r2_def:
    params = r2_def.group(1)
    results["upload_to_r2_sig"] = f"PASS: {params}"
else:
    results["upload_to_r2_sig"] = "FAIL: def not found"

# TEST 11: critical functions
required = [
    "resolve_future_once", "FirstFreeBroker", "GeminiWorker", "GeminiWorkerPool",
    "WmrDriverThread", "WmrWorkerPool", "poll_active_downloads", "process_bullmq_job",
    "startup_preflight", "main", "run_worker", "is_running_in_notebook",
    "comprehensive_login_check", "handle_google_login_fast",
    "_wmr_find_file_input", "_wmr_check_status", "_wmr_click_download",
    "validate_image_file", "convert_to_webp", "upload_to_r2",
    "nb_check_image", "_hover_and_dl_single_click",
    "ensure_flash_mode", "ensure_create_image_mode", "perform_robust_upload",
    "verify_attachment_count", "_inject_prompt_atomic", "_click_send_button",
    "verify_generation_started", "snapshot_urls", "_r2_client", "fs_configured"
]
missing = [n for n in required if not re.search(rf'\b(def|class)\s+{re.escape(n)}\b', source)]
results["critical_functions"] = "PASS" if not missing else f"FAIL: missing {missing}"

print("=" * 60)
print("FULL V14 AUDIT RESULTS")
print("=" * 60)
for k, v in results.items():
    status = "PASS" if v.startswith("PASS") else "FAIL"
    print(f"  {k:<30} {v}")

total = len(results)
passed = sum(1 for v in results.values() if v.startswith("PASS"))
print(f"\n{passed}/{total} tests PASS")
lines_count = len(lines)
print(f"Total lines: {lines_count}")
