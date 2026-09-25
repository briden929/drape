import sys; sys.stdout.reconfigure(encoding="utf-8")

with open('v13_clean_ast.py', 'r', encoding='utf-8') as f:
    top = f.read()

with open('v13_arch.py', 'r', encoding='utf-8') as f:
    arch = f.read()

# Filter out duplicate imports from arch if any, but python handles this fine.
# Let's combine them
final_code = top + "\n\n" + arch

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(final_code)

print("V13 FINALLY WRITTEN!")
