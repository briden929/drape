# Unicode arrow in comment - need to fix that
import re
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    source = f.read()

# Find and fix non-ASCII chars in comments/strings that are not intentional
# The arrow u+2192 is in a comment, replace it
source = source.replace("\u2192", "->")
source = source.replace("\u2714", "[OK]")
source = source.replace("\u2705", "[OK]")
source = source.replace("\u26a0", "[WARN]")
source = source.replace("\u274c", "[FAIL]")
source = source.replace("\u2728", "*")
source = source.replace("\u2795", "+")

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "w", encoding="utf-8") as f:
    f.write(source)

import ast
try:
    ast.parse(source)
    print("PASS AST ok")
except SyntaxError as e:
    print(f"FAIL {e}")

# Check the end of file
lines = source.split("\n")
print(f"\nTotal lines: {len(lines)}")
print("\n=== Last 15 lines ===")
for i, line in enumerate(lines[-15:], len(lines)-15+1):
    print(f"L{i}: {line}")
