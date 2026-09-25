import sys; sys.stdout.reconfigure(encoding="utf-8")
import ast

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V9.1_FINAL.py', 'r', encoding='utf-8', errors='replace') as f:
    source = f.read()

tree = ast.parse(source)
funcs = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

targets = [
    "ensure_flash_mode", "is_create_image_mode", "ensure_create_image_mode",
    "perform_robust_upload", "verify_attachment_count", "_inject_prompt_atomic",
    "_click_send_button", "verify_generation_started", "nb_check_image",
    "_hover_and_dl_single_click", "snapshot_urls", "_direct_fetch_cdp"
]

for t in targets:
    print(f"{t}: {t in funcs}")
