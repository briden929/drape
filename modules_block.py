# 3. Register db/credits/fashion_studio modules

# ----------------------------------------------------------------------------

import sys, types

_mod_db = types.ModuleType('db')

sys.modules['db'] = _mod_db

exec(compile((

    'import contextlib\n'

    'import os\n'

    'import threading\n'

    'import psycopg2\n'

    'from psycopg2 import pool as _pgpool\n'

    "DATABASE_URL = os.environ.get('DATABASE_URL')\n"

    '_pool = None\n'

    '_pool_lock = threading.Lock()\n'

    '_last_used = {}\n'

    '\n'

    'def _get_pool():\n'

    '    global _pool\n'

    '    if _pool is None:\n'

    '        with _pool_lock:\n'

    '            if _pool is None:\n'

    "                _pool = _pgpool.ThreadedConnectionPool(minconn=1, maxconn=24, dsn=DATABASE_URL, connect_timeout=10, options='-c statement_timeout=90000')\n"

    '    return _pool\n'

    '_PING_AFTER_IDLE_S = 60\n'

    '\n'

    'def _mark_used(conn):\n'

    '    import time\n'

    '    if len(_last_used) > 64:\n'

    '        _last_used.clear()\n'

    '    _last_used[id(conn)] = time.time()\n'

    '\n'

    'def _checkout():\n'

    '    import time\n'

    '    p = _get_pool()\n'

    '    for attempt in (1, 2):\n'

    '        conn = p.getconn()\n'

    '        if time.time() - _last_used.get(id(conn), 0) < _PING_AFTER_IDLE_S:\n'

    '            return conn\n'

    '        try:\n'

    '            with conn.cursor() as cur:\n'

    "                cur.execute('SELECT 1')\n"

    '            conn.rollback()\n'

    '            return conn\n'

    '        except Exception:\n'

    '            p.putconn(conn, close=True)\n'

    '            if attempt == 2:\n'

    '                raise\n'

    "    raise RuntimeError('unreachable')\n"

    '\n'

    '@contextlib.contextmanager\n'

    'def connection():\n'

    '    import time\n'

    '    conn = _checkout()\n'

    '    try:\n'

    '        yield conn\n'

    '    except Exception:\n'

    '        try:\n'

    '            conn.rollback()\n'

    '        except Exception:\n'

    '            _get_pool().putconn(conn, close=True)\n'

    '            raise\n'

    '        _mark_used(conn)\n'

    '        _get_pool().putconn(conn)\n'

    '        raise\n'

    '    else:\n'

    '        _mark_used(conn)\n'

    '        _get_pool().putconn(conn)\n'

    '\n'

    'class _PooledBorrow:\n'

    '\n'

    '    def __init__(self, conn):\n'

    '        self._conn = conn\n'

    '        self._returned = False\n'

    '\n'

    '    def __getattr__(self, name):\n'

    '        return getattr(self._conn, name)\n'

    '\n'

    '    def close(self):\n'

    '        if self._returned:\n'

    '            return\n'

    '        self._returned = True\n'

    '        try:\n'

    '            self._conn.rollback()\n'

    '        except Exception:\n'

    '            _get_pool().putconn(self._conn, close=True)\n'

    '            return\n'

    '        import time\n'

    '        _mark_used(self._conn)\n'

    '        _get_pool().putconn(self._conn)\n'

    '\n'

    'def borrow():\n'

    '    return _PooledBorrow(_checkout())'

), 'D:\\Project\\gemini-automation-main\\gemini-automation-main\\backend\\db.py', 'exec'), _mod_db.__dict__)

print("db module registered.")



import sys, types

_mod_credits = types.ModuleType('credits')

sys.modules['credits'] = _mod_credits

