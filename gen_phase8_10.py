import os

base = r'C:\Users\PC\.gemini\antigravity\scratch\Reddis'

def write_report(filepath, content):
    full_path = os.path.join(base, filepath)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written: {filepath}")

# ============ 8. ASYNCIO_COLAB_ANALYSIS.md ============
asyncio_analysis = """# Asyncio/Colab Analysis

## Environment Detection

```python
def is_running_in_notebook():
    try:
        get_ipython = __builtins__['get_ipython']
        shell = get_ipython()
        if shell is None:
            return False
        return shell.__class__.__name__ == 'ZMQInteractiveShell'
    except:
        return False
```

## Colab Entrypoint Pattern

In Colab/Jupyter, the event loop is ALREADY running. Calling `asyncio.run(main())` raises:
```
RuntimeError: asyncio.run() cannot be called from a running event loop
```

**Correct Colab pattern:**
```python
loop = asyncio.get_running_loop()
WORKER_MAIN_TASK = loop.create_task(main())
# Use done_callback for exception surfacing
WORKER_MAIN_TASK.add_done_callback(lambda t: print(t.exception()) if t.exception() else None)
```

**Correct Standalone pattern:**
```python
if __name__ == "__main__":
    asyncio.run(main())
```

## V14 N2N Entrypoint

```python
async def main():
    # Colab-safe: uses asyncio.get_running_loop()
    loop = asyncio.get_running_loop()
    
    async def process_msg(job, token):
        return await execute_job(job.id, job.data)
    
    worker = Worker("generations", process_msg, ...)
    
    while not _shutdown_event.is_set():
        await asyncio.sleep(1)
```

```python
if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(main())
    except RuntimeError:
        asyncio.run(main())
```

## Thread Safety Patterns

### Selenium Thread Safety
Selenium is synchronous/blocking. Must use `asyncio.to_thread()`:
```python
def _sync_gemini_ops():
    # Selenium calls here
    return result

result = await asyncio.to_thread(_sync_gemini_ops)
```

### Future Resolution Thread Safety
```python
def resolve_future_once(loop, future, result, is_exception=False):
    def _resolve():
        if future.done():
            return
        if is_exception:
            future.set_exception(result)
        else:
            future.set_result(result)
    loop.call_soon_threadsafe(_resolve)
```

### Double-Start Prevention
```python
_worker_started = False
if _worker_started:
    return  # Already running
_worker_started = True
```

## Historical Bugs

### Bug 1: asyncio.run() inside Colab
**Versions affected:** V9-V13
**Problem:** Called `asyncio.run(main())` inside notebook event loop
**Symptom:** `RuntimeError: asyncio.run() cannot be called from a running event loop`
**Fix:** V14 N2N - uses `loop.create_task(main())` in Colab

### Bug 2: coroutine never awaited
**Versions affected:** V9-V12
**Problem:** Created coroutines but didn't await them
**Symptom:** "coroutine was never awaited" warnings
**Fix:** V14 N2N - proper await patterns

### Bug 3: nest_asyncio usage
**Versions affected:** Some V12/V13
**Problem:** Used `nest_asyncio` to run asyncio in nested loop
**Symptom:** Unreliable, could cause event loop corruption
**Fix:** V14 N2N - uses `get_running_loop()` + `create_task()`

### Bug 4: Selenium on main event loop
**Versions affected:** V9-V14
**Problem:** Blocking Selenium calls on main asyncio thread
**Symptom:** Event loop blocked, no concurrent operations
**Fix:** V14 N2N - uses `asyncio.to_thread()` for Selenium operations

## Current V15 Implementation

V15 correctly implements:
- Colab detection with try/except RuntimeError
- `loop.create_task(main())` for Colab
- `asyncio.run(main())` for standalone
- `asyncio.to_thread()` for Selenium
- `resolve_future_once()` for thread-safe futures
- Double-start guard with `_worker_started`

## Colab vs Standalone Comparison

| Aspect | Colab | Standalone |
|--------|-------|------------|
| Event loop | Already running | Created by asyncio.run() |
| Entrypoint | `loop.create_task(main())` | `asyncio.run(main())` |
| Selenium | `asyncio.to_thread()` | `asyncio.to_thread()` |
| Future resolution | `loop.call_soon_threadsafe()` | `loop.call_soon_threadsafe()` |
| Shutdown | KeyboardInterrupt | KeyboardInterrupt |
| VNC | Required for browser | May not be needed |
| Display | Xvfb required | May not be needed |
"""
write_report("ASYNCIO_COLAB_ANALYSIS.md", asyncio_analysis)

# ============ 9. RESOURCE_LIFECYCLE_ANALYSIS.md ============
resource_lifecycle = """# Resource Lifecycle Analysis

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
"""
write_report("RESOURCE_LIFECYCLE_ANALYSIS.md", resource_lifecycle)
print("Resource lifecycle done")
