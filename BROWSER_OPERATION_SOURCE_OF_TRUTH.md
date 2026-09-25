# Browser Operation Source of Truth

## ECOM vs V11 vs V14 Comparison

### Login Detection

**ECOM (`ecom_source.py`):** Uses `handle_login(drv, wait)` function with multi-step Google login flow. Includes email entry, password entry, verification handling, and session validation. Uses `driver.find_element(By.ID, "passwordNext").click()` for password submission.

**google_login_raw.py:** Implements 7 independent login detection methods:
1. Profile avatar detection (XPath: `//div[@aria-label='Google Account']//img`)
2. Email text detection (regex pattern matching)
3. Account elements detection
4. No-signin button detection
5. URL pattern checking
6. Auth cookie checking (SID, HSID, SSID, APISID, SAPISID, LOGIN_INFO)
7. Profile button detection

`comprehensive_login_check()` aggregates all 7 methods with confidence scoring (>=43% = logged in).

**V14/FULL_QUEUE_WORKER_V14_N2N_FINAL.py:** Uses `verify_gemini_auth()` and `comprehensive_login_check()` from build_n2n_v1.py pattern. Cookie-based authentication with `_drive_cookies` path.

### Flash/Create Image Navigation

**ECOM (`ecom_source.py`):** Most mature implementation:
- `switch_to_flash(drv, wait)` - Selects Flash mode from mode picker
- `click_plus_button(drv, wait)` - Clicks + button to create image
- `_click_flash_in_picker(drv)` - Clicks Flash option
- `_verify_flash_selected(drv)` - Verifies Flash mode active
- `_activate_image_mode_and_upload()` - Full activation flow

**V14 N2N:** Uses `_click_flash_in_picker()`, `_verify_flash_selected()`, `_verify_editor_content()` from extracted functions.

### File Upload

**ECOM (`ecom_source.py`):**
- `_upload_ref_images()` - Uploads reference images to drawer
- `_verify_attachment_count()` - Verifies uploaded count
- Uses clipboard-based prompt injection
- `_click_send_button()` - Clicks Gemini send button

**V14 N2N:** Uses `_upload_files_to_drawer()`, `_verify_attachment_count()`, `_click_send_button()` from extracted functions.

### Generation Detection

**ECOM:** Uses polling to detect generation completion. Checks for generated image in output area.

**V14 N2N:** Uses `_is_gemini_processing()`, `_has_generated_image()` to detect generation state.

### WMR Operations

**ECOM (`ecom_source.py`):**
- Navigates to `https://logo-remover-fawn.vercel.app/gemini`
- Uploads image
- Waits for "Download PNG" button
- Clicks exact "Download PNG" button
- Saves to WR/ directory

**V14 N2N:** Uses `_wmr_click_download()`, `_wmr_check_status()`, `_wmr_find_file_input()` for WMR operations.

### Download Handling

**V14 N2N (Best):**
- `Browser.setDownloadBehavior` with `allowAndName`
- CDP `Browser.downloadWillBegin` event for GUID
- `Browser.downloadProgress` event for completion tracking
- `set_tab_download_dir()` for per-tab download directories
- Download registry maps GUID -> job_id

**ECOM:** Uses `tab_dl_dir` function and file-based download detection.

## Selected Strategies (Best Implementation)

| Operation | Source | Reason |
|-----------|--------|--------|
| Login detection | google_login_raw.py | 7 methods, confidence scoring, proven runtime |
| Flash selection | ecom_source.py | Most mature DOM operations |
| File upload | ecom_source.py | Clipboard injection, verification |
| Download tracking | V14 N2N CDP | GUID-based, not filename-based |
| WMR "Download PNG" | V14 N2N | Exact button click, GUID correlation |
| Chrome creation | V14 N2N | Profile cloning, CDP, Chrome-only |
| First-Free scheduling | V14 N2N | heapq + monotonic sequence |
| Entrypoint | V14 N2N | Colab/Standalone dual support |
