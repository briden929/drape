class GeminiWorkerPool:
    def __init__(self, max_workers: int = MAX_CONCURRENT_TABS):
        self.max_workers = max_workers
        self.tabs = []
        self.queue = asyncio.Queue()
        self.lock = asyncio.Lock()
        self.active_jobs = {}
        
    async def initialize(self):
        # Create persistent Chrome driver and exact tabs
        pass
        
    async def get_free_tab(self):
        return await self.queue.get()
        
    async def release_tab(self, tid: int, job_id: str):
        async with self.lock:
            if self.active_jobs.get(tid) == job_id:
                self.active_jobs[tid] = None
                await self.queue.put(tid)
