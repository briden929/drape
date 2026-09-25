# V15 RUNTIME HARDENING CHANGELOG

## Changes Required for Production Readiness

### P1: Real Browser Operations (CRITICAL)
- Replace `time.sleep(1.0)` in `process_gemini()` with real Selenium operations
- Replace `time.sleep(1.0)` in `process_wmr()` with real Selenium operations
- Implement CDP `Browser.downloadWillBegin` event listener
- Implement CDP `Browser.downloadProgress` event listener
- Implement `create_gemini_driver(tid)` with actual `webdriver.Chrome()`
- Implement `create_wmr_chrome_driver(worker_id)` with actual `webdriver.Chrome()`

### P2: Service Connections (CRITICAL)
- Connect BullMQ Worker to Redis using `REDIS_URL` environment variable
- Implement `boto3.client('s3')` for R2 upload
- Implement `psycopg2.connect()` for DB connection
- Implement `credits.decrement_credits()` for credits settlement

### P3: Pipeline Completion (MEDIUM)
- Implement PIL image validation
- Implement WebP conversion via Pillow
- Implement download stability checks
- Implement file size verification
- Implement attachment count verification

### P4: Error Handling (MEDIUM)
- Add comprehensive error handling for all pipeline stages
- Add retry logic for transient failures
- Add timeout handling for long operations
- Add logging for all pipeline stages
- Add proper exception propagation

## Change Log

| Version | Date | Change | Reason |
|---------|------|--------|--------|
| V15 Baseline | 2026-09-25 | Skeleton architecture | Forensic rebuild from V14 N2N analysis |
| V15 Pending | TBD | Real Selenium | Production readiness requires browser |
| V15 Pending | TBD | BullMQ connection | Queue requires Redis |
| V15 Pending | TBD | R2/DB/Credits | Pipeline requires services |
| V15 Pending | TBD | CDP events | Download tracking requires browser |
