import os
import ast

with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()
    print("Length:", len(text))
    print("Ends with:", text[-100:])
