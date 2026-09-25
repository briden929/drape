# Patch History

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
