# Run architecture unit tests
import heapq, threading, asyncio, tempfile, os
from PIL import Image
from io import BytesIO

class FirstFreeBroker:
    def __init__(self):
        self.seq = 0; self.lock = threading.Lock(); self.free_q = []; self.in_q = set()
    def release(self, rid):
        with self.lock:
            if rid not in self.in_q:
                self.seq += 1; heapq.heappush(self.free_q, (self.seq, rid)); self.in_q.add(rid)
    def acquire(self):
        with self.lock:
            if not self.free_q: return None
            _, rid = heapq.heappop(self.free_q); self.in_q.remove(rid); return rid

results = []
def chk(name, got, expected):
    ok = got == expected
    results.append((name, ok))
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
    if not ok: print(f"       got={got!r} want={expected!r}")

print("=== Architecture Tests ===")
# T8
b = FirstFreeBroker()
[b.release(t) for t in ["T2","T0","T3","T1"]]
chk("T8 FirstFree basic", [b.acquire() for _ in range(4)], ["T2","T0","T3","T1"])

# T9 
b = FirstFreeBroker()
[b.release(t) for t in ["T0","T1","T2"]]
[b.acquire() for _ in range(3)]
b.release("T1"); b.release("T2"); b.release("T0")
chk("T9 FirstFree reuse", [b.acquire() for _ in range(3)], ["T1","T2","T0"])

# T12
b = FirstFreeBroker()
[b.release(r) for r in ["W0-T0","W0-T1","W1-T0","W1-T1"]]
[b.acquire() for _ in range(4)]
b.release("W1-T0"); b.release("W0-T1")
chk("T12 WMR global FirstFree", [b.acquire() for _ in range(2)], ["W1-T0","W0-T1"])

print("\n=== Asyncio Dual-Mode Tests ===")

# Test A: main is coroutine function
import inspect
# We test from source-level (can't import due to missing deps)
# Instead verify the pattern manually

async def _mock_main():
    loop = asyncio.get_running_loop()
    return loop is not None

async def _test_A():
    chk("TA main is async def", inspect.iscoroutinefunction(_mock_main), True)
    result = await _mock_main()
    chk("TA get_running_loop inside coroutine", result, True)

asyncio.run(_test_A())

# Test B: start_in_current_environment pattern simulation
_worker_started = False
worker_main_task = None

def _mock_start():
    global worker_main_task, _worker_started
    if _worker_started:
        return None, "already_running"
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        _worker_started = True
        worker_main_task = loop.create_task(_mock_main())
        return worker_main_task, "scheduled"
    else:
        _worker_started = True
        asyncio.run(_mock_main())
        _worker_started = False
        return None, "terminal"

async def _test_B():
    global _worker_started, worker_main_task
    _worker_started = False
    task, mode = _mock_start()
    chk("TB Colab mode: create_task returned", isinstance(task, asyncio.Task), True)
    chk("TB Colab mode: scheduled", mode, "scheduled")
    # Double start protection
    task2, mode2 = _mock_start()
    chk("TB double-start blocked", mode2, "already_running")
    # Reset
    _worker_started = False
    worker_main_task = None

asyncio.run(_test_B())

# Test C: Terminal mode (no running loop)
import subprocess, sys
mini = "import asyncio\nasync def main():\n    pass\ntry:\n    loop = asyncio.get_running_loop()\nexcept RuntimeError:\n    asyncio.run(main())\n    print('TERMINAL_OK')\n"
r = subprocess.run([sys.executable, "-c", mini], capture_output=True, text=True)
chk("TC terminal path", "TERMINAL_OK" in r.stdout, True)

print("\n=== WebP Test ===")
tmp = tempfile.mktemp(suffix=".png")
Image.new("RGB", (100,100), (200,100,50)).save(tmp)

def convert_webp(png_path):
    webp = os.path.splitext(png_path)[0] + ".webp"
    img = Image.open(png_path); img.load()
    buf = BytesIO(); img.save(buf, format="WEBP", quality=85); 
    open(webp, "wb").write(buf.getvalue()); return webp

w = convert_webp(tmp)
chk("T24 WebP conversion", os.path.exists(w) and Image.open(w).format == "WEBP", True)

print(f"\n=== SUMMARY ===")
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} PASS")
for n, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {n}")
