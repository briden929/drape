import re, sys

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_TEST.py", "r", encoding="utf-8") as f:
    text = f.read()

# Let's write a script to remove the entire first half if it's a blind copy-paste.
# We will find the "def start_display():" and see how many times it appears.
print("start_display count:", text.count("def start_display():"))
print("comprehensive_login count:", text.count("def comprehensive_login_check"))
