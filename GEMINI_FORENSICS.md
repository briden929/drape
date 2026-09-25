# Gemini Forensics

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
