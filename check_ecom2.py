import json, ast

with open('C:\\Users\\PC\\Downloads\\Copy_of_ECOM_COMBO_PHOTOSHOOT_ORDER.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

funcs = []
for cell in nb.get('cells', []):
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        # strip out ipython magics
        source = "\n".join([line for line in source.split('\n') if not line.startswith('!') and not line.startswith('%')])
        try:
            tree = ast.parse(source)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs.append(node.name)
        except Exception as e:
            pass

print("Functions in ECOM:", funcs)
