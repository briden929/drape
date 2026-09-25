import json
with open('v13_classes.json', 'r', encoding='utf-8') as f:
    classes = json.load(f)
print("--- GeminiWorker ---")
print(classes['GeminiWorker'])
