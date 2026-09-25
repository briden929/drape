with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    for line in f:
        if 'def check_captcha' in line or 'def handle_login' in line or 'def comprehensive_login_check' in line:
            print(line.strip())
