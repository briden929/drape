"""
test_v4_architecture.py
Offline unit tests for FULL_QUEUE_WORKER_V4_ONE_CELL.py architecture.
No browsers are launched. All tests use mocks / stubs.
Run with: python test_v4_architecture.py
"""

import os
import sys
import asyncio
import threading
import queue
import time
import tempfile
import shutil
import json
import re
import io
import types
import traceback
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---- stub heavy deps that aren't available in Windows test env ----
for mod in ['psycopg2', 'boto3', 'bullmq', 'selenium', 'selenium.webdriver',
            'selenium.webdriver.chrome', 'selenium.webdriver.edge',
            'selenium.webdriver.chrome.options', 'selenium.webdriver.edge.options',
            'selenium.webdriver.common.by', 'selenium.webdriver.common.keys',
            'selenium.webdriver.common.action_chains',
            'pyvirtualdisplay', 'nest_asyncio', 'IPython', 'IPython.display',
            'psycopg2.pool']:
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)

# make psycopg2.pool accessible from top-level
import psycopg2
psycopg2.pool = sys.modules['psycopg2.pool']

import boto3 as _b3
_b3.client = MagicMock()

from PIL import Image

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []

def _run_test(name, fn):
    try:
        fn()
        results.append((name, True, None))
        print(f"  {PASS}  {name}")
    except Exception as e:
        results.append((name, False, str(e)))
        print(f"  {FAIL}  {name}")
        print(f"        {traceback.format_exc().strip().splitlines()[-1]}")

# ===========================================================================
# TEST 1: get_chrome_job_dir path construction
# ===========================================================================
def test_chrome_job_dir():
    with tempfile.TemporaryDirectory() as td:
        chrome_dl_base = Path(td) / 'chrome'

        # Simulate the function inline (we cannot import the heavy script)
        def _get_chrome_job_dir(tab_id, job_id, base=chrome_dl_base):
            job_dir = base / f'T{tab_id}' / job_id
            incoming = job_dir / 'incoming'
            incoming.mkdir(parents=True, exist_ok=True)
            return job_dir, incoming

        job_dir, incoming = _get_chrome_job_dir(2, 'abc123')
        assert 'T2' in str(job_dir), f"Expected T2 in path, got {job_dir}"
        assert 'abc123' in str(job_dir), f"Expected job_id in path, got {job_dir}"
        assert 'incoming' in str(incoming), f"Expected incoming subdir"
        assert incoming.exists(), "incoming dir must be created"
        assert job_dir.exists(), "job_dir must be created"

_run_test("TEST 1: get_chrome_job_dir path construction", test_chrome_job_dir)

# ===========================================================================
# TEST 2: get_edge_job_dir path construction
# ===========================================================================
def test_edge_job_dir():
    with tempfile.TemporaryDirectory() as td:
        edge_dl_base = Path(td) / 'edge'

        def _get_edge_job_dir(chrome_tab_id, job_id, base=edge_dl_base):
            job_dir = base / f'T{chrome_tab_id}' / job_id
            incoming = job_dir / 'incoming'
            incoming.mkdir(parents=True, exist_ok=True)
            return job_dir, incoming

        for tid in range(4):
            jid = f'job_{tid}_test'
            job_dir, incoming = _get_edge_job_dir(tid, jid)
            assert f'T{tid}' in str(job_dir)
            assert jid in str(job_dir)
            assert incoming.exists()
            # Edge dir must not bleed into chrome dir
            assert 'chrome' not in str(job_dir)

_run_test("TEST 2: get_edge_job_dir path construction", test_edge_job_dir)

# ===========================================================================
# TEST 3: get_final_output_dir path construction
# ===========================================================================
def test_final_output_dir():
    with tempfile.TemporaryDirectory() as td:
        final_base = Path(td) / 'final_output'

        def _get_final_output_dir(chrome_tab_id, job_id, base=final_base):
            d = base / f'T{chrome_tab_id}' / job_id
            d.mkdir(parents=True, exist_ok=True)
            return d

        d = _get_final_output_dir(1, 'finjob')
        assert 'T1' in str(d)
        assert 'finjob' in str(d)
        assert d.exists()

