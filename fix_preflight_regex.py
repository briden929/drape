import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Replace the broken startup_preflight function completely
pattern = r"def startup_preflight\(\):.*?def main\(\):"
good_preflight = """def startup_preflight():
    global chrome_driver
    print("Checking dependencies...")
    import bullmq
    import psycopg2
    import selenium
    
    print("Checking directories...")
    for d in [STATE_DIR, CHROME_DL_BASE, CHROME_STAGING_BASE, WMR_STAGING_BASE, WMR_DL_BASE, FINAL_OUTPUT_BASE]:
        d.mkdir(parents=True, exist_ok=True)
        
    print("Checking Redis URL...")
    assert os.environ.get('REDIS_TUNNEL_URL'), "REDIS_TUNNEL_URL not set"
    
    print("Checking DB...")
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as e:
        print(f"Warning DB check failed: {e}")
            
    print("Checking Chrome Driver creation...")
    chrome_driver = create_persistent_chrome_driver()
    check_chrome_driver_health(chrome_driver)

async def main():"""

source = re.sub(pattern, good_preflight, source, flags=re.DOTALL)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(source)
