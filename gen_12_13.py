import os

base = r'C:\Users\PC\.gemini\antigravity\scratch\Reddis'

def write_report(filepath, content):
    full_path = os.path.join(base, filepath)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written: {filepath}")

# ============ 12. WMR_FORENSICS.md ============
WMR_CONTENT = r"""# WMR Forensics

## Source Files Analyzed

1. FULL_QUEUE_WORKER_V14_N2N_FINAL.py - Best WMR implementation
2. FULL_QUEUE_WORKER_V14_FINAL.py - V14 WMR
3. ecom_source.py - ECOM WMR operations
4. FULL_QUEUE_WORKER_V13_FINAL.py - V13 WMR
5. add_wmr_logic.py - WMR logic additions
6. build_v14.py - V14 builder with WMR
7. build_v14_part1.py - V14 part1 with WMR
8. v11_raw.py, v12_work.py, v13_work.py - Historical WMR

## WMR Architecture

### Profile Structure
W0-W3 profiles, each with 2 tabs (W0-T0, W0-T1, W1-T0, W1-T1, W2-T0, W2-T1, W3-T0, W3-T1)

### WMR Driver Creation
Chrome-only driver creation with isolated profiles.
Never uses Microsoft Edge.

### WMR Workflow
1. Acquire WMR resource (wmr_broker.acquire()) -> "W0-T0"
2. Upload raw PNG to WMR site
3. Wait for processing
4. Click exact "Download PNG" button
5. downloadWillBegin fires -> register GUID
6. WMR resource released immediately
7. Clean PNG download continues
8. Validate -> WebP -> R2 -> DB -> Credits

### WMR "Download PNG" Strategy
The WMR site uses https://www.pixelcut.ai/watermark-remover
or https://logo-remover-fawn.vercel.app/gemini
Exact "Download PNG" button identified by text content matching.

### WMR Resource Release
WMR resource is released when Download PNG START is confirmed (downloadWillBegin fires), NOT when:
- WMR processing begins
- PNG download finishes
- Clean file is fully written
- WebP is created
- R2 upload completes

### Historical Bugs
1. WMR Global Queue - Single queue caused competition
2. Edge Contamination - Some versions used Edge for WMR
3. No Tab Isolation - Multiple jobs using same tab
4. Filename-Based Detection - Used filename instead of GUID

## What Must Be Preserved
1. create_wmr_chrome_driver() - Chrome-only driver creation
2. get_wmr_staging_dir() - Per-profile staging
3. get_wmr_job_dir() - Per-job directory
4. WMR Download PNG click logic
5. WMR resource release at download START
6. WMR FirstFreeBroker scheduling
"""

write_report("WMR_FORENSICS.md", WMR_CONTENT)

# ============ 13. GEMINI_FORENSICS.md ============
GEMINI_CONTENT = r"""# Gemini Forensics

## Source Files Analyzed

1. FULL_QUEUE_WORKER_V14_N2N_FINAL.py - Best Gemini implementation
2. FULL_QUEUE_WORKER_V14_FINAL.py - V14 Gemini
3. ecom_source.py - ECOM Gemini operations
4. google_login_raw.py - Google/Gemini login
5. build_v14_part1.py - V14 part1 builder
6. v11_raw.py - V11 raw implementation
7. gen_v14_clean_2/3/4.py - Clean generators

## Gemini T Resource Model
T0, T1, T2, T3 = 4 persistent Chrome profiles.
Each has independent --user-data-dir, master profile cloning, SingletonLock cleanup.

## Gemini Workflow
1. Acquire T resource (gemini_broker.acquire()) -> "T0"
2. Launch Chrome with T0 profile
3. Navigate to https://gemini.google.com/app
4. Verify session active
5. Open new chat
6. Navigate to Flash mode -> Create Image
7. Upload reference images
8. Inject prompt via clipboard
9. Click Send
10. Wait for generation detection
11. Click download
12. downloadWillBegin fires -> register GUID
13. T resource released immediately
14. Raw download continues independently

## Flash/Create Image Navigation
The Gemini app uses a mode picker.
Exact DOM strategy: look for "mode picker", "flash", "pro" labels.
Click plus button to create image. Open file input drawer. Upload references.

## What Must Be Preserved
1. Profile cloning and SingletonLock management
2. Flash/Create Image navigation DOM strategies
3. Generation detection logic
4. resolve_future_once() for thread-safe futures
5. _click_flash_in_picker(), _verify_flash_selected()
6. _click_send_button(), _is_gemini_processing()
7. _has_generated_image() for image detection
"""

write_report("GEMINI_FORENSICS.md", GEMINI_CONTENT)
print("WMR/Gemini forensics done")
