# Fix the wrong nb_check_image call at L1967
# "if not nb_check_image(drv, prefix):" - this should be a composer check
# Actually this is a check that composer is blank/ready (new chat)
# We should replace this with a proper check

# Let us look at lines around 1967
with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_FINAL.py", 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(1960, 1980):
    print(f"L{i+1}: {lines[i].rstrip()}")
