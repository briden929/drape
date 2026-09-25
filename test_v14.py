import sys
# Path to desktop to import the script
sys.path.append("C:\\Users\\PC\\Desktop")

try:
    import FULL_QUEUE_WORKER_V14_FINAL as v14
    
    print("TEST 7: Constructor/preflight")
    broker = v14.FirstFreeBroker()
    class DummyFuture:
        def done(self): return False
    ctx = v14.JobContext({"id": "j1"}, DummyFuture())
    gw = v14.GeminiWorker(0)
    gwp = v14.GeminiWorkerPool(1)
    wwp = v14.WmrWorkerPool(1)
    print("PASS: Constructors work")
    
    print("TEST 8: FIRST-FREE test")
    broker = v14.FirstFreeBroker()
    broker.release("T2")
    broker.release("T0")
    broker.release("T3")
    broker.release("T1")
    assert broker.acquire() == "T2"
    assert broker.acquire() == "T0"
    assert broker.acquire() == "T3"
    assert broker.acquire() == "T1"
    print("PASS: First-Free strict release order")
    
    print("TEST 9: FIRST-FREE release order under reuse")
    broker = v14.FirstFreeBroker()
    broker.release("T0") # assigned
    broker.acquire()
    broker.release("T1") # assigned
    broker.acquire()
    broker.release("T2") # assigned
    broker.acquire()
    
    broker.release("T1")
    broker.release("T2")
    broker.release("T0")
    assert broker.acquire() == "T1"
    assert broker.acquire() == "T2"
    assert broker.acquire() == "T0"
    print("PASS: First-Free release order under reuse")
    
    print("TEST 12: WMR global first-free")
    wmr_broker = v14.FirstFreeBroker()
    wmr_broker.release("W1-T0")
    wmr_broker.release("W0-T1")
    assert wmr_broker.acquire() == "W1-T0"
    assert wmr_broker.acquire() == "W0-T1"
    print("PASS: WMR global first-free")

    print("ALL UNIT TESTS PASSED!")
except Exception as e:
    import traceback
    traceback.print_exc()
