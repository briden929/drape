import sys; sys.stdout.reconfigure(encoding="utf-8")
with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V11_FINAL.py', 'r', encoding='utf-8') as f:
    text = 'import sys\nimport ast\n' + f.read()
    
text += '\nprint(run_ast_validation())\n'
with open('test_ast2.py', 'w', encoding='utf-8') as f:
    f.write(text)
