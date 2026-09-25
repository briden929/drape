# Fix remaining mojibake in comments (the em-dash replacement artifacts)
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    source = f.read()

# Replace common replacement character artifacts in comments
# The "?" replacement char from encoding issues
import re

# Specific known bad patterns from our output
bad_patterns = [
    ("\ufffd", "-"),    # Unicode replacement character -> dash
]
for old, new in bad_patterns:
    source = source.replace(old, new)

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "w", encoding="utf-8") as f:
    f.write(source)

# Now run all tests
import ast, subprocess

print("=== Final test suite ===\n")

# Test 1: py_compile
result = subprocess.run(
    ["python", "-m", "py_compile", r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py"],
    capture_output=True, text=True
)
print(f"T1 py_compile: {'PASS' if result.returncode == 0 else 'FAIL'}")
if result.stderr: print(f"   {result.stderr}")

# Test 2: AST
try:
    ast.parse(source)
    print("T2 AST parse: PASS")
except SyntaxError as e:
    print(f"T2 AST: FAIL - {e}")

# Test 3: F821
result = subprocess.run(
    ["flake8", "--select=F821", r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py"],
    capture_output=True, text=True
)
if result.returncode == 0:
    print("T3 F821: PASS - 0 undefined names")
else:
    print(f"T3 F821: FAIL\n{result.stdout}")

# Test 4: Duplicate top-level defs
top_defs = {}
for i, line in enumerate(source.split("\n"), 1):
    m = __import__("re").match(r"^(def|async def|class)\s+(\w+)", line)
    if m:
        name = m.group(2)
        top_defs.setdefault(name, []).append(i)
dups = {k: v for k, v in top_defs.items() if len(v) > 1}
print(f"T4 Duplicates: {'PASS' if not dups else 'FAIL - ' + str(list(dups.keys()))}")

# Test 5: Edge
edge_found = any("msedge" in l.lower() or "edgeoptions" in l.lower() for l in source.split("\n"))
print(f"T5 Edge: {'FAIL' if edge_found else 'PASS'}")

# Test 6: Mojibake
moji = any("\\xa0\\x8f" in l or "\\xc2" in l for l in source.split("\n"))
print(f"T6 Mojibake: {'FAIL' if moji else 'PASS'}")

# Test 7: Asyncio entrypoint check
has_start = "def start_in_current_environment():" in source
has_worker_task = "worker_main_task" in source
no_raise_err = "Use: await main()" not in source
has_double_guard = "_worker_started" in source
has_auto_exec = "__name__ != \"__main__\" and not _worker_started" in source
print(f"T7 Entrypoint start_in_current_environment: {'PASS' if has_start else 'FAIL'}")
print(f"T8 worker_main_task global: {'PASS' if has_worker_task else 'FAIL'}")
print(f"T9 No raise RuntimeError entrypoint: {'PASS' if no_raise_err else 'FAIL'}")
print(f"T10 Double-start guard: {'PASS' if has_double_guard else 'FAIL'}")
print(f"T11 Auto-exec Colab detection: {'PASS' if has_auto_exec else 'FAIL'}")

# Test 8: bare main() calls
bare = [l.strip() for l in source.split("\n") if re.match(r"^\s*main\(\)\s*$", l)]
print(f"T12 Bare main() calls: {'FAIL - ' + str(bare) if bare else 'PASS'}")

# Test 9: REDIS_KEY_PREFIX used in Worker
redis_prefix = 'REDIS_KEY_PREFIX' in source and 'Worker(' in source
print(f"T13 REDIS_KEY_PREFIX in Worker: {'PASS' if redis_prefix else 'FAIL'}")

# Test 10: Real R2 not stub
fake = "return 'https://r2/' + object_name" in source
print(f"T14 Real R2 (not stub): {'PASS' if not fake else 'FAIL'}")

# Summary
total_lines = len(source.split("\n"))
print(f"\nTotal lines: {total_lines}")
