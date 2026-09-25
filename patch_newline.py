with open("FULL_QUEUE_WORKER_FINAL_V16_PREP.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('print("\n============================================================")', 'print("\\n============================================================")')
text = text.replace('print("DISPLAY = OK\n")', 'print("DISPLAY = OK\\n")')

# Wait, the error shows that the string was ACTUALLY split:
# print("
# ============================================================")
# Because python evaluated `\n` in `"""` string.
# So I should find `print("` followed by newline followed by `==="`
import re
text = re.sub(r'print\("\n=+', r'print("\\n============================================================"', text)
text = re.sub(r'print\("DISPLAY = OK\n"\)', r'print("DISPLAY = OK\\n")', text)

with open("FULL_QUEUE_WORKER_FINAL_V16_PREP.py", "w", encoding="utf-8") as f:
    f.write(text)
