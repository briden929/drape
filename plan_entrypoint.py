# Full V14 entrypoint rewrite - dual mode
import re, ast

v14_path = r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py"
with open(v14_path, "r", encoding="utf-8") as f:
    source = f.read()

# 1. Find startup_preflight and verify it is present
has_preflight = "def startup_preflight" in source
print(f"startup_preflight present: {has_preflight}")

# 2. Find the main() function signature
main_start = source.find("async def main():")
print(f"main() at char {main_start}")

# 3. Identify what we are replacing (is_running_in_notebook + run_worker + if __name__)
# The tail of the file (last ~30 lines)
lines = source.split("\n")
for i, line in enumerate(lines[-35:], len(lines)-35+1):
    print(f"L{i}: {line}")
