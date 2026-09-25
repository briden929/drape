# Duplicate Code Analysis

## Most Critical Duplicates

### 1. _run_wmr_logic
**Defined in:** FULL_QUEUE_WORKER_V14_N2N_FINAL.py, FULL_QUEUE_WORKER_V14_FINAL.py, gen_v14_clean_2/3/4.py, apply_arch.py, build_v14_part1.py, FULL_QUEUE_WORKER_V13_FINAL.py, v13_arch.py, clean_extracted.py, v11_raw.py, v12_work.py, v13_work.py, v13_working.py, v20_work.py, etc.

**Issue:** Multiple definitions, old versions may shadow newer ones.
**Risk:** Stale implementation still reachable.

### 2. _finalize_job
**Defined in:** gen_v14_clean_2/3/4.py, FULL_QUEUE_WORKER_V14_N2N_FINAL.py, FULL_QUEUE_WORKER_V14_FINAL.py, apply_arch.py, build_v14_part1.py, FULL_QUEUE_WORKER_V13_FINAL.py, etc.

**Issue:** Same as _run_wmr_logic - multiple definitions across versions.

### 3. preflight_validate_runtime
**Defined in:** v15_work.py, patch_v18.py, gen_v12.py, v18_work.py, apply_arch.py, v13_base.py, v17_work.py, v12_builder.py, add_preflight.py, bottom.py, FULL_QUEUE_WORKER_V11_FINAL.py, v13_modified.py, v20_work.py, test_ast2.py, FULL_QUEUE_WORKER_V10_FINAL.py, final_build.py, v13_working.py, apply_all.py, FULL_QUEUE_WORKER_V12_FINAL.py, build_v18.py, v16_work.py, v19_work.py, FULL_QUEUE_WORKER_V9_FINAL.py

**Issue:** 20+ definitions across versions. Must consolidate.

### 4. startup_preflight
**Defined in:** gen_v14_clean_2/3/4.py, FULL_QUEUE_WORKER_V14_FINAL.py, build_v14_part1.py, apply_all.py, add_main.py, new_startup.py, build_v14.py, FULL_QUEUE_WORKER_V14_N2N_FINAL.py

**Issue:** 8+ definitions. Latest version should override but may not.

### 5. is_running_in_notebook
**Defined in:** gen_v14_clean_3/4.py, FULL_QUEUE_WORKER_V14_N2N_FINAL.py, FULL_QUEUE_WORKER_V14_FINAL.py, fix_v14_entrypoint.py, new_startup.py, apply_patch.py, apply_v14_fixes.py, gen_v14_clean_2.py, FULL_QUEUE_WORKER_V14_FINAL_before_asyncfix.py

**Issue:** Multiple definitions, some may be stale.

### 6. create_chrome_driver
**Defined in:** generate_final_v3.py, FULL_QUEUE_WORKER_V4_ONE_CELL.py, FULL_QUEUE_WORKER_V14_N2N_TEST.py, v9_work.py, worker_part3.py, v12_work.py, FULL_QUEUE_WORKER_V9_FINAL.py, FULL_QUEUE_WORKER_V8_FINAL.py, apply_improvements.py, FULL_QUEUE_WORKER_V11.py, patch_and_build.py, FULL_QUEUE_WORKER_V5_FINAL.py, FULL_QUEUE_WORKER_V7_FINAL.py, v11_raw.py, temp_v9.py, FULL_QUEUE_WORKER_V6_FINAL.py, FULL_QUEUE_WORKER_V9.1_FINAL.py, v11_work.py, queue_worker_v3_cell_part_A.py, build_script.py, v10_work.py, generate_worker_v3_perfect.py, FULL_QUEUE_WORKER_V3_ONE_CELL.py

**Issue:** 20+ definitions. The V14 N2N version is `create_gemini_driver(tid)` which should be authoritative.

### 7. main()
**Defined in:** FULL_QUEUE_WORKER_V12_FINAL.py, FULL_QUEUE_WORKER_V13_FINAL.py, v13_modified.py, gen_v12.py, script_1.py, v13_arch.py, ecom_source.py, modify_v13.py, auto_colab.py, v13_base.py, v12_builder.py, ecom_source_clean.py, gemini_generate_v3.py, ecom_script.py, script_2.py, user_pasted_code.py, v13_working.py, copy_of_ecom_combo_photoshoot_order.py

**Issue:** 18+ definitions. V14 N2N version is most complete.

## Resolution Strategy

1. The V14 N2N Final should be the authoritative source for all production functions
2. All other versions are historical references
3. Patch scripts that modify functions should be reviewed for duplicate creation
4. V15 Forensic Rebuilt should consolidate to single definitions

## Duplicate Detection Summary

Total duplicate function definitions found: ~15+ functions defined 5+ times each
Most duplicated: _run_wmr_logic, _finalize_job, create_chrome_driver, main(), preflight_validate_runtime, startup_preflight, is_running_in_notebook
