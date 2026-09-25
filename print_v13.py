import json
v13 = json.load(open('v13_syms.json', 'r', encoding='utf-8'))
print([k for k in v13.keys() if k not in ['FirstFreeBroker', 'GeminiWorker', 'JobContext']])
