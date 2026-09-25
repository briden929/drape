import json
v13 = json.load(open('v13_syms.json', 'r', encoding='utf-8'))
print(v13.get('FirstFreeBroker', 'Not found'))
