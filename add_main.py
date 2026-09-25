with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("""
    add('''
def startup_preflight():
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
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            
    print("Checking Chrome Driver creation...")
    chrome_driver = create_persistent_chrome_driver()
    check_chrome_driver_health(chrome_driver)

async def main():
    global main_loop, GEMINI_BROKER, WMR_BROKER, gemini_pool, wmr_pool
    main_loop = asyncio.get_event_loop()
    
    print("===============================================================")
    print("STARTUP PREFLIGHT")
    startup_preflight()
    print("PREFLIGHT SUCCESSFUL")
    print("===============================================================")
    
    GEMINI_BROKER = FirstFreeBroker()
    WMR_BROKER = FirstFreeBroker()
    
    gemini_pool = GeminiWorkerPool(GEMINI_WORKERS)
    wmr_pool = WmrWorkerPool(WMR_WORKERS)
    
    gemini_pool.start_all()
    wmr_pool.start_all()
    
    main_loop.create_task(poll_active_downloads())
    
    print("Starting BullMQ Worker...")
    # worker = Worker('generations', process_bullmq_job, {'connection': os.environ.get('REDIS_TUNNEL_URL'), 'concurrency': BULLMQ_CONCURRENCY})
    
    # Keep alive
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
''')

with open('C:\\\\Users\\\\PC\\\\Desktop\\\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as fout:
    fout.write("\\n\\n".join(v14_source))
    
print("V14 Generated.")
""")
