with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V13_FINAL.py', 'rb') as f:
    b = f.read()

s = b.decode('utf-8', errors='replace')
print("Rocket in file:", "\U0001f680" in s)
print("Key in file:", "\U0001f511" in s)
print("Mojibake sequences in utf-8 decode:")
print("ðŸ" in s)