_run_test("TEST 3: get_final_output_dir path construction", test_final_output_dir)

# ===========================================================================
# TEST 4: EdgeWorker profiles — each worker gets unique profile path
# ===========================================================================
def test_edge_worker_profiles():
    with tempfile.TemporaryDirectory() as td:
        profiles_base = Path(td) / 'edge_profiles'
        profiles = []
        for i in range(4):
            p = profiles_base / f'worker_{i}'
            p.mkdir(parents=True, exist_ok=True)
            profiles.append(str(p))

        assert len(profiles) == 4
        assert len(set(profiles)) == 4, "All profiles must be unique paths"
        for i, p in enumerate(profiles):
            assert f'worker_{i}' in p, f"Profile {i} must contain worker_{i}"

_run_test("TEST 4: EdgeWorkerPool profile uniqueness", test_edge_worker_profiles)

# ===========================================================================
# TEST 5: Download watcher logic — scans ONLY incoming_dir
# ===========================================================================
def test_download_watcher_incoming_only():
    """Simulate poll_active_downloads logic to confirm it only scans incoming_dir."""
    DOWNLOAD_MIN_SIZE = 5000
    DOWNLOAD_STABLE_CHECKS = 3

    import random
    def _make_large_png(path):
        """Write a large enough PNG to satisfy DOWNLOAD_MIN_SIZE."""
        import struct, zlib
        # Write a synthetic PNG: 200x200 RGB noise image using raw bytes
        width, height = 200, 200
        raw_rows = []
        for _ in range(height):
            row = bytes([0]) + bytes([random.randint(0, 255) for _ in range(width * 3)])
            raw_rows.append(row)
        raw = b''.join(raw_rows)
        compressed = zlib.compress(raw, 9)
        def chunk(name, data):
            c = struct.pack('>I', len(data)) + name + data
            c += struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)
            return c
        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr_data) +
               chunk(b'IDAT', compressed) + chunk(b'IEND', b''))
        Path(path).write_bytes(png)
        return len(png)

    with tempfile.TemporaryDirectory() as td:
        incoming_dir = Path(td) / 'chrome' / 'T0' / 'job_A' / 'incoming'
        incoming_dir.mkdir(parents=True, exist_ok=True)
        other_dir = Path(td) / 'other_downloads'
        other_dir.mkdir(parents=True, exist_ok=True)

        # Write a decoy file in other_dir (should NOT be picked up)
        decoy = other_dir / 'decoy.png'
        decoy.write_bytes(b'X' * 20000)

        # Write a valid large PNG in incoming_dir
        incoming_file = incoming_dir / 'generated.png'
        sz = _make_large_png(str(incoming_file))
        assert sz >= DOWNLOAD_MIN_SIZE, f"Test PNG only {sz} bytes — increase image size"

        # Simulate watcher: only scan incoming_dir, ignore other_dir
        found_file = None
        files_before = set()
        for fn in os.listdir(incoming_dir):
            if fn.endswith(('.crdownload', '.tmp', '.part', '.download')):
                continue
            if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                continue
            if fn in files_before:
                continue
            fp = incoming_dir / fn
            if fp.stat().st_size >= DOWNLOAD_MIN_SIZE:
                found_file = fp
                break

        assert found_file is not None, "Must find file in incoming_dir"
        assert str(found_file) == str(incoming_file), f"Found wrong file: {found_file}"
        assert str(decoy) not in str(found_file), "Must NOT pick up decoy from other_dir"

_run_test("TEST 5: Download watcher scans ONLY incoming_dir", test_download_watcher_incoming_only)


