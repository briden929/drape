import re
with open('v19_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix WMR download snapshot
# WMR worker does:
#        # Wait for file
#        import shutil
#        t0 = time.time()
#        final_file = None
#        while time.time() - t0 < 60:
# But we need snapshot before clicking!
text = text.replace(
    'log(f"{prefix} DOWNLOAD_BUTTON_DETECTED")',
    '''log(f"{prefix} DOWNLOAD_BUTTON_DETECTED")
        
        dl_dir = self.staging_dir / f"{job_id}_dl"
        dl_dir.mkdir(parents=True, exist_ok=True)
        set_tab_download_dir(drv, str(dl_dir))
        
        # Take snapshot BEFORE click
        files_before = set(dl_dir.iterdir())'''
)

text = text.replace(
    'for f in dl_dir.iterdir():',
    'for f in set(dl_dir.iterdir()) - files_before:'
)
# Remove duplicate directory creation
text = re.sub(r'dl_dir = self\.staging_dir.*?set_tab_download_dir\(drv, str\(dl_dir\)\)\n', '', text, count=1, flags=re.DOTALL)


# AST Validation
ast_code = '''
def run_ast_validation():
    import ast, sys
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception as e:
        print(f"AST parsing failed: {e}")
        return False
        
    func_names = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    
    # Check for duplicates of critical functions
    critical = [
        "create_gemini_driver", "create_wmr_chrome_driver", "poll_active_downloads",
        "_enqueue_wmr", "poll_wmr_workers", "_finalize_and_clean_job",
        "update_redis_queue_stats_loop", "central_scheduler_loop", "process_bullmq_job",
        "print_pipeline_status"
    ]
    for c in critical:
        count = func_names.count(c)
        if count == 0:
            print(f"AST ERROR: missing critical function {c}")
            return False
        if count > 1:
            print(f"AST ERROR: duplicate critical function {c} (found {count} times)")
            return False
            
    # Check for forbidden symbols
    forbidden = ["MAX_WMR_WORKERS", "find_first_idle_tab", "chrome_lock", "tab_states", "self.work_queue", "w.work_queue", "create_chrome_driver"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id in forbidden and node.id != "create_chrome_driver":
                print(f"AST ERROR: forbidden symbol found: {node.id}")
                return False
        if isinstance(node, ast.Attribute):
            if node.attr == "work_queue":
                print(f"AST ERROR: forbidden attribute found: work_queue")
                return False
                
    return True
'''
text = text.replace('def run_startup_self_test():', ast_code + '\ndef run_startup_self_test():')
text = text.replace('print("STARTUP_SELF_TEST=PASS")', 'if not run_ast_validation():\n        raise RuntimeError("AST_VALIDATION_FAILED")\n    print("STARTUP_SELF_TEST=PASS")')


with open('v19_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Task 5 done")
