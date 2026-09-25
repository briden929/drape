# Read google login.py for login reference
with open(r"C:\Users\PC\Downloads\google login.py", "r", encoding="utf-8", errors="replace") as f:
    src = f.read()
# Print first 200 lines
lines = src.split("\n")
for i, line in enumerate(lines[:100], 1):
    print(f"{i}: {line}")
