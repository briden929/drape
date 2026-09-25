
import re

with open('C:/Users/PC/.gemini/antigravity/scratch/Reddis/FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    code = f.read()

def dump_func(name):
    lines = code.split('\n')
    in_func = False
    indent = ""
    out_lines = []
    
    for i, line in enumerate(lines):
        if 'def ' + name in line or 'async def ' + name in line:
            in_func = True
            indent = line[:len(line) - len(line.lstrip())]
            out_lines.append(line)
            continue
            
        if in_func:
            if line.strip() == "" or line.startswith(indent + " ") or line.startswith(indent + "\t"):
                out_lines.append(line)
            else:
                break
    print(f"--- {name} ---")
    print("\n".join(out_lines))

dump_func("poll_active_downloads")
dump_func("_finalize_job")