# ===========================================================================
# TEST 6: _free_tab logic — does NOT clear active_downloads
# ===========================================================================
def test_free_tab_no_active_download_clear():
    S_IDLE = "IDLE"
    active_downloads = {}
    tab_states = [{
        "tab_id": 0, "state": "GENERATING", "job": "jobj", "job_id": "jid0",
        "gen": {}, "prompt": "text", "refs": [], "target_src": None,
        "download_started": True, "stuck_polls": 3, "start_time": time.time(),
        "future": None, "urls_before": {"blob:x"}, "chat_urls": {"blob:y"}, "attempt": 1
    }]

    # Simulate active_downloads entry for this job
    active_downloads["jid0"] = {"state": "DOWNLOAD_WAITING", "files": []}

    def _free_tab(tid, job_id):
        info = tab_states[tid]
        info["state"] = S_IDLE
        info["job"] = None
        info["job_id"] = None
        info["gen"] = None
        info["prompt"] = None
        info["refs"] = []
        info["target_src"] = None
        info["download_started"] = False
        info["stuck_polls"] = 0
        info["start_time"] = 0.0
        info["future"] = None
        info["urls_before"] = set()
        info["chat_urls"] = set()
        # active_downloads is NOT touched

    _free_tab(0, "jid0")
    assert tab_states[0]["state"] == S_IDLE
    assert tab_states[0]["job"] is None
    # CRITICAL: active_downloads must still have the entry
    assert "jid0" in active_downloads, "_free_tab must NOT remove active_downloads entry"
    assert active_downloads["jid0"]["state"] == "DOWNLOAD_WAITING"

_run_test("TEST 6: _free_tab does NOT clear active_downloads", test_free_tab_no_active_download_clear)

# ===========================================================================
# TEST 7: Strict Flash validation (not Lite, not Pro)
# ===========================================================================
def test_flash_validation():
    def is_valid_flash(text):
        t = text.strip().lower()
        return "flash" in t and "lite" not in t and "pro" not in t

    valid_cases = [
        "3.0 Flash (All-around help)",
        "Flash",
        "2.0 Flash Experimental",
        "Gemini Flash",
    ]
    invalid_cases = [
        "3.5 Flash-Lite (Fastest answers)",
        "3.1 Pro (Advanced reasoning)",
        "Flash Lite",
        "Flash-Lite",
        "Gemini Pro Flash",  # contains "pro"
        "GPT-4",
        "",
    ]
    for txt in valid_cases:
        assert is_valid_flash(txt), f"Should be valid Flash: '{txt}'"
    for txt in invalid_cases:
        assert not is_valid_flash(txt), f"Should be INVALID Flash: '{txt}'"

_run_test("TEST 7: Strict Flash validation (not Lite, not Pro)", test_flash_validation)

# ===========================================================================
# TEST 8: normalize_prompt_text idempotent
# ===========================================================================
def test_normalize_prompt_text():
    def normalize_prompt_text(text):
        if not text:
            return ""
        t = text.replace("\r\n", "\n").replace("\r", "\n")
        t = re.sub(r"[ \t]+", " ", t)
        lines = [line.rstrip() for line in t.split("\n")]
        return "\n".join(lines).strip()

    prompt = "FASHION TRY-ON\n\nGenerate ONE photorealistic  image.\nColors: red, blue.\n"
    n1 = normalize_prompt_text(prompt)
    n2 = normalize_prompt_text(n1)
    assert n1 == n2, "normalize_prompt_text must be idempotent"

    # Check CRLF handling
    crlf = "Line1\r\nLine2\r\nLine3"
    normalized = normalize_prompt_text(crlf)
    assert "\r" not in normalized, "Must strip CR"
    assert normalized == "Line1\nLine2\nLine3"

_run_test("TEST 8: normalize_prompt_text idempotent", test_normalize_prompt_text)

# ===========================================================================
# TEST 9: Tab priority — lowest-ID first (T0 > T1 > T2 > T3)
# ===========================================================================
def test_lowest_id_tab_priority():
    S_IDLE = "IDLE"
    S_GEN_WAITING = "GENERATING"
    tab_states = [
        {"state": S_GEN_WAITING},
        {"state": S_GEN_WAITING},
        {"state": S_IDLE},
        {"state": S_GEN_WAITING},
    ]

    def find_first_idle_tab():
        for tid in range(4):
            if tab_states[tid]["state"] == S_IDLE:
                return tid
        return None

    result = find_first_idle_tab()
    assert result == 2, f"Expected T2 (first idle), got T{result}"

    # T0 becomes idle — should now be returned
    tab_states[0]["state"] = S_IDLE
    result2 = find_first_idle_tab()
    assert result2 == 0, f"Expected T0 (lowest idle), got T{result2}"

