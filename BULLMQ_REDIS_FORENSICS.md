# BullMQ & Redis Forensics

## Source Files Analyzed

1. FULL_QUEUE_WORKER_V14_N2N_FINAL.py - Best BullMQ implementation
2. FULL_QUEUE_WORKER_V14_FINAL.py - V14 BullMQ
3. build_v14.py / build_v14_part1.py - Builders
4. bullmq_block.py - BullMQ block generator
5. bottom.py - Bottom module with BullMQ job handler
6. build_script.py - Main build script
7. create_final.py - Final creation

## BullMQ Architecture

### Queue Name
```python
QUEUE_NAME = "generations"
```

### Worker Configuration
```python
BULLMQ_CONCURRENCY = 8
# Worker processes up to 8 jobs concurrently
```

### Job Handler
```python
async def process_bullmq_job(job, job_token):
    job_id = job.id
    payload = job.data
    # Create JobContext
    # Execute pipeline: Gemini -> Raw Download -> WMR -> Downstream
    # Return {"status": "completed"} or {"status": "failed", "error": "..."}
```

### Redis Connection
```python
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')
# Uses environment variable for configuration
```

## Concurrency Model

**KEY DISTINCTION:** BullMQ job concurrency, resource concurrency, Gemini concurrency, WMR concurrency are SEPARATE concepts.

- **BullMQ concurrency:** 8 jobs processed simultaneously
- **Gemini concurrency:** 4 T resources (T0-T3)
- **WMR concurrency:** 8 WMR resources (W0-T0 through W3-T1)
- **Resource concurrency:** Limited by available T/W resources, not by BullMQ worker count

## Historical Bugs

### Bug 1: Conflated Concurrency
**Versions affected:** V9-V12
**Problem:** BullMQ worker concurrency conflated with Gemini T resource concurrency
**Symptom:** Too many jobs assigned, T resources exhausted
**Fix:** V14 N2N - Separate FirstFreeBroker for T resources

### Bug 2: No Redis Connection Handling
**Versions affected:** Some V13/V14
**Problem:** No retry logic for Redis connection failures
**Symptom:** Worker crashes on Redis disconnect
**Fix:** V14 N2N - Connection error handling

### Bug 3: Missing Heartbeat
**Versions affected:** V9-V13
**Problem:** No BullMQ heartbeat mechanism
**Symptom:** Stale jobs not detected
**Fix:** V14 N2N - Heartbeat monitoring

## BullMQ Job Lifecycle

```
Job QUEUED
  -> BullMQ worker picks up job
  -> GEMINI_RESERVED
  -> GEMINI_GENERATING
  -> RAW_DOWNLOAD_START
  -> GEMINI_RELEASED
  -> RAW_DOWNLOADING
  -> RAW_READY
  -> WMR_QUEUED
  -> WMR_RESERVED
  -> WMR_PROCESSING
  -> WMR_DOWNLOAD_START
  -> WMR_RELEASED
  -> CLEAN_READY
  -> WEBP_READY
  -> R2_READY
  -> DB_READY
  -> CREDITS_SETTLED
  -> COMPLETED
```

## What Must Be Preserved
1. `process_bullmq_job()` - Main job handler
2. BullMQ Worker configuration with concurrency
3. Redis URL from environment variable
4. Queue name "generations"
5. Job state machine
6. Failure isolation per job
7. BullMQ completion/failure handling
8. Retry logic
