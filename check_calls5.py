with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    for line in f:
        if 'get_wmr_job_dir' in line:
            print(line.strip())
