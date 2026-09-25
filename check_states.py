with open('v12_work.py', 'r', encoding='utf-8') as f:
    text = f.read()
if 'self.state = "VALIDATING"' in text:
    print('States injected successfully')
else:
    print('Failed to inject states')
