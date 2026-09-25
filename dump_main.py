with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    lines = f.read().split("\n")
with open(r"C:\Users\PC\.gemini\antigravity\scratch\main_body.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines[2548:]))
