with open("FULL_QUEUE_WORKER_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
print("Length:", len(text))
# Let's find imports
print("IMPORTS:", text.find("from bullmq import Worker"))
m = re.search(r'from bullmq import .*', text)
if m: print(m.group(0))

# Let's find main
m = re.search(r'async def main\(\):', text)
if m: print("main:", m.start())

# Let's find start_worker / Colab block
m = re.search(r'def start_worker', text)
if m: print("start_worker:", m.start())
m = re.search(r'if __name__ == .__main__.:', text)
if m: print("if __name__:", m.start())
