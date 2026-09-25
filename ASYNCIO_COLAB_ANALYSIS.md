# Asyncio/Colab Analysis

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
