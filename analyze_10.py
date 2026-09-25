import os
import ast
import json

files = [
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\DUPLICATE_CODE_ANALYSIS.md",
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_V14_N2N_FINAL.py",
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_V14_N2N_TEST.py",
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\v11_raw.py",
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\user_prompt_v14_rebuild.txt",
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_V9.1_FINAL.py",
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\Copy_of_ECOM_COMBO_PHOTOSHOOT_ORDER.ipynb",
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_V11.py",
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_V9_FINAL.py",
    r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_V4_ONE_CELL.py"
]

results = {}

for path in files:
    if not os.path.exists(path):
        results[os.path.basename(path)] = "File not found."
        continue
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        try:
            with open(path, 'r', encoding='cp1252') as f:
                content = f.read()
        except Exception as e:
            results[os.path.basename(path)] = f"Could not read: {e}"
            continue
            
    lines = content.split('\n')
    size = len(content)
    
    if path.endswith('.md') or path.endswith('.txt'):
        results[os.path.basename(path)] = f"Text/Markdown file. Lines: {len(lines)}, Size: {size} bytes. Preview: {content[:100]}..."
        continue
        
    if path.endswith('.ipynb'):
        try:
            data = json.loads(content)
            cells = len(data.get('cells', []))
            code_cells = len([c for c in data.get('cells', []) if c.get('cell_type') == 'code'])
            results[os.path.basename(path)] = f"Jupyter Notebook. Total Cells: {cells}, Code Cells: {code_cells}. Size: {size} bytes."
        except:
            results[os.path.basename(path)] = "Invalid IPYNB."
        continue

    # Python analysis
    classes = []
    funcs = []
    imports = []
    has_async = False
    has_thread = False
    
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef):
                funcs.append(node.name)
            elif isinstance(node, ast.AsyncFunctionDef):
                funcs.append(f"async {node.name}")
                has_async = True
            elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                imports.append(ast.unparse(node))
                if 'threading' in ast.unparse(node): has_thread = True
    except:
        pass # syntax error
        
    results[os.path.basename(path)] = {
        "Lines": len(lines),
        "Size": size,
        "Classes": classes,
        "Total Functions": len(funcs),
        "Top Functions": funcs[:10],
        "Has Async": has_async,
        "Has Threading": has_thread
    }

for name, res in results.items():
    print(f"--- {name} ---")
    if isinstance(res, dict):
        print(f"Lines: {res['Lines']} | Size: {res['Size']} | Async: {res['Has Async']} | Thread: {res['Has Threading']}")
        print(f"Classes: {', '.join(res['Classes'])}")
        print(f"Functions (Preview): {', '.join(res['Top Functions'])}")
    else:
        print(res)
    print("")
