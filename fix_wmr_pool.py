with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("""
    add('''
class WmrWorkerPool:
    def __init__(self, num_profiles):
        self.num_profiles = num_profiles
        self.threads = {}
        
    def start_all(self):
        for i in range(self.num_profiles):
            self.threads[i] = WmrDriverThread(i)
            self.threads[i].start()
            for t in range(WMR_TABS_PER_PROFILE):
                WMR_BROKER.release(f"W{i}-T{t}")

    async def execute_async(self, resource_id, func, *args):
        profile_id = int(resource_id.split('-')[0][1:])
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        cfut = concurrent.futures.Future()
        
        def _done(f):
            if loop.is_closed():
                return
            try:
                res = f.result()
                loop.call_soon_threadsafe(fut.set_result, res)
            except Exception as e:
                loop.call_soon_threadsafe(fut.set_exception, e)
                
        cfut.add_done_callback(_done)
        self.threads[profile_id].cmd_queue.put((func, args, cfut))
        return await fut
''')
""")
