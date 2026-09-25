import subprocess
print(subprocess.run(["git", "diff", "v13_work.py"], capture_output=True, text=True).stdout)
