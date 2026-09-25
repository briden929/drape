import os, sys, datetime, re, ast

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
OUT_FILE = os.path.join(ROOT, "PROJECT_FILE_INVENTORY.md")

headers = [
    "Relative Path", "Filename", "Ext", "Size (bytes)", "Modified", "File Type",
    "Purpose", "Generation/Version", "Category", "Imports", "Reads", "Generates", "Modifies",
    "Prod Logic", "Browser Logic", "Queue Logic", "Auth Logic", "DL Logic", "WMR Logic",
    "R2/DB/Cred Logic", "Tests", "Historical", "Patch/Gen", "Preserve", "Confidence"
]

def analyze_file(path):
    rel_path = os.path.relpath(path, ROOT)
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1].lower()
    stat = os.stat(path)
    size = stat.st_size
    modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
    
    file_type = "Script" if ext == ".py" else "Text" if ext in [".txt", ".md"] else "Data" if ext in [".json", ".yaml", ".yml", ".csv"] else "Other"
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='cp1252') as f:
                content = f.read()
        except Exception:
            content = ""
            
    content_lower = content.lower()
    
    # Heuristics
    purpose = "Unknown"
    gen = "Unknown"
    category = []
    
    # Version detection
    v_match = re.search(r'v(\d+)', filename, re.IGNORECASE)
    if v_match:
        gen = "V" + v_match.group(1)
    elif "ecom" in filename.lower():
        gen = "ECOM"
    
    imports = []
    if ext == ".py":
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names: imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module: imports.append(node.module)
        except:
            imports = re.findall(r'^import (\w+)', content, re.MULTILINE) + re.findall(r'^from (\w+) import', content, re.MULTILINE)
    
    reads = list(set(re.findall(r'open\([\'"]([^\'"]+)[\'"],\s*[\'"]r[\'"]', content)))
    generates = list(set(re.findall(r'open\([\'"]([^\'"]+)[\'"],\s*[\'"]w[\'"]', content)))
    modifies = []
    
    prod_logic = "Yes" if "class " in content or "def main" in content else "No"
    browser = "Yes" if "selenium" in content_lower or "webdriver" in content_lower else "No"
    queue = "Yes" if "bullmq" in content_lower or "redis" in content_lower else "No"
    auth = "Yes" if "login" in content_lower or "auth" in content_lower or "cookie" in content_lower else "No"
    dl = "Yes" if "download" in content_lower or "cdp" in content_lower else "No"
    wmr = "Yes" if "wmr" in content_lower else "No"
    r2_db = "Yes" if "boto3" in content_lower or "psycopg2" in content_lower or "r2" in content_lower or "credit" in content_lower else "No"
    tests = "Yes" if "test_" in filename or "def test" in content else "No"
    patch_gen = "Yes" if "re.sub" in content or "replace" in content and ext == ".py" else "No"
    
    if patch_gen == "Yes":
        category.append("K. PATCH SCRIPT" if "re.sub" in content else "L. GENERATOR SCRIPT")
        purpose = "Modify/Generate code"
    elif tests == "Yes":
        category.append("P. UNIT TEST")
        purpose = "Testing"
    elif "report" in filename.lower() or "audit" in filename.lower():
        category.append("S. AUDIT REPORT")
        purpose = "Reporting"
    elif ext == ".py" and prod_logic == "Yes":
        category.append("B. PRODUCTION SOURCE")
        purpose = "Worker Logic"
    
    if not category:
        category.append("Y. UNKNOWN")
        
    historical = "Yes" if "old" in filename.lower() or "backup" in filename.lower() else "No"
    preserve = "Review"
    confidence = "High" if ext == ".py" else "Medium"
    
    imports_str = ", ".join(set(imports))[:50]
    reads_str = ", ".join(reads)[:30]
    gens_str = ", ".join(generates)[:30]
    cats_str = ", ".join(category)
    
    return [
        rel_path, filename, ext, str(size), modified, file_type, purpose, gen, cats_str,
        imports_str, reads_str, gens_str, "", prod_logic, browser, queue, auth, dl, wmr, r2_db,
        tests, historical, patch_gen, preserve, confidence
    ]

rows = []
for root, dirs, files in os.walk(ROOT):
    for f in files:
        rows.append(analyze_file(os.path.join(root, f)))

with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write("# Project File Inventory\n\n")
    f.write("| " + " | ".join(headers) + " |\n")
    f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
    for r in rows:
        r = [str(x).replace("\n", " ").replace("|", ",") for x in r]
        f.write("| " + " | ".join(r) + " |\n")

print(f"Inventory written to {OUT_FILE}")
