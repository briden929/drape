import json

with open('C:\\Users\\PC\\Downloads\\Copy_of_ECOM_COMBO_PHOTOSHOOT_ORDER.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

out = []
for cell in nb.get('cells', []):
    if cell['cell_type'] == 'code':
        out.append("".join(cell['source']))
        out.append("\n\n" + "-"*80 + "\n\n")

with open('ecom_source.py', 'w', encoding='utf-8') as f:
    f.write("".join(out))
