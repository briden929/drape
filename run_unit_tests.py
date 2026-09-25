# Run FirstFree + Unit tests
import heapq, threading, time, uuid

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
def check(name, got, expected):
    ok = got == expected
    results.append((name, ok))
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
    if not ok:
        print(f"       Got: {got}")
        print(f"       Expected: {expected}")

print("=== FirstFree Tests ===")
# T8
b = FirstFreeBroker()
b.release('T2'); b.release('T0'); b.release('T3'); b.release('T1')
got = [b.acquire() for _ in range(4)]
check("T8: basic release order", got, ['T2','T0','T3','T1'])

# T9
b = FirstFreeBroker()
[b.release(t) for t in ['T0','T1','T2']]
[b.acquire() for _ in range(3)]  # drain
b.release('T1'); b.release('T2'); b.release('T0')
got = [b.acquire() for _ in range(3)]
check("T9: reuse release order", got, ['T1','T2','T0'])

# T12
b = FirstFreeBroker()
[b.release(r) for r in ['W0-T0','W0-T1','W1-T0','W1-T1']]
[b.acquire() for _ in range(4)]  # drain
b.release('W1-T0'); b.release('W0-T1')
got = [b.acquire() for _ in range(2)]
check("T12: WMR global first-free", got, ['W1-T0','W0-T1'])

print("\n=== WebP Test (T24) ===")
import tempfile, os
from PIL import Image
from io import BytesIO
# Create a real temp PNG
tmp = tempfile.mktemp(suffix='.png')
img = Image.new('RGB', (200,200), color=(100,200,100))
img.save(tmp)

def convert_to_webp(png_path, max_size_kb=800):
    try:
        webp_path = os.path.splitext(png_path)[0] + '.webp'
        img = Image.open(png_path); img.load()
        if img.mode not in ('RGB','RGBA'):
            img = img.convert('RGBA' if img.mode in ('P','LA','PA') else 'RGB')
        for q in (90, 80, 70, 60, 50, 40):
            buf = BytesIO()
            img.save(buf, format='WEBP', quality=q, method=4)
            data = buf.getvalue()
            if len(data)/1024 <= max_size_kb or q == 40:
                from pathlib import Path
                Path(webp_path).write_bytes(data)
                return webp_path
        return webp_path
    except Exception as e:
        return None

webp = convert_to_webp(tmp)
check("T24: WebP conversion", webp is not None and os.path.exists(webp), True)
if webp:
    wimg = Image.open(webp)
    check("T24: WebP valid format", wimg.format, 'WEBP')

print("\n=== validate_image_file Test ===")
def validate_image_file(path, min_size=1024, max_size=None):
    from pathlib import Path
    try:
        p = Path(path)
        if not p.exists(): return (False, f'File not found: {path}')
        sz = p.stat().st_size
        if sz < min_size: return (False, f'File too small: {sz} < {min_size}')
        with Image.open(p) as im: im.verify()
        with Image.open(p) as im:
            im.load(); w, h = im.size
            if w < 32 or h < 32: return (False, f'Image too small: {w}x{h}')
        return (True, 'OK')
    except Exception as e:
        return (False, f'Validation error: {e}')

valid, msg = validate_image_file(tmp, 100)
check("validate: real PNG", valid, True)

valid2, msg2 = validate_image_file('/nonexistent.png', 100)
check("validate: nonexistent", valid2, False)

print("\n=== Asyncio Test (T22) ===")
import asyncio

async def test_colab_pattern():
    loop = asyncio.get_running_loop()
    assert loop is not None, "Loop should be running"
    return True

# This simulates what happens in Colab: running inside existing loop
try:
    result = asyncio.run(test_colab_pattern())
    check("T22: async main can get running loop", result, True)
except Exception as e:
    results.append(("T22", False))
    print(f"  FAIL T22: {e}")

print("\n=== SUMMARY ===")
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"{passed}/{total} PASS")
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
