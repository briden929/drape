import os
files = [
    r"C:\Users\PC\Downloads\google login.py",
    r"C:\Users\PC\Downloads\copy_of_ecom_combo_photoshoot_order.py",
    r"C:\Users\PC\Downloads\GEMINI QUEUE WORKER (1).ipynb",
    r"C:\Users\PC\Downloads\FULL_QUEUE_WORKER_V11.py"
]
for f in files:
    print(f"{f}: {os.path.exists(f)}")
