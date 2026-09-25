import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('C:\\Users\\PC\\Downloads\\Copy_of_ECOM_COMBO_PHOTOSHOOT_ORDER.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb.get('cells', []):
    if cell['cell_type'] == 'code':
        print("".join(cell['source']))
        print("\n\n" + "-"*80 + "\n\n")
