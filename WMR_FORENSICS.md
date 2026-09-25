# WMR Forensics

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
