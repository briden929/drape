# Run FirstFree test 
import sys, os
sys.path.insert(0, os.getcwd())

# Simulate the FirstFreeBroker
import heapq
import threading

class FirstFreeBroker:
    def __init__(self):
        self.seq = 0
        self.lock = threading.Lock()
        self.free_q = []
        self.in_q = set()
    def release(self, resource_id):
        with self.lock:
            if resource_id not in self.in_q:
                self.seq += 1
                heapq.heappush(self.free_q, (self.seq, resource_id))
                self.in_q.add(resource_id)
    def acquire(self):
        with self.lock:
            if not self.free_q:
                return None
            seq, resource_id = heapq.heappop(self.free_q)
            self.in_q.remove(resource_id)
            return resource_id
    def remove(self, resource_id):
        with self.lock:
            if resource_id in self.in_q:
                self.free_q = [x for x in self.free_q if x[1] != resource_id]
                heapq.heapify(self.free_q)
                self.in_q.remove(resource_id)

# TEST 8: First free test
print("=== TEST 8: FIRST-FREE basic ===")
b = FirstFreeBroker()
b.release('T2'); b.release('T0'); b.release('T3'); b.release('T1')
expected = ['T2', 'T0', 'T3', 'T1']
got = [b.acquire() for _ in range(4)]
print(f"Expected: {expected}")
print(f"Got:      {got}")
print("PASS" if got == expected else "FAIL")

# TEST 9: First free release order under reuse
print("\n=== TEST 9: FIRST-FREE reuse ===")
b = FirstFreeBroker()
b.release('T0'); b.release('T1'); b.release('T2')
# Simulate jobs assigned
t0 = b.acquire(); t1 = b.acquire(); t2 = b.acquire()
print(f"Assigned: T0={t0}, T1={t1}, T2={t2}")
# Now release in order: T1, T2, T0
b.release('T1'); b.release('T2'); b.release('T0')
# Expected: T1, T2, T0
expected = ['T1', 'T2', 'T0']
got = [b.acquire() for _ in range(3)]
print(f"Expected: {expected}")
print(f"Got:      {got}")
print("PASS" if got == expected else "FAIL")

# TEST 12: WMR global first-free  
print("\n=== TEST 12: WMR Global first-free ===")
b = FirstFreeBroker()
b.release('W0-T0'); b.release('W0-T1'); b.release('W1-T0'); b.release('W1-T1')
w0t0 = b.acquire(); w0t1 = b.acquire(); w1t0 = b.acquire(); w1t1 = b.acquire()
print(f"Assigned: {w0t0}, {w0t1}, {w1t0}, {w1t1}")
# Release W1-T0 first, then W0-T1
b.release('W1-T0'); b.release('W0-T1')
got1 = b.acquire(); got2 = b.acquire()
print(f"Expected: W1-T0, W0-T1")
print(f"Got: {got1}, {got2}")
print("PASS" if got1 == 'W1-T0' and got2 == 'W0-T1' else "FAIL")
