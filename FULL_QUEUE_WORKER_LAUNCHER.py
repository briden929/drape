# @title FULL_QUEUE_WORKER_LAUNCHER
# ============================================================================
# ONE launcher cell for FULL_QUEUE_WORKER_FINAL.py.
#
# This cell does NOT duplicate any worker logic. It:
#   1. Loads environment/secrets (Colab Secrets if available, else os.environ).
#   2. Verifies required environment variables are present BEFORE the heavy
#      Chrome/Xvfb/noVNC bootstrap in FULL_QUEUE_WORKER_FINAL.py even starts.
#   3. Loads (execs) FULL_QUEUE_WORKER_FINAL.py as a module -- NOT as
#      __main__, so its own `if __name__ == '__main__':` block does not
#      also try to start the worker a second time.
#   4. Calls start_worker() explicitly and awaits the returned task at the
#      TOP LEVEL of this cell, so IPython's autoawait keeps the notebook's
#      already-running event loop alive on it (no asyncio.run() is ever
#      called here while a loop is running).
#   5. Surfaces any worker exception with a full traceback instead of
#      letting it disappear into an unobserved task.
#
# Paste this entire cell's contents into one Colab cell and run it (after
# FULL_QUEUE_WORKER_FINAL.py has been uploaded/placed next to it, e.g. via
# Google Drive or a repo checkout).
# ============================================================================

import os
import sys
import traceback

WORKER_FILE = "FULL_QUEUE_WORKER_FINAL.py"

# --- Step 1/2: load secrets (Colab Secrets userdata takes precedence when
# available) and verify everything the worker itself requires is present,
# so a missing secret fails in <1s instead of after minutes of bootstrap. ---
_REQUIRED_SECRETS = [
    "DATABASE_URL",
    "REDIS_URL",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_PUBLIC_URL",
]

try:
    from google.colab import userdata  # type: ignore
    for _k in _REQUIRED_SECRETS:
        if not os.environ.get(_k):
            try:
                _v = userdata.get(_k)
                if _v:
                    os.environ[_k] = _v
            except Exception:
                pass
except Exception:
    pass  # not running in Colab, or Colab Secrets not configured -- fall through to plain os.environ

_missing = [k for k in _REQUIRED_SECRETS if not os.environ.get(k)]
if _missing:
    raise RuntimeError(
        f"[LAUNCHER] Missing required environment variables: {', '.join(_missing)}. "
        f"Set them via Colab Secrets or os.environ before running this cell."
    )
print(f"[LAUNCHER] All {len(_REQUIRED_SECRETS)} required secrets are present.")

# --- Step 3: load FULL_QUEUE_WORKER_FINAL.py's top-level code (bootstrap,
# secrets, Chrome/noVNC setup, Google login, DOM engine, broker, BullMQ
# wiring, etc.) into its own namespace WITHOUT letting its bottom
# `if __name__ == '__main__':` block auto-start the worker a second time. ---
if not os.path.exists(WORKER_FILE):
    raise FileNotFoundError(f"[LAUNCHER] {WORKER_FILE} not found next to this launcher.")

print(f"[LAUNCHER] Loading {WORKER_FILE} ...")
_worker_ns = {"__name__": "full_queue_worker_final", "__file__": os.path.abspath(WORKER_FILE)}
with open(WORKER_FILE, "r", encoding="utf-8") as _f:
    _worker_src = _f.read()
exec(compile(_worker_src, WORKER_FILE, "exec"), _worker_ns)
print("[LAUNCHER] Worker module loaded.")

start_worker = _worker_ns["start_worker"]

# --- Step 4/5: start the worker and keep this cell (and therefore the
# notebook's event loop) alive on it, surfacing any crash loudly. ---
print("[LAUNCHER] Starting worker...")
worker_task = start_worker()
try:
    await worker_task
except Exception:
    print("=" * 70)
    print("[LAUNCHER] WORKER TASK RAISED")
    print("=" * 70)
    traceback.print_exc()
    raise
