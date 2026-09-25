import sys; sys.stdout.reconfigure(encoding="utf-8")
with open('v13_clean_ast_fixed.py', 'r', encoding='utf-8') as f:
    top = f.read()
with open('v13_arch.py', 'r', encoding='utf-8') as f:
    arch = f.read()

# Wait, `v13_arch.py` has `MAX_CONCURRENT_TABS` ? Let me check.
# Let's fix the GEMINI_WORKERS NameError in v13_arch directly
arch = arch.replace('class GeminiWorkerPool:\n    def __init__(self, max_workers: int = GEMINI_WORKERS):', 'class GeminiWorkerPool:\n    def __init__(self, max_workers: int = MAX_CONCURRENT_TABS):')

final_code = top + "\n\n" + arch + "\nif __name__ == '__main__':\n    main()\n"
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(final_code)
print("Arch appended.")
