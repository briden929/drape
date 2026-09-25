
import re

with open('C:/Users/PC/.gemini/antigravity/scratch/Reddis/FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    code = f.read()

def dump_func(name):
    lines = code.split('\n')
    in_func = False
    indent = ""
    out_lines = []
    
    for line in lines:
        if line.startswith(f"async def {name}") or line.startswith(f"def {name}") or line.strip().startswith(f"def {name}"):
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


dump_func("process_bullmq_job")
dump_func("process_job_pipeline")
dump_func("_process_job_thread")