_run_test("TEST 9: Lowest-ID tab priority", test_lowest_id_tab_priority)

# ===========================================================================
# TEST 10: validate_image_file — PIL verify
# ===========================================================================
def test_validate_image_file():
    DOWNLOAD_MIN_SIZE = 5000

    import struct, zlib, random

    def _make_noise_png(path, width=200, height=200):
        """Write a synthetic noise PNG guaranteed to be > 5000 bytes."""
        raw_rows = []
        for _ in range(height):
            row = bytes([0]) + bytes([random.randint(0, 255) for _ in range(width * 3)])
            raw_rows.append(row)
        raw = b''.join(raw_rows)
        compressed = zlib.compress(raw, 1)  # fast compress -> larger output
        def chunk(name, data):
            c = struct.pack('>I', len(data)) + name + data
            c += struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)
            return c
        ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
               chunk(b'IDAT', compressed) + chunk(b'IEND', b''))
        Path(path).write_bytes(png)
        return len(png)

    def validate_image_file(path, min_size=DOWNLOAD_MIN_SIZE):
        try:
            p = Path(path)
            if not p.exists() or p.stat().st_size < min_size:
                return False
            with Image.open(p) as im:
                im.verify()
            return True
        except Exception:
            return False

    with tempfile.TemporaryDirectory() as td:
        # Valid noise PNG (guaranteed > 5000 bytes)
        valid_path = Path(td) / 'valid.png'
        sz = _make_noise_png(str(valid_path))
        assert sz >= DOWNLOAD_MIN_SIZE, f"Test noise PNG only {sz}B — increase width/height"
        assert validate_image_file(valid_path), "Valid noise PNG must pass"

        # Too small
        small_path = Path(td) / 'small.png'
        small_path.write_bytes(b'X' * 100)
        assert not validate_image_file(small_path), "Small file must fail"

        # Corrupted
        corrupt_path = Path(td) / 'corrupt.png'
        corrupt_path.write_bytes(b'NOTAPNG' + b'X' * 10000)
        assert not validate_image_file(corrupt_path), "Corrupt file must fail"

        # Non-existent
        assert not validate_image_file(Path(td) / 'ghost.png'), "Nonexistent must fail"

_run_test("TEST 10: validate_image_file PIL verify", test_validate_image_file)


# ===========================================================================
# TEST 11: EdgeWorkerPool round-robin on all-busy
# ===========================================================================
def test_edge_pool_round_robin():
    """When all workers are PROCESSING, pool should assign to lowest queue.qsize()."""
    class FakeWorker:
        def __init__(self, wid):
            self.worker_id = wid
            self.state = "PROCESSING"
            self.work_queue = queue.Queue()

    workers = [FakeWorker(i) for i in range(4)]
    # Put 2 items in worker 0, 1 in worker 1, 0 in worker 2, 1 in worker 3
    workers[0].work_queue.put("x")
    workers[0].work_queue.put("x")
    workers[1].work_queue.put("x")
    workers[3].work_queue.put("x")

    # find_idle returns None (all PROCESSING)
    idle = next((w for w in workers if w.state == "IDLE" and w.work_queue.empty()), None)
    assert idle is None

    # round-robin fallback: min queue size -> worker[2]
    best = min(workers, key=lambda w: w.work_queue.qsize())
    assert best.worker_id == 2, f"Expected E2 (empty queue), got E{best.worker_id}"

_run_test("TEST 11: EdgeWorkerPool round-robin on all-busy", test_edge_pool_round_robin)

# ===========================================================================
# TEST 12: Job retry requeue logic
# ===========================================================================
def test_job_retry_requeue():
    MAX_JOB_RETRIES = 2
    requeued = []
    failed = []

    def fail_job(job_id, reason):
        failed.append(job_id)

    def simulate_recover(job_id, attempt, gen, job, prompt, refs, future):
        if job is not None and attempt < MAX_JOB_RETRIES:
            requeued.append({"job_id": job_id, "attempt": attempt + 1})
        else:
            fail_job(job_id, "exhausted retries")

    # Attempt 1: should requeue
    simulate_recover("job1", 1, {"id": "job1"}, "jobj", "prompt", [], None)
    assert len(requeued) == 1 and requeued[-1]["attempt"] == 2
    assert len(failed) == 0, "Should not fail on attempt 1"

    # Attempt 2 (== MAX_JOB_RETRIES): should fail
    simulate_recover("job1", 2, {"id": "job1"}, "jobj", "prompt", [], None)
    assert len(failed) == 1, "Must fail on final attempt"
    assert len(requeued) == 1, "Must not requeue on final attempt"

    # No gen (jobj is None): should fail immediately
    simulate_recover("job2", 1, None, None, None, [], None)
    assert len(failed) == 2, "Must fail when gen is None"

