import os, ast
from collections import defaultdict

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
OUT_FILE = os.path.join(ROOT, "PYTHON_CODE_ANALYSIS.md")

py_files = []
for root, dirs, files in os.walk(ROOT):
    for f in files:
        if f.endswith('.py'):
            py_files.append(os.path.join(root, f))

categories = defaultdict(list)

for path in py_files:
    filename = os.path.basename(path)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        try:
            with open(path, 'r', encoding='cp1252') as f:
                content = f.read()
        except:
            continue
            
    # Classify based on filename and content
    name_lower = filename.lower()
    content_lower = content.lower()
    
    cat = "Other Scripts"
    if name_lower.startswith('add_') or name_lower.startswith('fix_') or name_lower.startswith('update_') or name_lower.startswith('apply_'):
        cat = "Patch / Modifier Scripts"
    elif name_lower.startswith('extract_') or name_lower.startswith('dump_') or name_lower.startswith('read_'):
        cat = "Extraction / Dump Scripts"
    elif name_lower.startswith('test_') or name_lower.startswith('check_') or name_lower.startswith('verify_'):
        cat = "Test / Validation Scripts"
    elif name_lower.startswith('build_') or name_lower.startswith('gen_') or name_lower.startswith('create_'):
        cat = "Generator / Builder Scripts"
    elif 'worker' in name_lower or 'main' in name_lower or 'v11' in name_lower or 'v14' in name_lower:
        cat = "Production Candidate / Worker Scripts"
    elif 'login' in name_lower:
        cat = "Login Scripts"
    
    # Extract structural info
    funcs = []
    classes = []
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                funcs.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
    except:
        pass # Syntax error in the script
        
    categories[cat].append({
        'name': filename,
        'size': len(content),
        'funcs': len(funcs),
        'classes': len(classes),
        'top_funcs': funcs[:3]
    })

with open(OUT_FILE, 'w', encoding='utf-8') as f:
    f.write("# Python Code Analysis (462 Files)\n\n")
    f.write("Detailed breakdown of every Python script found in the repository, categorized by their structural type and purpose.\n\n")
    
    for cat, files in sorted(categories.items()):
        f.write(f"## {cat} ({len(files)} files)\n")
        f.write("| Filename | Size (bytes) | Functions | Classes | Key Functions (Preview) |\n")
        f.write("|---|---|---|---|---|\n")
        for file in sorted(files, key=lambda x: x['name']):
            funcs_str = ", ".join(file['top_funcs'])
            if file['funcs'] > 3:
                funcs_str += "..."
            if not funcs_str:
                funcs_str = "None (Flat script)"
            f.write(f"| {file['name']} | {file['size']} | {file['funcs']} | {file['classes']} | {funcs_str} |\n")
        f.write("\n")
