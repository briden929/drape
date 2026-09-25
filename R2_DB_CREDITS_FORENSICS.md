# R2/DB/Credits Forensics

## Source Files Analyzed

1. FULL_QUEUE_WORKER_V14_N2N_FINAL.py - Best implementation
2. FULL_QUEUE_WORKER_V14_FINAL.py - V14 R2/DB/credits
3. build_v14_part1.py - Builder with R2/DB/credits
4. ecom_source.py - ECOM backend
5. build_script.py - Main build script
6. create_final.py - Final creation

## R2 Upload

### Configuration
```python
R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY")
```

### Upload Flow
```python
# WebP file uploaded to R2
# Returns absolute URL
# Uses boto3 client
# Credentials from environment variables
```

## Database State Transitions

### Configuration
```python
DB_URL = os.environ.get("DB_URL")
```

### State Machine
```
QUEUED -> GEMINI_RESERVED -> GEMINI_GENERATING -> RAW_DOWNLOAD_START -> 
GEMINI_RELEASED -> RAW_DOWNLOADING -> RAW_READY -> RAW_VALIDATED -> 
WMR_QUEUED -> WMR_RESERVED -> WMR_PROCESSING -> WMR_DOWNLOAD_START -> 
WMR_RELEASED -> CLEAN_READY -> WEBP_READY -> R2_READY -> 
DB_FINALIZING -> DB_READY -> CREDITS_SETTLED -> COMPLETED
```

### DB Operations
- Idempotent UPDATE queries
- Threaded connection pool via psycopg2
- State transitions tracked in database

## Credits Settlement

### Logic
```python
# credits.decrement_credits() called ONLY if final pipeline successful
# Failure in WMR/R2/DB must NOT prevent credits from being settled
# Credits failure should log warning, NOT fail the job
```

### Historical Bug: Credits Failure Blocking Job
**Versions affected:** V9-V13
**Problem:** Credits failure caused job to fail entirely
**Symptom:** Jobs failed due to credits system issues
**Fix:** Credits failure should log warning, allow job completion

### Order of Operations
```
1. WebP ready
2. R2 upload (WebP -> get URL)
3. DB state -> DB_FINALIZING
4. Credits settlement (decrement_credits)
5. DB state -> DB_READY
6. Credits settled -> CREDITS_SETTLED
7. COMPLETED
```

## Credits Failure Handling
- Credits failure MUST NOT fail the job
- Credits failure MUST log a warning
- Credits failure MUST be isolated from job completion
- Credits failure MUST NOT crash the worker

## What Must Be Preserved
1. `boto3` R2 client with env var credentials
2. `psycopg2` DB connection pool
3. Idempotent UPDATE queries
4. `credits.decrement_credits()` logic
5. Credits failure isolation (warning, not error)
6. DB state transition tracking
7. Order: R2 -> DB_FINALIZING -> Credits -> DB_READY -> COMPLETED
