import re

with open('v13_base.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add loggingPrefs to driver factory
if 'goog:loggingPrefs' not in text:
    text = re.sub(
        r'(options = uc\.ChromeOptions\(\))',
        r'\1\n    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})',
        text
    )

with open('v13_base.py', 'w', encoding='utf-8') as f:
    f.write(text)
