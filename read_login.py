import json, ast

with open('C:\\Users\\PC\\Downloads\\Copy_of_ECOM_COMBO_PHOTOSHOOT_ORDER.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb.get('cells', []):
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        if 'def handle_login(' in source or 'def quick_check_logged_in(' in source:
            print(source)
            print("-" * 80)
