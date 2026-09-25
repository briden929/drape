# coding: utf-8
with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("ipy.run_cell(\"task = start_worker()\nawait task\")", "ipy.run_cell(\"task = start_worker()\\nawait task\")")

with open("FULL_QUEUE_WORKER_FINAL.py", "w", encoding="utf-8") as f:
    f.write(text)
