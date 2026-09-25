FINAL = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_FINAL.py"
ORCH = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\orchestration.py"

with open(FINAL, "a", encoding="utf-8") as f:
    with open(ORCH, "r", encoding="utf-8") as orch_f:
        f.write("\n")
        f.write(orch_f.read())
        f.write("\n")
        
print("Appended orchestration successfully.")
