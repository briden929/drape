with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read().lower()
    for word in ['msedge', 'edgeoptions', 'edgeworker']:
        if word in text:
            print(f"FAILED: Found forbidden word {word}")
print("EDGE CHECK DONE")
