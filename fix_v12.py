with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V12_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('print("' + chr(10) + '================', 'print("\\n================')
text = text.replace('print("' + chr(10) + 'REDIS', 'print("\\nREDIS')
text = text.replace('print("' + chr(10) + 'GEMINI', 'print("\\nGEMINI')
text = text.replace('print("' + chr(10) + 'DOWNLOADS', 'print("\\nDOWNLOADS')
text = text.replace('print("' + chr(10) + 'WMR', 'print("\\nWMR')
text = text.replace('print("' + chr(10) + 'RESULT', 'print("\\nRESULT')
text = text.replace('FAIL={counters[\'failed\']}")\n    print("====================================================================' + chr(10) + '")', 'FAIL={counters[\'failed\']}")\n    print("====================================================================\\n")')

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V12_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)
