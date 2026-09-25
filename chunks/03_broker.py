# ================================================================================================================
# BROKER ARCHITECTURE
# ================================================================================================================
import heapq

class FirstFreeBroker:
    def __init__(self):
        self._free_heap = []
        self._seq = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._known_resources = set()
        self._dead_resources = set()

    def add_resource(self, resource_id: str):
        with self._lock:
            if resource_id not in self._known_resources:
                self._known_resources.add(resource_id)
                self._seq += 1
                heapq.heappush(self._free_heap, (self._seq, resource_id))
                self._condition.notify_all()

    async def acquire(self) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._acquire_sync)

    def _acquire_sync(self) -> str:
        with self._lock:
            while not self._free_heap:
                self._condition.wait()
            _, resource_id = heapq.heappop(self._free_heap)
            return resource_id

    def release(self, resource_id: str):
        with self._lock:
            if resource_id in self._known_resources and resource_id not in self._dead_resources:
                # Prevent duplicate release
                if not any(res_id == resource_id for _, res_id in self._free_heap):
                    self._seq += 1
                    heapq.heappush(self._free_heap, (self._seq, resource_id))
                    print(f"[BROKER] Released {resource_id}")
                    self._condition.notify_all()

    def fail(self, resource_id: str):
        with self._lock:
            self._dead_resources.add(resource_id)
            print(f"[BROKER] Marked {resource_id} DEAD")

    def recover(self, resource_id: str):
        with self._lock:
            if resource_id in self._dead_resources:
                self._dead_resources.remove(resource_id)
                self._seq += 1
                heapq.heappush(self._free_heap, (self._seq, resource_id))
                print(f"[BROKER] Recovered {resource_id}")
                self._condition.notify_all()

    def is_free(self, resource_id: str) -> bool:
        with self._lock:
            return any(res_id == resource_id for _, res_id in self._free_heap)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total": len(self._known_resources),
                "free": len(self._free_heap),
                "dead": len(self._dead_resources),
                "free_items": [r for _, r in self._free_heap]
            }

GEMINI_BROKER = FirstFreeBroker()
WMR_BROKER = FirstFreeBroker()
