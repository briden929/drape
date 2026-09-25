# ============================================================================
# QUEUE WORKER v3.0 — DUAL-BROWSER + AGGRESSIVE TAB MANAGEMENT
# ============================================================================
# Paste this ENTIRE cell into Google Colab and run.
#
# v3.0 CHANGES:
#   1. New Redis tunnel URL (controlled-write-argue-loans)
#   2. Microsoft Edge for watermark removal (separate browser, no login)
#   3. Aggressive round-robin tab management (immediate next-tab dispatch)
#   4. Per-tab download folders (Chrome gen + Edge WMR)
#   5. Chrome uses existing logged-in profile only
#   6. Better step names throughout
# ============================================================================

# ----------------------------------------------------------------------------
# STEP_INIT_SECRETS: Load credentials
# ----------------------------------------------------------------------------
import os

_HARDCODED = {
    'DATABASE_URL': 'postgresql://postgres.cfgthwsqgmvtftlyoamj:Daxil%4016%3F80!@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres',
    'R2_ACCOUNT_ID': '8e22889fff8e7c874800278c4bdcb26c',
    'R2_ACCESS_KEY_ID': 'e90045f23e9cd55bb08238384b771bf2',
    'R2_SECRET_ACCESS_KEY': '0b0e32afb39cf06d1682968ee7dc1750526b04c2ea16b200fb6027b070e7d4d6',
    'R2_BUCKET_NAME': 'studio-photoshoot',
    'R2_PUBLIC_URL': 'https://pub-943056d53cd64d87aef37136315753a7.r2.dev',
    'REDIS_TUNNEL_URL': 'https://controlled-write-argue-loans.trycloudflare.com',
}
for _name, _val in _HARDCODED.items():
    os.environ[_name] = _val

_FORMAT_HINTS = {
    "DATABASE_URL": lambda v: v.startswith(("postgres://", "postgresql://")),
    "R2_PUBLIC_URL": lambda v: v.startswith("https://"),
    "REDIS_TUNNEL_URL": lambda v: v.startswith(("https://", "wss://")),
    "R2_ACCOUNT_ID": lambda v: len(v) == 32 and all(c in "0123456789abcdef" for c in v.lower()),
}
_problems = [n for n in _HARDCODED if not _HARDCODED[n].strip()]
for _name, _check in _FORMAT_HINTS.items():
    _val = _HARDCODED.get(_name, "")
    if _val and not _check(_val):
        print(f"  WARNING: {_name} doesn't look right (got: {_val[:12]}...)")
if _problems:
    raise SystemExit(f"Empty value(s): {_problems}")

os.environ.setdefault("REDIS_KEY_PREFIX", "vastralook:")
print("✅ STEP_INIT_SECRETS: All credentials loaded")
for _name, _val in _HARDCODED.items():
    _shown = _val if len(_val) <= 10 else f"{_val[:6]}...{_val[-4:]}"
    print(f"  {_name}: {_shown} (len={len(_val)})")


# ----------------------------------------------------------------------------
# STEP_INSTALL_DEPS: Python packages + Chrome + Edge
# ----------------------------------------------------------------------------
import subprocess, sys
print("\n" + "=" * 70)
print("🔧 STEP_INSTALL_DEPS: Installing all dependencies")
print("=" * 70)

# Python packages
for _pkg in ("bullmq", "psycopg2-binary", "boto3", "selenium", "Pillow",
             "websockets", "nest_asyncio", "undetected-chromedriver",
             "webdriver-manager", "pyvirtualdisplay", "setuptools"):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", _pkg], check=False)
print("  ✅ Python packages installed")

# Google Chrome
subprocess.run(["apt-get", "-qq", "update"], check=False)
subprocess.run(["apt-get", "-qq", "install", "-y", "google-chrome-stable"], check=False)
print("  ✅ Google Chrome installed")

# Microsoft Edge (for watermark removal — completely separate browser)
print("  📦 Installing Microsoft Edge...")
subprocess.run(["bash", "-c",
    "curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /tmp/microsoft.gpg && "
    "install -o root -g root -m 644 /tmp/microsoft.gpg /etc/apt/trusted.gpg.d/ && "
    "echo 'deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main' > /etc/apt/sources.list.d/microsoft-edge.list && "
    "apt-get update -qq && apt-get install -y -qq microsoft-edge-stable"
], check=False)
_edge_bin = None
for _ep in ["/usr/bin/microsoft-edge-stable", "/usr/bin/microsoft-edge", "/opt/microsoft/msedge/msedge"]:
    if os.path.exists(_ep):
        _edge_bin = _ep
        break
if _edge_bin:
    print(f"  ✅ Microsoft Edge installed: {_edge_bin}")
else:
    print("  ⚠️ Edge install failed — watermark removal will use Chrome fallback")

print("✅ STEP_INSTALL_DEPS: Complete\n")
