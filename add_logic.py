with open('build_v14_part1.py', 'a', encoding='utf-8') as f:
    f.write("""
for fname in [
    'get_chrome_job_dir', 'get_wmr_job_dir', 'get_wmr_staging_dir', 'get_final_output_dir',
    'validate_image_file', 'convert_to_webp', 'upload_to_r2',
    'create_persistent_chrome_driver', 'create_wmr_chrome_driver',
    'comprehensive_login_check', 'handle_google_login_fast', 'open_new_chat_and_reload',
    'perform_robust_upload', '_wmr_click_download', 'check_chrome_driver_health',
    'wait_for_attachment_chip', '_hover_and_download', '_click_download_button',
    '_wmr_find_file_input', '_wmr_check_status', '_direct_fetch_image', 'snapshot_urls',
    'check_new_image', 'check_new_image_lenient', 'wait_for_image', 'set_download_behavior',
    'check_limit_or_refusal', 'start_new_chat', 'click_plus_button', 'click_create_image',
    '_in_image_mode', 'wait_for_image_mode', 'activate_create_image_mode', 'select_gemini_model',
    'handle_consent', 'click_upload_files_in_drawer', 'find_file_input', 'jsdrop_single',
    'save_debug_screenshot', 'upload_images', '_attach_images_together', '_attach_one_image',
    'get_editor', '_strip_ws', '_verify_editor_content', '_clear_editor', 'type_prompt', 'click_send',
    'ensure_flash_mode', 'ensure_create_image_mode', 'verify_attachment_count',
    '_inject_prompt_atomic', '_click_send_button', 'verify_generation_started',
    '_hover_and_dl_single_click', 'nb_check_image', '_click_menu_item', 'turn_off_gemini_activity'
]:
    # Prefer V11 if exists, else V13
    if fname in v11:
        add(v11[fname])
    elif fname in v13:
        add(v13[fname])
    else:
        print(f"Missing func: {fname}")
""")
