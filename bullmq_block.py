# 5. Run the worker (BLOCKS — this is the worker's own loop, picking up and processing jobs until you stop it: Runtime → Interrupt execution)

# ----------------------------------------------------------------------------

import asyncio

import json

import os

import subprocess

import sys

import time

import traceback

import uuid

from pathlib import Path

from bullmq import Worker

import credits

import db

import fashion_studio

QUEUE_NAME = 'generations'

REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')

REDIS_KEY_PREFIX = os.environ.get('REDIS_KEY_PREFIX', 'vastralook:')

WORKER_ID = f'queue_worker-{uuid.uuid4().hex[:8]}'



def log(msg, file=None):

    ts = time.strftime('%H:%M:%S')

    print(f'[{ts}] {msg}', file=file)

WORKER_STATE_DIR = Path('/content/queue_worker_bundle/queue_worker_state')

WORKER_STATE_DIR.mkdir(exist_ok=True)

_drive_cookies = Path('/content/drive/MyDrive/gemini-queue-worker/cookies.pkl')

COOKIES_FILE = _drive_cookies if _drive_cookies.parent.parent.exists() else WORKER_STATE_DIR / 'cookies.pkl'

COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

REFS_DIR = WORKER_STATE_DIR / 'refs'

PROFILE_DIR = WORKER_STATE_DIR / 'chrome_profile'

GENERATE_SCRIPT = Path('/content/queue_worker_bundle/gemini_generate.py')

PYTHON_BIN = sys.executable

GENERATION_TIMEOUT_S = 180

LOGIN_TIMEOUT_S = 900

SUBPROCESS_TIMEOUT_S = LOGIN_TIMEOUT_S + GENERATION_TIMEOUT_S + 300



def fetch_generation(gen_id):

    conn = db.borrow()

    try:

        cur = conn.cursor()

        cur.execute('\n            SELECT g.id, g.user_id, g.model_id, g.catalogue_item_id, g.package_id,\n                   g.prompt, g.params, g.attempts, g.max_attempts, g.credits_cost,\n                   ci.hologram_url, ci.thumbnail_url, ci.model_id AS ci_model_id,\n                   pk.primary_outfit_name,\n                   m.image_url AS model_image_url, m.angle_image_url AS model_angle_url\n            FROM image_generations g\n            LEFT JOIN catalogue_items ci ON ci.id = g.catalogue_item_id\n            LEFT JOIN packages pk ON pk.id = COALESCE(g.package_id, ci.package_id)\n            LEFT JOIN models m ON m.id = COALESCE(g.model_id, ci.model_id)\n            WHERE g.id = %s\n            ', (gen_id,))

        row = cur.fetchone()

        if not row:

            return None

        cols = [d[0] for d in cur.description]

        return dict(zip(cols, row))

    finally:

        conn.close()



def resolve_prompt_and_refs(gen):

    params = gen.get('params') or {}

    if isinstance(params, str):

        params = json.loads(params)

    garment_url = params.get('garmentImage') or params.get('garmentUrl') or params.get('garment_image_url') or params.get('garmentImageUrl')

    if not garment_url:

        garment_images = params.get('garmentImages')

        if isinstance(garment_images, list):

            garment_url = next((u for u in garment_images if isinstance(u, str) and u.strip()), None)

    if not garment_url:

        raise ValueError(f"generation {gen['id']}: no garment reference found in params (checked garmentImage/garmentUrl/garment_image_url/garmentImageUrl/garmentImages[0]) — params keys were: {list(params.keys())}")

    model_image_url = params.get('modelImage') or gen.get('model_angle_url') or gen.get('model_image_url')

    hologram_url = params.get('styleImage') or gen.get('hologram_url')

    REFS_DIR.mkdir(parents=True, exist_ok=True)

    garment_path = fashion_studio.download_remote_image(garment_url, REFS_DIR)

    model_image_path = fashion_studio.download_remote_image(model_image_url, REFS_DIR) if model_image_url else None

    hologram_path = fashion_studio.download_remote_image(hologram_url, REFS_DIR) if hologram_url else None

    prompt = gen.get('prompt')

    if not prompt:

        prompt = fashion_studio.fashion_tryon_prompt(has_model=bool(model_image_path))

    return (prompt, garment_path, model_image_path, hologram_path)



