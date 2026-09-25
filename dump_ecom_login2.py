import json

with open('C:\\Users\\PC\\Downloads\\Copy_of_ECOM_COMBO_PHOTOSHOOT_ORDER.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

out = []
for cell in nb.get('cells', []):
    if cell['cell_type'] == 'code':
        # strip magics
        lines = [line for line in "".join(cell['source']).split('\n') if not line.startswith('!') and not line.startswith('%')]
        out.append("\n".join(lines))

with open('ecom_source_clean.py', 'w', encoding='utf-8') as f:
    f.write("\n\n".join(out))

import ast
tree = ast.parse("\n\n".join(out))
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in ('handle_login', 'quick_check_logged_in', 'check_captcha'):
        start = node.lineno - 1
        end = node.end_lineno
        lines = "\n\n".join(out).split('\n')[start:end]
        print('\n'.join(lines))
        print('-'*80)
