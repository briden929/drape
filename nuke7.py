import re
with open('v14_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Nuke STEP 7
pattern = r'# ============================================================================\n# STEP 7: ULTRA-FIXED GOOGLE LOGIN.*?# STEP 8:'
if re.search(pattern, text, re.DOTALL):
    text = re.sub(pattern, '# STEP 8:', text, flags=re.DOTALL)
    print("Nuked STEP 7")
else:
    print("STEP 7 not found by regex")
    
with open('v14_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