def run_generation_subprocess(prompt, garment_path, model_image_path, hologram_path, out_dir):

    out_dir = Path(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    status_file = out_dir / 'status.json'

    cmd = [PYTHON_BIN, str(GENERATE_SCRIPT), '--status-file', str(status_file), '--output-dir', str(out_dir), '--cookies-file', str(COOKIES_FILE), '--profile-dir', str(PROFILE_DIR), '--login-timeout', str(LOGIN_TIMEOUT_S), '--generation-timeout', str(GENERATION_TIMEOUT_S), '--prompt', prompt, '--image-path', garment_path]

    if model_image_path:

        cmd += ['--model-image-path', model_image_path]

    if hologram_path:

        cmd += ['--hologram-image-path', hologram_path]

    gen_id_for_log = out_dir.name

    proc_log_file = out_dir / 'subprocess.log'

    log(f'[{WORKER_ID}] {gen_id_for_log}: launching gemini_generate.py (can take a few minutes; login alone may take up to {LOGIN_TIMEOUT_S}s if cookies are stale)')

    with open(proc_log_file, 'w', encoding='utf-8') as lf:

        proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)

        deadline = time.time() + SUBPROCESS_TIMEOUT_S

        last_phase = None

        seen_vnc_url = False

        while proc.poll() is None:

            if time.time() > deadline:

                proc.kill()

                proc.wait(timeout=10)

                raise RuntimeError(f'gemini_generate.py timed out after {SUBPROCESS_TIMEOUT_S}s')

            if status_file.exists():

                try:

                    live_status = json.loads(status_file.read_text(encoding='utf-8'))

                except Exception:

                    live_status = {}

                vnc_url = live_status.get('vnc_url')

                if vnc_url and (not seen_vnc_url):

                    log(f'[{WORKER_ID}] {gen_id_for_log}: noVNC link (open to log in if needed): {vnc_url}')

                    seen_vnc_url = True

                phase = live_status.get('phase')

                if phase and phase != last_phase:

                    log(f"[{WORKER_ID}] {gen_id_for_log}: phase={phase} {live_status.get('message', '')}".rstrip())

                    last_phase = phase

            time.sleep(3)

    status = {}

    if status_file.exists():

        try:

            status = json.loads(status_file.read_text(encoding='utf-8'))

        except Exception:

            pass

    if proc.returncode != 0 and status.get('phase') != 'done':

        tail = proc_log_file.read_text(encoding='utf-8', errors='replace')[-2000:] if proc_log_file.exists() else ''

        raise RuntimeError(status.get('error') or f'gemini_generate.py exited {proc.returncode}: {tail}')

    if status.get('phase') != 'done':

        raise RuntimeError(status.get('error') or 'generation did not report success')

    return status



def record_dead_letter(gen, failed_reason, attempts_made, max_attempts, error_stack=None):

    conn = db.borrow()

    try:

        cur = conn.cursor()

        summary = json.dumps({'generationId': gen['id']})

        cur.execute("\n            INSERT INTO dead_letter_jobs\n                (queue_name, job_name, generation_id, payload_summary, failed_reason,\n                 attempts_made, status, worker_id, error_stack)\n            VALUES (%s, %s, %s, %s::jsonb, %s, %s, 'open', %s, %s)\n            ", (QUEUE_NAME, 'process-generation', gen['id'], summary, failed_reason[:4000], attempts_made, WORKER_ID, (error_stack or '')[:8000]))

        conn.commit()

    finally:

        conn.close()



async def process(job, job_token):

    gen_id = job.data['generationId']

    log(f'[{WORKER_ID}] picked up generation {gen_id} (attempt {job.attemptsMade + 1})')

    gen = fetch_generation(gen_id)

    if gen is None:

        log(f'[{WORKER_ID}] {gen_id}: no image_generations row found, skipping')

        return {'skipped': 'row_not_found'}

    out_dir = WORKER_STATE_DIR / 'jobs' / gen_id

    try:

        prompt, garment_path, model_image_path, hologram_path = resolve_prompt_and_refs(gen)

        status = run_generation_subprocess(prompt, garment_path, model_image_path, hologram_path, out_dir)

        png_path = status.get('output_image')

        webp_path = status.get('output_image_webp')

        result = fashion_studio.push_generation(png_path, prompt, user_id=gen['user_id'], gen_id=gen_id, webp_path=webp_path, force=True, params={'garmentImage': garment_path, 'modelImage': model_image_path, 'styleImage': hologram_path})

        try:

            credits.settle_look(gen_id)

        except Exception as e:

            log(f'[{WORKER_ID}] {gen_id}: settle_look failed (non-fatal): {e}', file=sys.stderr)

        log(f"[{WORKER_ID}] {gen_id}: done -> {result['output_url']}")

        return {'output_url': result['output_url'], 'webp_url': result['webp_url']}

    except Exception as e:

        attempts_made = job.attemptsMade + 1

        max_attempts = job.opts.get('attempts') or 1

        is_final = attempts_made >= max_attempts

        log(f'[{WORKER_ID}] {gen_id}: attempt {attempts_made}/{max_attempts} failed: {e}', file=sys.stderr)

        if is_final:

            try:

                record_dead_letter(gen, str(e), attempts_made, max_attempts, traceback.format_exc())

            except Exception as dlq_err:

                log(f'[{WORKER_ID}] {gen_id}: DLQ insert also failed: {dlq_err}', file=sys.stderr)

            try:

                credits.refund_look(gen_id, str(e)[:500])

            except Exception as refund_err:

                log(f'[{WORKER_ID}] {gen_id}: refund also failed: {refund_err}', file=sys.stderr)

        raise



async def main():

    log(f'[{WORKER_ID}] connecting to {REDIS_URL} queue={QUEUE_NAME!r} prefix={REDIS_KEY_PREFIX!r}')

    worker = Worker(QUEUE_NAME, process, {'connection': REDIS_URL, 'prefix': REDIS_KEY_PREFIX, 'concurrency': 1})

    log(f'[{WORKER_ID}] waiting for jobs (Ctrl+C to stop)...')

    try:

        while True:

            await asyncio.sleep(3600)

    except (KeyboardInterrupt, asyncio.CancelledError):

        pass

    finally:

        await worker.close()

if __name__ == '__main__':

    import nest_asyncio

    nest_asyncio.apply()

    asyncio.run(main())


now please that improved in V8 becouse now we have introduse direct reddice connect 

also befor process how many in que job that also print please combined best V9 code create that login check if not login complite login manage after that all process manage & output in reddies 

