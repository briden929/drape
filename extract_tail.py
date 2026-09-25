with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()
with open(r"C:\Users\PC\.gemini\antigravity\scratch\entrypoint_tail.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(text.split("\n")[-150:]))