exec(compile((

    'import hashlib\n'

    'import hmac\n'

    'import json\n'

    'import os\n'

    'import uuid\n'

    'import psycopg2\n'

    'import requests\n'

    'import db\n'

    "DATABASE_URL = os.environ.get('DATABASE_URL')\n"

    "RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')\n"

    "RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')\n"

    "PAYMENTS_MOCK = os.environ.get('GA_PAYMENTS_MOCK') == '1'\n"

    "COST_PER_LOOK = int(os.environ.get('GA_CREDITS_PER_LOOK', '10'))\n"

    "RAZORPAY_API = 'https://api.razorpay.com/v1'\n"

    '\n'

    'def configured():\n'

    '    return bool(DATABASE_URL)\n'

    '\n'

    'def payments_configured():\n'

    '    return PAYMENTS_MOCK or bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)\n'

    '\n'

    'class InsufficientCredits(Exception):\n'

    '\n'

    '    def __init__(self, needed, balance):\n'

    '        self.needed = needed\n'

    '        self.balance = balance\n'

    "        super().__init__(f'Insufficient credits: need {needed}, have {balance}.')\n"

    '\n'

    'class PaymentError(Exception):\n'

    '    pass\n'

    '\n'

    'def _conn():\n'

    '    return db.borrow()\n'

    '\n'

    'def _apply_delta(cur, user_id, delta, reason, reference_type, reference_id):\n'

    "    cur.execute('SELECT credit_balance FROM users WHERE id = %s FOR UPDATE', (user_id,))\n"

    '    row = cur.fetchone()\n'

    '    if not row:\n'

    "        raise PaymentError(f'user {user_id} not found')\n"

    '    after = row[0] + delta\n'

    '    if after < 0:\n'

    '        raise InsufficientCredits(-delta, row[0])\n'

    "    cur.execute('UPDATE users SET credit_balance = %s WHERE id = %s', (after, user_id))\n"

    "    cur.execute('INSERT INTO credit_transactions (user_id, delta, balance_after, reason, reference_type, reference_id)\\n           VALUES (%s,%s,%s,%s,%s,%s)', (user_id, delta, after, reason, reference_type, reference_id))\n"

    '    return after\n'

    '\n'

    'def balance(user_id):\n'

    '    conn = _conn()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('SELECT credit_balance FROM users WHERE id = %s', (user_id,))\n"

    '        row = cur.fetchone()\n'

    '        return row[0] if row else None\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def packages():\n'

    '    conn = _conn()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('SELECT slug, name, credits, price_minor, currency FROM credit_packages\\n               WHERE is_active ORDER BY price_minor')\n"

    "        return [{'slug': r[0], 'name': r[1], 'credits': r[2], 'price_minor': r[3], 'currency': r[4].strip()} for r in cur.fetchall()]\n"

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def charge_run(user_id, job, combos, prompt):\n'

    '    conn = _conn()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    '        for c in combos:\n'

    '            gen_id = str(uuid.uuid4())\n'

    '            cur.execute("INSERT INTO image_generations\\n                       (id, user_id, prompt, params, is_free, credits_cost, status,\\n                        worker_id, provider_job_id, started_at)\\n                   VALUES (%s,%s,%s,%s,FALSE,%s,\'processing\',\'gemini-automation\',%s,now())", (gen_id, user_id, prompt, json.dumps({\'source\': \'gemini-automation\', **{k: v for k, v in {\'garmentName\': job.get(\'garment_name\'), \'modelName\': job.get(\'model_name\'), \'styleName\': c.get(\'style_name\'), \'modelImage\': job.get(\'model_portrait_url\'), \'styleImage\': c.get(\'style_thumbnail_url\')}.items() if v}}), COST_PER_LOOK, job[\'id\']))\n'

    "            _apply_delta(cur, user_id, -COST_PER_LOOK, 'generation_spend', 'generation', gen_id)\n"

    "            cur.execute('INSERT INTO credit_holds (user_id, generation_id, amount) VALUES (%s,%s,%s)', (user_id, gen_id, COST_PER_LOOK))\n"

    "            c['charge_id'] = gen_id\n"

    '        conn.commit()\n'

    '    except Exception:\n'

    '        conn.rollback()\n'

    '        raise\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def settle_look(gen_id):\n'

    '    conn = _conn()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    '        cur.execute("UPDATE credit_holds SET status = \'settled\', released_at = now()\\n               WHERE generation_id = %s AND status = \'held\'", (gen_id,))\n'

    '        cur.execute("UPDATE image_generations SET status = \'done\', completed_at = now()\\n               WHERE id = %s AND status = \'processing\'", (gen_id,))\n'

    '        conn.commit()\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def refund_look(gen_id, error=None):\n'

    '    conn = _conn()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    '        cur.execute("UPDATE credit_holds SET status = \'released\', released_at = now()\\n               WHERE generation_id = %s AND status = \'held\'\\n               RETURNING user_id, amount", (gen_id,))\n'

    '        row = cur.fetchone()\n'

    '        if row and row[1] > 0:\n'

    "            _apply_delta(cur, row[0], row[1], 'hold_release', 'generation', gen_id)\n"

    '        cur.execute("UPDATE image_generations\\n               SET status = \'failed\', error = COALESCE(%s, error), completed_at = now()\\n               WHERE id = %s AND status = \'processing\'", ((error or \'generation did not finish\')[:500], gen_id))\n'

    '        conn.commit()\n'

    '        return bool(row)\n'

    '    except Exception:\n'

    '        conn.rollback()\n'

    '        raise\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def create_order(user_id, package_slug):\n'

    '    conn = _conn()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('SELECT id, name, credits, price_minor, currency FROM credit_packages\\n               WHERE slug = %s AND is_active', (package_slug,))\n"

    '        pack = cur.fetchone()\n'

    '        if not pack:\n'

    "            raise PaymentError('unknown credit pack')\n"

    '        pack_id, name, credits_n, amount_minor, currency = (pack[0], pack[1], pack[2], pack[3], pack[4].strip())\n'

    '        cur.execute("INSERT INTO payments (user_id, kind, amount_minor, currency, provider, credit_package_id)\\n               VALUES (%s,\'credit_pack\',%s,%s,\'razorpay\',%s) RETURNING id", (user_id, amount_minor, currency, pack_id))\n'

    '        payment_id = str(cur.fetchone()[0])\n'

    '        if PAYMENTS_MOCK:\n'

    "            order_id = f'order_mock_{payment_id[:18]}'\n"

    '        else:\n'

    "            resp = requests.post(f'{RAZORPAY_API}/orders', auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET), json={'amount': amount_minor, 'currency': currency, 'receipt': payment_id, 'notes': {'payment_id': payment_id, 'kind': 'credit_pack'}}, timeout=20)\n"

    '            if resp.status_code >= 300:\n'

    "                raise PaymentError(f'gateway rejected the order ({resp.status_code})')\n"

    "            order_id = resp.json()['id']\n"

    "        cur.execute('UPDATE payments SET provider_payment_id = %s WHERE id = %s', (order_id, payment_id))\n"

    '        conn.commit()\n'

    "        return {'payment_id': payment_id, 'razorpay_order_id': order_id, 'key_id': RAZORPAY_KEY_ID, 'amount_minor': amount_minor, 'currency': currency, 'description': name, 'credits': credits_n, 'mock': PAYMENTS_MOCK, 'test_mode': PAYMENTS_MOCK or RAZORPAY_KEY_ID.startswith('rzp_test_')}\n"

    '    except Exception:\n'

    '        conn.rollback()\n'

    '        raise\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def _settle_paid_order(user_id, order_id, amount_minor, currency):\n'

    '    conn = _conn()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('SELECT id, user_id, amount_minor, currency, status, credit_package_id\\n               FROM payments WHERE provider_payment_id = %s FOR UPDATE', (order_id,))\n"

    '        pay = cur.fetchone()\n'

    '        if not pay:\n'

    "            raise PaymentError('payment not found for that order')\n"

    '        pay_id, pay_user, pay_amount, pay_currency, status, pack_id = (str(pay[0]), str(pay[1]), pay[2], pay[3].strip(), pay[4], pay[5])\n'

    '        if pay_user != str(user_id):\n'

    "            raise PaymentError('payment belongs to a different account')\n"

    "        if status == 'paid':\n"

    "            return {'already_processed': True, 'credits_granted': 0}\n"

    '        if amount_minor != pay_amount or currency != pay_currency:\n'

    "            raise PaymentError('captured amount does not match the order')\n"

    '        cur.execute("UPDATE payments SET status = \'paid\', paid_at = now() WHERE id = %s", (pay_id,))\n'

    "        cur.execute('SELECT credits FROM credit_packages WHERE id = %s', (pack_id,))\n"

    '        granted = cur.fetchone()[0]\n'

    "        after = _apply_delta(cur, pay_user, granted, 'pack_purchase', 'payment', pay_id)\n"

    '        conn.commit()\n'

    "        return {'already_processed': False, 'credits_granted': granted, 'balance': after}\n"

    '    except Exception:\n'

    '        conn.rollback()\n'

    '        raise\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def verify_payment(user_id, order_id, payment_id, signature):\n'

    "    if PAYMENTS_MOCK and order_id.startswith('order_mock_'):\n"

    '        conn = _conn()\n'

    '        try:\n'

    '            cur = conn.cursor()\n'

    "            cur.execute('SELECT amount_minor, currency FROM payments WHERE provider_payment_id = %s', (order_id,))\n"

    '            row = cur.fetchone()\n'

    '        finally:\n'

    '            conn.close()\n'

    '        if not row:\n'

    "            raise PaymentError('payment not found for that order')\n"

    '        return _settle_paid_order(user_id, order_id, row[0], row[1].strip())\n'

    "    expected = hmac.new(RAZORPAY_KEY_SECRET.encode(), f'{order_id}|{payment_id}'.encode(), hashlib.sha256).hexdigest()\n"

    "    if not hmac.compare_digest(expected, signature or ''):\n"

    "        raise PaymentError('payment signature verification failed')\n"

    "    resp = requests.get(f'{RAZORPAY_API}/payments/{payment_id}', auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET), timeout=20)\n"

    '    if resp.status_code >= 300:\n'

    "        raise PaymentError(f'could not confirm the payment with the gateway ({resp.status_code})')\n"

    '    payment = resp.json()\n'

    "    if payment.get('order_id') != order_id:\n"

    "        raise PaymentError('payment does not belong to that order')\n"

    "    if payment.get('status') == 'authorized':\n"

    "        cap = requests.post(f'{RAZORPAY_API}/payments/{payment_id}/capture', auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET), json={'amount': payment['amount'], 'currency': payment['currency']}, timeout=20)\n"

    '        if cap.status_code >= 300:\n'

    "            raise PaymentError('payment could not be captured')\n"

    '        payment = cap.json()\n'

    "    if payment.get('status') != 'captured':\n"

    '        raise PaymentError(f"payment is {payment.get(\'status\')}")\n'

    "    return _settle_paid_order(user_id, order_id, payment['amount'], payment['currency'])"

), 'D:\\Project\\gemini-automation-main\\gemini-automation-main\\backend\\credits.py', 'exec'), _mod_credits.__dict__)

