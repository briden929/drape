import os
import re

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

# Remove the old WmrWorkerPool from V9
text = re.sub(r'class WmrWorkerPool:.*?(?=wmr_pool = WmrWorkerPool)', '', text, flags=re.DOTALL)
text = re.sub(r'wmr_pool = WmrWorkerPool\(CHROME_WMR_WORKERS\)', '', text)

# Add missing standard imports
imports_to_add = "import types\nimport urllib.request\nimport urllib.error\nimport urllib.parse\n"
text = text.replace("import uuid", "import uuid\n" + imports_to_add)

# Remove `_PooledBorrow` reference if it's in a V9 db function that I don't strictly need,
# or just redefine it if it's needed by `db_borrow()`.
pooled_borrow_code = """
class _PooledBorrow:
    def __init__(self, conn):
        self._conn = conn
        self._returned = False
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def close(self):
        if self._returned: return
        self._returned = True
        try: self._conn.rollback()
        except: pass
        _get_pool().putconn(self._conn)
"""
text = text.replace("def db_borrow():", pooled_borrow_code + "\ndef db_borrow():")

# Fix `main` undefined reference. In V9, `start_novnc_tunnel` uses `main` as a target?
# Let's check what uses `main`. It's probably in `if __name__ == '__main__':` from V9.
# Let's strip the old `if __name__ == '__main__':` block.
text = re.sub(r'if __name__ == [\'"]__main__[\'"]:.*', '', text, flags=re.DOTALL)

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)

# Append the correct entrypoint
entry = """
if __name__ == "__main__":
    start_worker()
"""
with open(FINAL, "a", encoding="utf-8") as f:
    f.write(entry)
