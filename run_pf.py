import subprocess
try:
    res = subprocess.run(["pyflakes", "C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py"], capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
except Exception as e:
    print(e)
