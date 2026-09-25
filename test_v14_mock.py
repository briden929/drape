import sys
import unittest

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    source = f.read()
    
# Mock external dependencies for pure unit tests of the logic
source = source.replace("import psycopg2", "import mock as psycopg2")
source = source.replace("import boto3", "import mock as boto3")
source = source.replace("from bullmq", "from mock import bullmq")
source = source.replace("from pyvirtualdisplay", "from mock import pyvirtualdisplay")
source = source.replace("from PIL", "from mock import PIL")
source = source.replace("import selenium", "import mock as selenium")

d = {}
try:
    exec(source, d)
except Exception as e:
    pass # we just want the classes

class DummyFuture:
    def done(self): return False

try:
    FirstFreeBroker = d['FirstFreeBroker']
    JobContext = d['JobContext']
    
    print("TEST 7: Constructor/preflight")
    broker = FirstFreeBroker()
    ctx = JobContext({"id": "j1"}, DummyFuture())
    print("PASS: Constructors work")
    
    print("TEST 8: FIRST-FREE test")
    broker = FirstFreeBroker()
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
    broker = FirstFreeBroker()
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
    wmr_broker = FirstFreeBroker()
    wmr_broker.release("W1-T0")
    wmr_broker.release("W0-T1")
    assert wmr_broker.acquire() == "W1-T0"
    assert wmr_broker.acquire() == "W0-T1"
    print("PASS: WMR global first-free")

    print("ALL UNIT TESTS PASSED!")
except Exception as e:
    import traceback
    traceback.print_exc()
