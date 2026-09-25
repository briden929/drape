import os

base = r'C:\Users\PC\.gemini\antigravity\scratch\Reddis'

def write_report(filepath, content):
    full_path = os.path.join(base, filepath)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written: {filepath}")

# ============ 4. BROWSER_OPERATION_SOURCE_OF_TRUTH.md ============
browser_st = """# Browser Operation Source of Truth

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
"""
write_report("BROWSER_OPERATION_SOURCE_OF_TRUTH.md", browser_st)

# ============ 5. PATCH_HISTORY.md ============
patch_hist = """# Patch History

## Overview

The project went through extensive patch-generation cycles. Many patches produced duplicate code, introduced regressions, or were later reversed.

## Patch Generations

### Phase 1: V9-V10 Patches
- `patch_v9.py` through `patch_v9_16.py` - Sequential V9 improvements
- `patch_v10_1.py` through `patch_v10_11.py` - Sequential V10 improvements
- `patch_wmr.py`, `patch_flash.py`, `patch_gemini.py` - Feature-specific patches
- `patch_script.py` (21218 lines) - Major patch script

### Phase 2: V11-V13 Patches
- `fix_v11.py` (8163 lines) - V11 fixes
- `fix_v12.py`, `fix_v13_final.py`, `fix_v13_final2.py` - V12/V13 fixes
- `modify_v13.py` (14073 lines) - V13 modifications
- `apply_improvements.py` (56876 lines) - Major improvements

### Phase 3: V14 Patches
- `apply_patch.py` (9501 lines) - Main patch framework
- `apply_patch2.py` through `apply_patch6.py` - Sequential patches
- `apply_v14_fixes.py` (4664 lines) - V14 specific fixes
- `fix_v14_entrypoint.py` (16542 lines) - Entrypoint fix
- `fix_v14_final_audit.py` (9869 lines) - Final audit fix
- `fix_missing.py`, `fix_missing_again.py` - Missing code fixes
- `fix_import.py`, `fix_imports_2.py` - Import fixes
- `fix_preflight_indent.py`, `fix_preflight_regex.py` - Preflight fixes
- `clean_mojibake.py`, `utf8_fix.py` - Encoding fixes
- `update_omits.py`, `update_omits_2.py` - Omit updates

### Phase 4: N2N Patches
- `build_n2n_v1.py` (4003 lines) - N2N v1 build
- `build_n2n_v2.py` (5811 lines) - N2N v2 build
- `refactor_n2n_v15.py` (6452 lines) - N2N v15 refactor
- `gen_v14_clean_2.py`, `gen_v14_clean_3.py`, `gen_v14_clean_4.py` - Clean generators

## Patch Analysis

### apply_patch.py
- **Input:** V14 N2N Final source
- **Output:** Modified V14 N2N source
- **Changes:** Injected dependency bootstrap, fixed entrypoint, added login checks
- **Result:** Partially successful, introduced duplicate definitions

### apply_v14_fixes.py
- **Input:** V14 N2N source
- **Changes:** Added `GeminiWorkerPool`, `WmrWorkerPool`, `BullMQ` integration
- **Result:** Introduced duplicate `_run_wmr_logic` and `_finalize_job` definitions

### fix_v14_entrypoint.py
- **Input:** V14 N2N source
- **Changes:** Fixed Colab entrypoint to use `loop.create_task(main())`
- **Result:** Successful, double-start guard added

### fix_missing_again.py
- **Input:** V14 N2N source
- **Changes:** Added missing `_ensure_driver` and `_fail_job` functions
- **Result:** Partial, some functions still missing

## Known Issues from Patches

1. **Duplicate definitions:** `_run_wmr_logic`, `_finalize_job`, `startup_preflight` defined multiple times
2. **Stale code:** Old function definitions shadowed by later patches
3. **Edge contamination:** `apply_improvements.py` introduced Edge/`msedgedriver` references
4. **Mojibake:** Encoding artifacts from patch application
5. **Hardcoded credentials:** Patches sometimes hardcoded `_drive_cookies` paths
6. **Tuple-vs-Path issues:** Some patches used tuples where Path objects expected
"""
write_report("PATCH_HISTORY.md", patch_hist)
print("Patch history done")
