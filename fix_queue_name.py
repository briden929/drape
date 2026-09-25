with open('v13_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('job_queue.qsize()', 'GEMINI_ADMISSION_Q.qsize()')
text = text.replace('WMR_QUEUE={job_queue.qsize()}', 'GEMINI_ADMISSION={GEMINI_ADMISSION_Q.qsize()}')
with open('v13_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Fixed queue name in dashboard")
