import sys; sys.stdout.reconfigure(encoding="utf-8")
import ast
import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V9.1_FINAL.py', 'r', encoding='utf-8', errors='replace') as f:
    source = f.read()

source = re.sub(r'[\x80-\xFF]', '', source)
source = re.sub(r'[^\x00-\x7F]+', '', source)

tree = ast.parse(source)

allowed_funcs = {
    "log", "get_chrome_job_dir", "get_wmr_job_dir", "get_wmr_staging_dir",
    "get_final_output_dir", "run_cmd", "_get_pool", "_mark_used", "_checkout",
    "db_connection", "db_borrow", "credits_settle_look", "credits_refund_look",
    "fs_configured", "_r2_client", "upload_to_r2", "fashion_tryon_prompt",
    "download_remote_image", "push_generation", "_port_open", "_wait_for_port",
    "_kill_port", "start_display", "start_vnc", "start_novnc_tunnel",
    "is_logged_in_method_1_profile_avatar", "is_logged_in_method_2_email_text",
    "is_logged_in_method_3_account_elements", "is_logged_in_method_4_no_signin",
    "is_logged_in_method_5_url_check", "is_logged_in_method_6_cookies",
    "is_logged_in_method_7_profile_button", "comprehensive_login_check",
    "extract_verification_number", "extract_page_details", "display_page_info",
    "take_screenshot", "save_cookies", "load_cookies",
    "detect_push_notification_verification", "wait_for_push_notification_approval",
    "handle_verification_code_with_retry", "handle_google_login_fast",
    "turn_off_gemini_activity", "convert_to_webp", "validate_image_file",
    "safe_execute_script", "_wmr_expose_file_inputs", "ensure_flash_mode",
    "is_create_image_mode", "ensure_create_image_mode", "perform_robust_upload",
    "verify_attachment_count", "_inject_prompt_atomic", "_click_send_button",
    "verify_generation_started", "nb_check_image", "_hover_and_dl_single_click",
    "snapshot_urls", "_direct_fetch_cdp", "_send_btn_enabled", "_is_gemini_processing"
}

extracted = []
for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        extracted.append(ast.unparse(node))
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.name in allowed_funcs:
            extracted.append(ast.unparse(node))
    elif isinstance(node, ast.Assign):
        # Allow only constant globals, no state globals
        is_allowed = False
        for t in node.targets:
            if isinstance(t, ast.Name):
                if t.id.isupper() or t.id in ["_pool", "_pool_lock", "_last_used", "_fallbacks", "WORKER_ID", "QUEUE_NAME"]:
                    is_allowed = True
        if is_allowed:
            extracted.append(ast.unparse(node))

top_code = "\n".join(extracted)

with open('v13_clean_ast.py', 'w', encoding='utf-8') as f:
    f.write(top_code)
print("Clean AST extracted.")
