# Resource Lifecycle Analysis

## Gemini T Resource Lifecycle

```
T0: NOT_CREATED
  |
  v
CREATED (create_gemini_driver(tid))
  |
  v
READY (driver initialized, Gemini app loaded)
  |
  v
RESERVED(job_id) (gemini_broker.acquire())
  |
  v
GENERATING (Gemini generating image)
  |
  v
DOWNLOAD_START_CONFIRMED (Browser.downloadWillBegin fires)
  |
  v
FREE (gemini_broker.release(resource_id))
  |
  v (TAB STAYS OPEN - persistent)
READY (next job can use this T)
```

**CRITICAL RULE:** T becomes FREE immediately after DOWNLOAD START CONFIRMED.
It does NOT wait for:
- Raw download completion
- PIL validation
- WMR processing
- WebP creation
- R2 upload
- DB update
- Credits settlement
- BullMQ completion

## WMR Resource Lifecycle

```
W0-T0: NOT_CREATED
  |
  v
CREATED (create_wmr_chrome_driver(0))
  |
  v
READY (driver initialized, WMR site loaded)
  |
  v
RESERVED(job_id) (wmr_broker.acquire())
  |
  v
PROCESSING (uploading, waiting for processing)
  |
  v
DOWNLOAD_START_CONFIRMED (exact "Download PNG" click fires)
  |
  v
FREE (wmr_broker.release(resource_id))
  |
  v (TAB STAYS OPEN - persistent)
READY (next job can use this W0-T0)
```

**CRITICAL RULE:** WMR becomes FREE immediately after DOWNLOAD PNG START CONFIRMED.
It does NOT wait for:
- PNG download completion
- Clean file writing
- WebP conversion
- R2 upload
- DB update
- Credits settlement

## Download Lifecycle (SEPARATE from Resource Lifecycle)

### Raw Download
```
downloadWillBegin -> GUID assigned -> download in progress -> completed -> stable -> PIL validated
```

### WMR Clean Download
```
exact Download PNG click -> downloadWillBegin -> GUID assigned -> download -> completed -> validated -> WebP -> R2 -> DB -> Credits
```

**KEY PRINCIPLE:** RESOURCE LIFECYCLE != DOWNLOAD LIFECYCLE

- Resource lifecycle: When a T/W tab can accept a new job
- Download lifecycle: When the file is fully processed end-to-end

## First-Free-Wins Scheduling

### Gemini
```python
class FirstFreeBroker:
    def __init__(self):
        self.seq = 0
        self.lock = threading.Lock()
        self.free_q = []  # heapq: (sequence, resource_id)
        self.in_q = set() # Currently reserved
    
    def release(self, resource_id):
        # Monotonic sequence preserves release order
        heapq.heappush(self.free_q, (self.seq, resource_id))
    
    def acquire(self):
        # Returns the resource that was released earliest
        return heapq.heappop(self.free_q)
```

**Example:**
- T0 busy, T1 busy, T2 free, T3 busy
- T2 gets assigned next job (First-Free-Wins)
- T3 does NOT get priority just because it has higher ID

### WMR
```python
wmr_resources = ["W0-T0", "W0-T1", "W1-T0", "W1-T1", "W2-T0", "W2-T1", "W3-T0", "W3-T1"]
```

Same First-Free-Wins logic applies globally.

**Example:**
- W0-T0 busy, W0-T1 free, W1-T0 free
- W0-T1 gets assigned next job (not W1-T0)

## Crash Isolation

### T0 Crash
- T0 driver quit() and recreated
- T1, T2, T3 unaffected
- Job assigned to T0 fails, retried on different T

### W0 Crash
- W0 driver quit() and recreated
- W1, W2, W3 unaffected
- Job assigned to W0 fails, retried on different W

### Single Job Failure
- Job marked FAILED
- Does NOT crash entire worker
- Other jobs continue processing

### Raw Download Failure
- T resource released immediately
- Job marked FAILED
- T available for next job

### WMR Download Failure
- WMR resource released immediately
- Job marked FAILED
- WMR tab available for next job