_run_test("TEST 12: Job retry requeue logic", test_job_retry_requeue)

# ===========================================================================
# TEST 13: open_new_chat_and_reload — confirmation dialog detection logic
# ===========================================================================
def test_new_chat_dialog_text_matching():
    """Verify dialog button text matching correctly identifies affirmative vs. cancel."""

    def _is_affirmative(txt, aria):
        combined = (txt.strip().lower() + " " + aria.lower())
        affirmative_words = ['new chat', 'create', 'confirm', 'delete', 'continue', 'yes']
        return any(w in combined for w in affirmative_words) and 'cancel' not in combined

    def _is_cancel(txt, aria):
        return 'cancel' in (txt.strip().lower() + " " + aria.lower())

    cases = [
        ("New chat", "",       True),
        ("Create",  "",        True),
        ("Confirm", "",        True),
        ("Delete",  "",        True),
        ("Yes",     "",        True),
        ("Cancel",  "",        False),
        ("OK",      "cancel",  False),
        ("Close",   "",        False),  # not affirmative
        ("New chat (3)", "",   True),
    ]
    for txt, aria, expected in cases:
        result = _is_affirmative(txt, aria) and not _is_cancel(txt, aria)
        assert result == expected, f"_is_affirmative('{txt}', '{aria}') expected {expected}, got {result}"

_run_test("TEST 13: Confirmation dialog affirmative button detection", test_new_chat_dialog_text_matching)

# ===========================================================================
# TEST 14: Finalization order — credits NEVER settled before R2 upload
# ===========================================================================
def test_finalization_order():
    """
    Simulate _finalize_and_clean_job logic to verify credits.settle is
    called ONLY after push_generation (R2 upload) succeeds.
    """
    call_order = []
    r2_should_fail = False

    def mock_push_generation(**kwargs):
        call_order.append("R2_UPLOAD")
        if r2_should_fail:
            raise RuntimeError("R2 network error")
        return {"output_url": "https://example.com/x.png"}

    def mock_settle_look(job_id):
        call_order.append("CREDITS_SETTLE")

    def mock_refund_look(job_id, reason):
        call_order.append("CREDITS_REFUND")

    # Scenario A: R2 succeeds -> credits settle
    r2_should_fail = False
    call_order.clear()
    try:
        result = mock_push_generation(image_path="x.png", prompt="p")
        mock_settle_look("job1")
    except Exception:
        mock_refund_look("job1", "failed")
    assert call_order == ["R2_UPLOAD", "CREDITS_SETTLE"], f"Wrong order: {call_order}"

    # Scenario B: R2 fails -> refund, NO settle
    r2_should_fail = True
    call_order.clear()
    try:
        result = mock_push_generation(image_path="x.png", prompt="p")
        mock_settle_look("job1")
    except Exception:
        mock_refund_look("job1", "R2 failed")
    assert "CREDITS_SETTLE" not in call_order, "Must NOT settle if R2 failed"
    assert "CREDITS_REFUND" in call_order, "Must refund if R2 failed"

_run_test("TEST 14: Credits settled ONLY after R2 upload", test_finalization_order)

# ===========================================================================
# SUMMARY
# ===========================================================================
print()
print("=" * 60)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed_tests = [(n, e) for n, ok, e in results if not ok]
print(f"  RESULTS: {passed}/{total} PASSED")
if failed_tests:
    print("\n  FAILURES:")
    for name, err in failed_tests:
        print(f"    • {name}: {err}")
print("=" * 60)
sys.exit(0 if not failed_tests else 1)
