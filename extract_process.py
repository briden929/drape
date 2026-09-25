import re

with open('v13_base.py', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'    def _process_job\(self, item\):(.*?)(?=    def quit\(self\):)', text, re.DOTALL)
if m:
    with open('v13_gemini_process.py', 'w', encoding='utf-8') as f:
        f.write("def _process_job(self, item):" + m.group(1))