print("credits module registered.")



import sys, types

_mod_fashion_studio = types.ModuleType('fashion_studio')

sys.modules['fashion_studio'] = _mod_fashion_studio

exec(compile((

    'import json\n'

    'import mimetypes\n'

    'import os\n'

    'import uuid\n'

    'from pathlib import Path\n'

    'import boto3\n'

    'import psycopg2\n'

    'import db\n'

    "R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')\n"

    "R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')\n"

    "R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')\n"

    "R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')\n"

    "R2_PUBLIC_URL = (os.environ.get('R2_PUBLIC_URL') or '').rstrip('/')\n"

    "DATABASE_URL = os.environ.get('DATABASE_URL')\n"

    "FASHION_STUDIO_USER_ID = os.environ.get('FASHION_STUDIO_USER_ID')\n"

    '\n'

    'def configured():\n'

    '    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_PUBLIC_URL and DATABASE_URL)\n'

    '\n'

    'def _r2_client():\n'

    "    return boto3.client('s3', endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com', aws_access_key_id=R2_ACCESS_KEY_ID, aws_secret_access_key=R2_SECRET_ACCESS_KEY, region_name='auto')\n"

    '\n'

    'def _db():\n'

    '    return db.borrow()\n'

    '\n'

    'def already_done(gen_id):\n'

    '    if not DATABASE_URL:\n'

    '        return False\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('SELECT status, output_url FROM image_generations WHERE id = %s', (gen_id,))\n"

    '        row = cur.fetchone()\n'

    "        return bool(row and row[0] == 'done' and row[1])\n"

    '    except Exception:\n'

    '        return False\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_categories():\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('\\n            SELECT DISTINCT cat.name\\n            FROM catalogue_items ci\\n            JOIN categories cat ON cat.id = ci.category_id\\n            WHERE ci.is_active = TRUE AND cat.is_active = TRUE\\n            ORDER BY cat.name\\n            ')\n"

    '        return [row[0] for row in cur.fetchall()]\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_genders():\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('\\n            SELECT DISTINCT g.label\\n            FROM catalogue_items ci\\n            JOIN genders g ON g.id = ci.gender_id\\n            WHERE ci.is_active = TRUE\\n            ORDER BY g.label\\n            ')\n"

    '        return [row[0] for row in cur.fetchall()]\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def _format_facet_label(raw):\n'

    "    label = ' '.join(raw.split())\n"

    '    return label[:1].upper() + label[1:] if label else label\n'

    '\n'

    'def list_pose_types():\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    '        cur.execute("\\n            SELECT DISTINCT ON (lower(trim(pose_type))) trim(pose_type)\\n            FROM poses\\n            WHERE NULLIF(trim(pose_type), \'\') IS NOT NULL\\n            ORDER BY lower(trim(pose_type)), trim(pose_type)\\n            ")\n'

    '        return [_format_facet_label(row[0]) for row in cur.fetchall()]\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_view_angles():\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    '        cur.execute("\\n            SELECT DISTINCT ON (lower(trim(view_angle))) trim(view_angle)\\n            FROM poses\\n            WHERE NULLIF(trim(view_angle), \'\') IS NOT NULL\\n            ORDER BY lower(trim(view_angle)), trim(view_angle)\\n            ")\n'

    '        return [_format_facet_label(row[0]) for row in cur.fetchall()]\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_styles(limit=16, category=None, gender=None, pose_type=None, view_angle=None, search=None):\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        where = ['ci.is_active = TRUE', 'pk.is_active = TRUE', 'ci.thumbnail_url IS NOT NULL']\n"

    '        params = []\n'

    '        if category:\n'

    "            where.append('cat.name = %s')\n"

    '            params.append(category)\n'

    '        if gender:\n'

    "            where.append('g.label = %s')\n"

    '            params.append(gender)\n'

    '        if pose_type:\n'

    "            where.append('lower(trim(po.pose_type)) = lower(trim(%s))')\n"

    '            params.append(pose_type)\n'

    '        if view_angle:\n'

    "            where.append('lower(trim(po.view_angle)) = lower(trim(%s))')\n"

    '            params.append(view_angle)\n'

    '        if search:\n'

    "            where.append('(bg.name ILIKE %s OR pk.primary_outfit_name ILIKE %s OR ci.title ILIKE %s)')\n"

    "            like = f'%{search}%'\n"

    '            params += [like, like, like]\n'

    '        params.append(limit)\n'

    '        cur.execute(f"\\n            SELECT ci.id, ci.title, ci.thumbnail_url, ci.hologram_url, ci.camera_angle, ci.body_visibility,\\n                   pk.primary_outfit_name, po.pose_type, po.view_angle,\\n                   bg.name AS background_name, cat.name AS category_name\\n            FROM catalogue_items ci\\n            JOIN packages pk ON pk.id = ci.package_id\\n            LEFT JOIN poses po ON po.id = ci.pose_id\\n            LEFT JOIN backgrounds bg ON bg.id = pk.background_id\\n            LEFT JOIN categories cat ON cat.id = ci.category_id\\n            LEFT JOIN genders g ON g.id = ci.gender_id\\n            WHERE {\' AND \'.join(where)}\\n            ORDER BY random()\\n            LIMIT %s\\n            ", params)\n'

    "        cols = ['id', 'title', 'thumbnail_url', 'hologram_url', 'camera_angle', 'body_visibility', 'outfit_name', 'pose_type', 'view_angle', 'background', 'category']\n"

    '        rows = [dict(zip(cols, row)) for row in cur.fetchall()]\n'

    '        for row in rows:\n'

    "            row['id'] = str(row['id'])\n"

    "            row['prompt'] = style_prompt(row)\n"

    '        return rows\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_ethnicities():\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('\\n            SELECT DISTINCT e.label FROM models m JOIN ethnicities e ON e.id = m.ethnicity_id\\n            WHERE m.is_active = TRUE ORDER BY e.label\\n            ')\n"

    '        return [row[0] for row in cur.fetchall()]\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_skin_tones():\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('\\n            SELECT DISTINCT st.label FROM models m JOIN skin_tones st ON st.id = m.skin_tone_id\\n            WHERE m.is_active = TRUE ORDER BY st.label\\n            ')\n"

    '        return [row[0] for row in cur.fetchall()]\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_body_types():\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('\\n            SELECT DISTINCT bt.label FROM models m JOIN body_types bt ON bt.id = m.body_type_id\\n            WHERE m.is_active = TRUE ORDER BY bt.label\\n            ')\n"

    '        return [row[0] for row in cur.fetchall()]\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_ages():\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        cur.execute('\\n            SELECT DISTINCT age_min, age_max FROM models\\n            WHERE is_active = TRUE AND age_min IS NOT NULL AND age_max IS NOT NULL\\n            ORDER BY age_min\\n            ')\n"

    "        return [f'{row[0]}–{row[1]}' for row in cur.fetchall()]\n"

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_models(limit=16, ethnicity=None, skin_tone=None, body_type=None, age=None):\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        where = ['m.is_active = TRUE', 'm.image_url IS NOT NULL']\n"

    '        params = []\n'

    '        if ethnicity:\n'

    "            where.append('e.label = %s')\n"

    '            params.append(ethnicity)\n'

    '        if skin_tone:\n'

    "            where.append('st.label = %s')\n"

    '            params.append(skin_tone)\n'

    '        if body_type:\n'

    "            where.append('bt.label = %s')\n"

    '            params.append(body_type)\n'

    "        if age and '–' in age:\n"

    "            age_min, age_max = age.split('–', 1)\n"

    '            if age_min.isdigit() and age_max.isdigit():\n'

    "                where.append('m.age_min = %s AND m.age_max = %s')\n"

    '                params += [int(age_min), int(age_max)]\n'

    '        params.append(limit)\n'

    '        cur.execute(f"\\n            SELECT m.id, m.name, m.image_url, m.angle_image_url,\\n                   e.label AS ethnicity, st.label AS skin_tone, bt.label AS body_type,\\n                   m.age_min, m.age_max\\n            FROM models m\\n            LEFT JOIN ethnicities e ON e.id = m.ethnicity_id\\n            LEFT JOIN skin_tones st ON st.id = m.skin_tone_id\\n            LEFT JOIN body_types bt ON bt.id = m.body_type_id\\n            WHERE {\' AND \'.join(where)}\\n            ORDER BY random()\\n            LIMIT %s\\n            ", params)\n'

    "        cols = ['id', 'name', 'image_url', 'angle_image_url', 'ethnicity', 'skin_tone', 'body_type', 'age_min', 'age_max']\n"

    '        rows = [dict(zip(cols, row)) for row in cur.fetchall()]\n'

    '        for row in rows:\n'

    "            row['id'] = str(row['id'])\n"

    '        return rows\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def list_packages(limit=16, category=None, search=None, style_count=None):\n'

    '    if not DATABASE_URL:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    "        where = ['pk.is_active = TRUE', 'pk.cover_image_url IS NOT NULL']\n"

    '        params = []\n'

    '        if category:\n'

    "            where.append('cat.name = %s')\n"

    '            params.append(category)\n'

    '        if search:\n'

    "            where.append('(bg.name ILIKE %s OR pk.primary_outfit_name ILIKE %s)')\n"

    "            like = f'%{search}%'\n"

    '            params += [like, like]\n'

    '        if style_count:\n'

    "            at_least = style_count.endswith('+')\n"

    '            n = style_count[:-1] if at_least else style_count\n'

    '            if n.isdigit():\n'

    "                op = '>=' if at_least else '='\n"

    "                where.append(f'(SELECT count(*) FROM catalogue_items ci WHERE ci.package_id = pk.id AND ci.is_active) {op} %s')\n"

    '                params.append(int(n))\n'

    '        params.append(limit)\n'

    '        cur.execute(f"\\n            SELECT pk.id, pk.name, pk.cover_image_url, pk.primary_outfit_name,\\n                   cat.name AS category_name, fm.label AS mood\\n            FROM packages pk\\n            LEFT JOIN categories cat ON cat.id = pk.category_id\\n            LEFT JOIN fashion_moods fm ON fm.id = pk.fashion_mood_id\\n            LEFT JOIN backgrounds bg ON bg.id = pk.background_id\\n            WHERE {\' AND \'.join(where)}\\n            ORDER BY random()\\n            LIMIT %s\\n            ", params)\n'

    "        cols = ['id', 'name', 'cover_image_url', 'outfit_name', 'category', 'mood']\n"

    '        rows = [dict(zip(cols, row)) for row in cur.fetchall()]\n'

    '        for row in rows:\n'

    "            row['id'] = str(row['id'])\n"

    "            row['prompt'] = package_prompt(row)\n"

    '        if rows:\n'

    "            ids = [row['id'] for row in rows]\n"

    "            cur.execute('\\n                SELECT package_id, id, title, thumbnail_url, hologram_url, item_count\\n                FROM (\\n                    SELECT ci.package_id, ci.id, ci.title, ci.thumbnail_url, ci.hologram_url,\\n                           row_number() OVER (PARTITION BY ci.package_id ORDER BY ci.sequence_no) AS rn,\\n                           count(*) OVER (PARTITION BY ci.package_id) AS item_count\\n                    FROM catalogue_items ci\\n                    WHERE ci.package_id = ANY(%s::uuid[]) AND ci.is_active AND ci.thumbnail_url IS NOT NULL\\n                ) t\\n                WHERE rn <= 8\\n                ORDER BY package_id, rn\\n                ', (ids,))\n"

    '            scenes_by_pkg = {}\n'

    '            count_by_pkg = {}\n'

    '            for package_id, item_id, title, thumbnail_url, hologram_url, item_count in cur.fetchall():\n'

    '                package_id = str(package_id)\n'

    "                scenes_by_pkg.setdefault(package_id, []).append({'id': str(item_id), 'title': title, 'thumbnail_url': thumbnail_url, 'hologram_url': hologram_url})\n"

    '                count_by_pkg[package_id] = item_count\n'

    '            for row in rows:\n'

    "                row['scenes'] = scenes_by_pkg.get(row['id']) or [{'id': row['id'], 'title': row['name'], 'thumbnail_url': row['cover_image_url'], 'hologram_url': None}]\n"

    "                row['scene_count'] = count_by_pkg.get(row['id'], len(row['scenes']))\n"

    '        return rows\n'

    '    finally:\n'

    '        conn.close()\n'

    '\n'

    'def package_prompt(pkg):\n'

    '    bits = []\n'

    "    if pkg.get('category'):\n"

    '        bits.append(f"professional {pkg[\'category\']} fashion photography")\n'

    "    if pkg.get('outfit_name'):\n"

    '        bits.append(f"garment styled as: {pkg[\'outfit_name\']}")\n'

    "    if pkg.get('mood'):\n"

    '        bits.append(f"{pkg[\'mood\']} mood")\n'

    "    bits.append('studio-quality lighting, sharp focus, realistic fabric texture')\n"

    "    return 'Put this exact garment on a fashion model. ' + ', '.join(bits) + '.'\n"

    '\n'

    'def style_prompt(style):\n'

    '    bits = []\n'

    "    if style.get('category'):\n"

    '        bits.append(f"professional {style[\'category\']} fashion photography")\n'

    "    if style.get('outfit_name'):\n"

    '        bits.append(f"garment styled as: {style[\'outfit_name\']}")\n'

    "    if style.get('pose_type'):\n"

    "        pose = style['pose_type']\n"

    "        if style.get('view_angle'):\n"

    '            pose = f"{style[\'view_angle\']} {pose}"\n'

    '        bits.append(pose)\n'

    "    if style.get('camera_angle'):\n"

    '        bits.append(f"{style[\'camera_angle\']} camera angle")\n'

    "    if style.get('body_visibility'):\n"

    '        bits.append(f"{style[\'body_visibility\']} shot")\n'

    "    if style.get('background'):\n"

    '        bits.append(f"set against {style[\'background\']}")\n'

    "    bits.append('studio-quality lighting, sharp focus, realistic fabric texture')\n"

    "    return 'Put this exact garment on a fashion model. ' + ', '.join(bits) + '.'\n"

    '_FASHION_TRYON_BODY = "GOLDEN RULE: BINARY VISIBILITY MASK\\nThe mannequin is a strict binary visibility mask. Replace ONLY pixels occupied by the mannequin. Never expand the mask. Never generate outside the mannequin\'s crop boundaries. If a body part is cropped in the mannequin, it remains cropped.\\n\\nREFERENCE AUTHORITY (STRICT ISOLATION)\\n• MANNEQUIN_REF: Absolute authority for pose, skeleton, camera, crop, framing, lighting, shadows, environment, accessory paths, and footwear contact. Contains ZERO clothing/face data.\\n• CLOTHING_REF: Absolute authority for garment identity, construction, structural topology, material properties and commercial product specification. Contains ZERO pose, body or camera data.{face_ref_authority}\\n\\nREFERENCE COMPLETENESS\\nUse only information explicitly visible in each reference.\\nWhen information is not visible, reconstruct conservatively from visible structural evidence without redesigning or inventing new product features.\\n\\nHARD CONSTRAINTS & SOFT PREFERENCES\\nHARD CONSTRAINTS (Must Never Change):\\n• Visibility mask and crop boundaries\\n• Pose, skeleton, and camera geometry\\n• Face identity and hairstyle identity\\n• Garment identity and material identity\\n• Accessory geometry and paths\\n\\nSOFT PREFERENCES (Optimize When Possible):\\n• Photographic realism and lighting consistency\\n• Fabric wrinkles, folds, and drape\\n• Facial expression and eye gaze\\n• Hair strand physics and movement\\n• Soft tissue and skin deformation\\n\\nCONFLICT HIERARCHY\\n1. Visibility Mask & Canvas (Absolute)\\n2. Pose, Skeleton & Camera (Immutable structural base)\\n3. Garment & Face Identity (Identity Preservation)\\n4. Photorealistic Rendering (Execution)\\n\\nFAILURE POLICY\\nIf all constraints cannot be satisfied simultaneously, preserve every hard constraint.\\nNever invent new content to resolve ambiguity.\\nPrefer an incomplete but faithful reconstruction over an incorrect reconstruction.\\nDo not redesign, approximate, beautify, or hallucinate missing information.\\nWhen uncertainty exists, preserve product identity and structural consistency rather than inventing missing garment details.\\n\\nPOSE OVERRIDES GARMENT\\nIf preserving garment appearance requires changing pose, skeleton, camera, or framing, DO NOT modify the body.\\nAlways adapt the garment to the locked pose.\\nNever adapt the pose to the garment.\\n\\nPOSE, SKELETON & CAMERA LOCK\\n• Skeleton: Immutable. Faithfully preserve exact joint angles, limb states, weight distribution, and asymmetry. Do not relax, beautify, or auto-correct.\\n• Hands & Contact: Faithfully preserve exact gesture, finger curl, and physical contact points. No new or removed contacts.\\n• Camera: Camera geometry is immutable. Maintain identical viewpoint, perspective, focal length, framing, crop, and aspect ratio.\\n\\nVISIBILITY & OCCLUSION\\n• Mask Rule: Visible anatomy comes ONLY from MANNEQUIN_REF. Never reveal hidden surfaces or complete cropped regions.\\n• Occlusion: Exact foreground/background relationships maintained.\\n\\nGARMENT IDENTITY\\nTreat CLOTHING_REF as the canonical product specification rather than a worn garment\\nInfer garment construction only from visible evidence contained in CLOTHING_REF.\\nReconstruct the same garment as if professionally worn on the reconstructed body without altering its identity.\\nFaithfully preserve the original garment identity, including:\\n• garment category, construction, neckline, sleeve length\\n• embroidery geometry, placement, border geometry, print layout\\n• fabric type, micro-texture, weave pattern, embroidery density, printed motifs, trims, borders, surface finish and material appearance.\\nDo not redesign, reinterpret, or approximate the product.\\nPreserve the commercial product exactly; only physically plausible deformation caused by dressing and the locked pose is permitted.\\n\\nIDENTITY CONTINUITY\\nAll visible garment regions must remain mutually consistent as parts of the same commercial product.\\nConstruction, proportions, materials, decorative elements and finishing details must remain coherent across the entire garment.\\n\\nGARMENT DRESSING\\nReconstruct the complete human anatomy from MANNEQUIN_REF before applying the garment.\\nDress the reconstructed body with the garment defined by CLOTHING_REF.\\nDetermine the correct wearing configuration from the garment construction, structural design and fastening system.\\nBody anatomy defines garment deformation.\\nGenerate physically realistic wrapping, layering, fastening, tension, compression, folds and drape created only by body anatomy, gravity, material properties and the locked pose.\\nDo not copy fold patterns from CLOTHING_REF.\\nGenerate new folds from physical interaction while preserving product identity.\\n\\nGARMENT TOPOLOGY\\nPreserve the relative spatial arrangement and proportions of all structural garment components.\\nNecklines, waistlines, shoulder seams, sleeve attachments, borders, hems, pleats, panels, lapels, collars, cuffs and structural elements must remain in their correct anatomical positions.\\nDo not shift, rotate, resize or proportionally alter structural garment components.\\n\\nBODY–GARMENT COUPLING\\nThe garment must appear physically worn rather than overlaid.\\nMaintain continuous body contact where naturally expected.\\nFabric deformation must arise only from body anatomy, contact, gravity, material properties and the locked pose.\\nAvoid floating fabric or detached garment regions.\\nMaterial appearance should respond naturally to the locked scene lighting while preserving original fabric characteristics.\\n\\nSTRUCTURAL STABILITY\\nPreserve the structural integrity of the garment.\\nSeams, attachment points, closures, waistlines, necklines, cuffs, collars and other structural components must remain mechanically consistent under deformation.\\nOnly physically plausible deformation is permitted.\\n\\nFACE & HAIR ADAPTATION\\n• Face: Identity is immutable. Do not copy the reference expression. Generate a natural expression from the combined influence of body language, head orientation, garment style, environment, lighting, camera distance and commercial fashion intent. Expressions should appear naturally emerging from the interaction between the model, photographer, garment and environment, rather than looking artificially posed or emotionally empty. Preserve natural facial asymmetry, subtle facial muscle activation, dimples, smile lines, crow\'s feet, nasolabial folds and other genuine micro-expressions when naturally produced by the scene or expression.\\n• Hair: Identity (haircut, length, density, texture and color) is immutable. Hair strands are adaptive. Preserve hairstyle identity while naturally responding to gravity, body movement, shoulder contact and airflow. Hair must emerge naturally from the scalp with realistic volume and strand continuity.\\n\\nEYE BEHAVIOR\\nEyes should exhibit realistic human behavior with natural focus, subtle eyelid asymmetry, appropriate catchlights, gaze stability, gentle squinting under bright sunlight and relaxed ocular muscles. Avoid frozen staring or perfectly symmetrical eyes.\\n\\nSKIN REALISM\\nPreserve natural skin characteristics including fine pores, subtle wrinkles, gentle skin compression, lip texture, realistic translucency, slight color variation and natural specular highlights appropriate to the lighting.\\n\\nACCESSORY & ENVIRONMENT LOCK\\n• Accessories: Rigid geometry. Faithfully preserve exact dimensions, strap paths, and occlusion. Do not reroute straps or float bags.\\n• Environment: Static. Lighting, shadows, and background remain spatially identical to MANNEQUIN_REF.\\n\\nCONSISTENCY PRINCIPLE\\nAll reconstructed elements must remain mutually consistent.\\nFace, body, clothing, lighting, shadows, perspective, and material response must appear to belong to a single photograph captured at one moment in time.\\nAll reconstructed elements must share one physically coherent three-dimensional world space.\\n\\nHUMAN REALISM\\nProduce an authentic commercial fashion photograph with consistent lighting, perspective, material response and photographic realism.\\nPreserve natural human asymmetry, realistic skin and authentic fabric imperfections.\\nAvoid synthetic, over-processed or digitally illustrated appearance.\\n\\nNEGATIVE CONSTRAINTS\\nDo not violate:\\n• visibility\\n• pose\\n• camera\\n• garment identity\\n• face identity\\n• material identity\\n• accessory geometry\\n\\nAvoid:\\n• AI artifacts\\n• plastic skin\\n• floating objects\\n• unrealistic fabric physics\\n• incorrect garment construction\\n• geometry distortion\\n• artificial symmetry\\n\\nINPUT ORDER (this request):\\n{input_order}\\nGenerate exactly one final fashion photograph."\n'

    '\n'

    'def fashion_tryon_prompt(has_model):\n'

    '    if has_model:\n'

    "        core_objective = 'CORE OBJECTIVE\\nCreate one physically plausible commercial fashion photograph by replacing the mannequin with the real person from FACE_REF while faithfully preserving the garment identity from CLOTHING_REF and the complete body pose from MANNEQUIN_REF.\\nThis is a constrained reconstruction task, not creative image synthesis.'\n"

    "        face_ref_authority = '\\n• FACE_REF: Absolute authority for facial identity, skin, hair, and person appearance from the model character/angle reference. Contains ZERO body pose data — pose always comes from MANNEQUIN_REF.'\n"

    "        input_order = '1) CLOTHING_REF image(s) — garment packshot(s)\\n2) MANNEQUIN_REF image — hologram / pose mannequin\\n3) FACE_REF image — model character / angle reference (identity)'\n"

    '    else:\n'

    "        core_objective = 'CORE OBJECTIVE\\nCreate one physically plausible commercial fashion photograph by rendering a professional fashion model wearing the garment from CLOTHING_REF, in the exact body pose, camera framing and scene established by MANNEQUIN_REF.\\nThis is a constrained reconstruction task, not creative image synthesis.'\n"

    "        face_ref_authority = ''\n"

    "        input_order = '1) CLOTHING_REF image(s) — garment packshot(s)\\n2) MANNEQUIN_REF image — hologram / pose mannequin'\n"

    "    return core_objective + '\\n\\n' + _FASHION_TRYON_BODY.format(face_ref_authority=face_ref_authority, input_order=input_order)\n"

    '\n'

    'def download_remote_image(url, dest_dir):\n'

    '    import hashlib\n'

    '    import urllib.request\n'

    "    ext = Path(url.split('?')[0]).suffix or '.webp'\n"

    '    dest_dir = Path(dest_dir)\n'

    '    dest_dir.mkdir(parents=True, exist_ok=True)\n'

    "    dest = dest_dir / f'ref-{hashlib.sha1(url.encode()).hexdigest()[:20]}{ext}'\n"

    '    if dest.exists() and dest.stat().st_size > 0:\n'

    '        return str(dest)\n'

    "    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})\n"

    '    with urllib.request.urlopen(req, timeout=20) as resp:\n'

    '        dest.write_bytes(resp.read())\n'

    '    return str(dest)\n'

    '\n'

    'def list_generations(user_id, limit=30):\n'

    '    if not configured() or not user_id:\n'

    '        return []\n'

    '    conn = _db()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    '        cur.execute("\\n            SELECT id, prompt, params, output_url,\\n                   EXTRACT(EPOCH FROM created_at) AS created_at\\n            FROM image_generations\\n            WHERE user_id = %s AND status = \'done\' AND output_url IS NOT NULL\\n            ORDER BY created_at DESC\\n            LIMIT %s\\n            ", (user_id, limit))\n'

    '        rows = cur.fetchall()\n'

    '    finally:\n'

    '        conn.close()\n'

    '    out = []\n'

    '    for gen_id, prompt_text, params, output_url, created_at in rows:\n'

    '        p = params if isinstance(params, dict) else {}\n'

    "        garment_images = p.get('garmentImages') or []\n"

    "        out.append({'id': str(gen_id), 'output_url': output_url, 'prompt': prompt_text, 'created_at': float(created_at) if created_at is not None else None, 'garment_name': p.get('garmentName'), 'model_name': p.get('modelName'), 'style_name': p.get('styleName'), 'garment_image': (garment_images[0] if garment_images else None) or p.get('garmentImage'), 'model_image': p.get('modelImage'), 'style_image': p.get('styleImage'), 'source': p.get('source')})\n"

    '    return out\n'

    '\n'

    'def push_generation(image_path, prompt, user_id=None, params=None, gen_id=None, webp_path=None, force=False):\n'

    '    if not configured():\n'

    "        raise RuntimeError('fashion-studio push not configured — check backend/.env (R2_*, DATABASE_URL)')\n"

    '    target_user_id = user_id or FASHION_STUDIO_USER_ID\n'

    '    if not target_user_id:\n'

    "        raise RuntimeError('no fashion-studio account linked — sign in with Google (Step 0) first, or set FASHION_STUDIO_USER_ID in backend/.env as a fallback')\n"

    "    ext = Path(image_path).suffix.lstrip('.').lower() or 'png'\n"

    "    if ext == 'jpeg':\n"

    "        ext = 'jpg'\n"

    "    content_type = mimetypes.guess_type(image_path)[0] or 'image/png'\n"

    '    gen_id = gen_id or str(uuid.uuid4())\n'

    "    key = f'generations/{target_user_id}/{gen_id}.{ext}'\n"

    "    with open(image_path, 'rb') as f:\n"

    '        data = f.read()\n'

    "    _r2_client().put_object(Bucket=R2_BUCKET_NAME, Key=key, Body=data, ContentType=content_type, CacheControl='public, max-age=31536000, immutable')\n"

    "    output_url = f'{R2_PUBLIC_URL}/{key}'\n"

    '    webp_url = None\n'

    '    if webp_path and os.path.exists(webp_path):\n'

    "        webp_key = f'generations/{target_user_id}/{gen_id}.webp'\n"

    "        with open(webp_path, 'rb') as f:\n"

    '            webp_data = f.read()\n'

    "        _r2_client().put_object(Bucket=R2_BUCKET_NAME, Key=webp_key, Body=webp_data, ContentType='image/webp', CacheControl='public, max-age=31536000, immutable')\n"

    "        webp_url = f'{R2_PUBLIC_URL}/{webp_key}'\n"

    "    params_json = json.dumps({'source': 'gemini-automation', **{k: v for k, v in (params or {}).items() if v}})\n"

    '    conn = db.borrow()\n'

    '    try:\n'

    '        cur = conn.cursor()\n'

    '        try:\n'

    '            if force:\n'

    '                cur.execute("\\n                    INSERT INTO image_generations\\n                        (id, user_id, prompt, params, is_free, credits_cost, status,\\n                         output_url, webp_url, started_at, completed_at)\\n                    VALUES (%s, %s, %s, %s, TRUE, 0, \'done\', %s, %s, now(), now())\\n                    ON CONFLICT (id) DO UPDATE SET\\n                        status = \'done\', output_url = EXCLUDED.output_url,\\n                        webp_url = EXCLUDED.webp_url, completed_at = now()\\n                    ", (gen_id, target_user_id, prompt, params_json, output_url, webp_url))\n'

    '            else:\n'

    '                cur.execute("\\n                    UPDATE image_generations\\n                    SET status = \'done\', output_url = %s, webp_url = %s, completed_at = now()\\n                    WHERE id = %s AND status = \'processing\'\\n                    ", (output_url, webp_url, gen_id))\n'

    '                if cur.rowcount == 0:\n'

    '                    cur.execute("\\n                        INSERT INTO image_generations\\n                            (id, user_id, prompt, params, is_free, credits_cost, status,\\n                             output_url, webp_url, started_at, completed_at)\\n                        VALUES (%s, %s, %s, %s, TRUE, 0, \'done\', %s, %s, now(), now())\\n                        ON CONFLICT (id) DO NOTHING\\n                        ", (gen_id, target_user_id, prompt, params_json, output_url, webp_url))\n'

    '        except psycopg2.errors.UndefinedColumn:\n'

    '            conn.rollback()\n'

    '            cur = conn.cursor()\n'

    '            if force:\n'

    '                cur.execute("\\n                    INSERT INTO image_generations\\n                        (id, user_id, prompt, params, is_free, credits_cost, status,\\n                         output_url, started_at, completed_at)\\n                    VALUES (%s, %s, %s, %s, TRUE, 0, \'done\', %s, now(), now())\\n                    ON CONFLICT (id) DO UPDATE SET\\n                        status = \'done\', output_url = EXCLUDED.output_url, completed_at = now()\\n                    ", (gen_id, target_user_id, prompt, params_json, output_url))\n'

    '            else:\n'

    '                cur.execute("\\n                    UPDATE image_generations\\n                    SET status = \'done\', output_url = %s, completed_at = now()\\n                    WHERE id = %s AND status = \'processing\'\\n                    ", (output_url, gen_id))\n'

    '                if cur.rowcount == 0:\n'

    '                    cur.execute("\\n                        INSERT INTO image_generations\\n                            (id, user_id, prompt, params, is_free, credits_cost, status,\\n                             output_url, started_at, completed_at)\\n                        VALUES (%s, %s, %s, %s, TRUE, 0, \'done\', %s, now(), now())\\n                        ON CONFLICT (id) DO NOTHING\\n                        ", (gen_id, target_user_id, prompt, params_json, output_url))\n'

    '        conn.commit()\n'

    '    finally:\n'

    '        conn.close()\n'

    "    return {'output_url': output_url, 'webp_url': webp_url}"

), 'D:\\Project\\gemini-automation-main\\gemini-automation-main\\backend\\fashion_studio.py', 'exec'), _mod_fashion_studio.__dict__)

print("fashion_studio module registered.")







# ----------------------------------------------------------------------------

