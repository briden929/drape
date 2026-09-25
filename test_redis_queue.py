# ============================================================================
# test_redis_queue.py — PHASE 2A: Redis/BullMQ queue discovery, INSPECTION ONLY
#
# Answers exactly one question: "Is there currently any job in the
# generations queue?" Connects to Redis, reads job counts, and lists safe
# metadata for waiting jobs. It never starts a Worker, never calls
# moveToActive/process/complete/fail on any job, and never touches Chrome,
# Gemini, WMR, R2, DB finalization, or credits.
#
# Run standalone: python test_redis_queue.py
# (or paste into its own Colab cell — it does not import or exec
# FULL_QUEUE_WORKER_FINAL.py, so it cannot accidentally start production.)
# ============================================================================

import asyncio
import os
from urllib.parse import urlparse

from bullmq import Queue

QUEUE_NAME = os.environ.get("QUEUE_NAME", "generations")
REDIS_KEY_PREFIX = os.environ.get("REDIS_KEY_PREFIX")
REDIS_URL = os.environ.get("REDIS_URL")


def _redis_connection_opts(redis_url: str) -> dict:
    """Same parsing FULL_QUEUE_WORKER_FINAL.py uses: rediss:// -> ssl=True
    (NOT tls={} — redis-py's Redis() has no `tls` kwarg, only `ssl`)."""
    u = urlparse(redis_url or "")
    opts = {"host": u.hostname or "localhost", "port": u.port or 6379}
    if u.password:
        opts["password"] = u.password
    if u.scheme == "rediss":
        opts["ssl"] = True
    return opts


def _safe_job_summary(job) -> dict:
    """Only the fields explicitly whitelisted for this test. Never dumps
    job.data wholesale — no credentials, cookies, or tokens can leak
    through this even if job payloads ever grow to include them."""
    data = job.data if isinstance(job.data, dict) else {}
    opts = job.opts if isinstance(job.opts, dict) else {}
    return {
        "job_id": job.id,
        "name": job.name,
        "generation_id": data.get("generationId") or data.get("id"),
        "timestamp": job.timestamp,
        "attempts_made": job.attemptsMade,
        "max_attempts": opts.get("attempts"),
    }


async def main() -> None:
    print("=" * 60)
    print("REDIS CONNECTION TEST")
    print("=" * 60)

    if not REDIS_URL:
        print("REDIS CONNECTION: FAIL")
        print("Reason: REDIS_URL is not set in the environment.")
        return

    real_opts = _redis_connection_opts(REDIS_URL)
    connection_opts = {"connection": real_opts}
    if REDIS_KEY_PREFIX:
        connection_opts["prefix"] = REDIS_KEY_PREFIX

    queue = None
    try:
        queue = Queue(QUEUE_NAME, connection_opts)

        # PING check
        pong = await queue.client.ping()
        print(f"PING -> {'PONG' if pong else pong}")
        print("REDIS CONNECTION: PASS")

        print()
        print("=" * 60)
        print("REDIS / BULLMQ QUEUE STATUS")
        print("=" * 60)
        print(f"Queue: {QUEUE_NAME}")

        counts = await queue.getJobCounts()
        waiting = counts.get("waiting", 0)
        active = counts.get("active", 0)
        delayed = counts.get("delayed", 0)
        completed = counts.get("completed", 0)
        failed = counts.get("failed", 0)
        prioritized = counts.get("prioritized", 0)
        waiting_children = counts.get("waiting-children", 0)

        print(f"Waiting:          {waiting}")
        print(f"Active:           {active}")
        print(f"Delayed:          {delayed}")
        print(f"Completed:        {completed}")
        print(f"Failed:           {failed}")
        print(f"Prioritized:      {prioritized}")
        print(f"Waiting Children: {waiting_children}")
        print("=" * 60)

        if waiting == 0 and active == 0:
            print("\U0001F7E2 QUEUE EMPTY — REDIS CONNECTION WORKING")
        if waiting > 0:
            print("\U0001F7E1 JOBS AVAILABLE IN QUEUE")
        if active > 0:
            print("\U0001F535 JOBS CURRENTLY ACTIVE")

        job_summaries = []
        if waiting > 0:
            # INSPECTION ONLY — getWaiting() reads the waiting list, it does
            # not move jobs to active or mutate their state in any way.
            waiting_jobs = await queue.getWaiting(0, min(waiting, 50) - 1)
            for job in waiting_jobs:
                summary = _safe_job_summary(job)
                job_summaries.append(summary)
                print()
                print("=" * 60)
                print("\U0001F4E6 WAITING JOB")
                print("=" * 60)
                print(f"Job ID:          {summary['job_id']}")
                print(f"Name:            {summary['name']}")
                print(f"Generation ID:   {summary['generation_id']}")
                print(f"Attempts Made:   {summary['attempts_made']}")
                print(f"Max Attempts:    {summary['max_attempts']}")
                print(f"Timestamp:       {summary['timestamp']}")
                print("=" * 60)

        print()
        print("=" * 60)
        print("FINAL RESULT")
        print("=" * 60)
        print("REDIS CONNECTION: PASS")
        print()
        print(f"QUEUE: {QUEUE_NAME}")
        print()
        print(f"WAITING: {waiting}")
        print(f"ACTIVE: {active}")
        print(f"DELAYED: {delayed}")
        print(f"COMPLETED: {completed}")
        print(f"FAILED: {failed}")
        print(f"PRIORITIZED: {prioritized}")
        print(f"WAITING-CHILDREN: {waiting_children}")
        print()
        print(f"JOBS AVAILABLE: {'YES' if waiting > 0 else 'NO'}")
        if job_summaries:
            print()
            print("JOB IDS:")
            for s in job_summaries:
                print(f"  {s['job_id']}")
            print()
            print("GENERATION IDS:")
            for s in job_summaries:
                print(f"  {s['generation_id']}")

    except Exception as e:
        print("REDIS CONNECTION: FAIL")
        print(f"\U0001F534 REDIS CONNECTION FAILED: {type(e).__name__}: {e}")
    finally:
        if queue is not None:
            await queue.close()


if __name__ == "__main__":
    try:
        asyncio.get_running_loop()
        # Already inside a running loop (e.g. pasted into a Colab cell that
        # has one) — schedule instead of nesting a second loop.
        asyncio.create_task(main())
    except RuntimeError:
        asyncio.run(main())
