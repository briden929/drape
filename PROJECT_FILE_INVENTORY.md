# Project File Inventory

**Total Files:** 549
**Python Files:** 477
**Markdown Files:** 42
**Other Files:** 30

## File Categories Summary

### A. Production Worker Versions
- FULL_QUEUE_WORKER_V9_FINAL.py (V9, OBSOLETE)
- FULL_QUEUE_WORKER_V10_FINAL.py (V10, OBSOLETE)
- FULL_QUEUE_WORKER_V11.py (V11, REFERENCE)
- FULL_QUEUE_WORKER_V11_FINAL.py (V11, REFERENCE)
- FULL_QUEUE_WORKER_V12_FINAL.py (V12, REFERENCE)
- FULL_QUEUE_WORKER_V13_FINAL.py (V13, REFERENCE)
- FULL_QUEUE_WORKER_V14_FINAL.py (V14, PRODUCTION CANDIDATE, 3521 lines)
- FULL_QUEUE_WORKER_V14_N2N_FINAL.py (V14 N2N, PRODUCTION CANDIDATE, 3758 lines)
- FULL_QUEUE_WORKER_V15_FORENSIC_REBUILT.py (V15, SKELETON, 377 lines)

### B. ECOM Implementation
- ecom_source.py (4237 lines - proven browser operations)
- ecom_source_clean.py (4237 lines)
- ecom_script.py (132000 lines)
- copy_of_ecom_combo_photoshoot_order.py (158989 lines)

### C. Login Implementations
- google_login_raw.py (1109 lines - 7 detection methods)
- new_login.py (25418 lines)
- ultra_login_block.py (24419 lines)
- apply_login.py (4566 lines)
- dump_ecom_login.py / dump_ecom_login2.py / dump_ecom_login3.py

### D. Build/Generator Scripts
- generator.py (10191 lines)
- build_v11.py (26283 lines)
- build_v14.py (17971 lines)
- build_v14_part1.py (34691 lines)
- build_n2n_v1.py / build_n2n_v2.py
- gen_v14_clean_2/3/4.py (33500+ lines each)
- refactor_n2n_v15.py (6452 lines)
- run_generator.py (30351 lines)
- create_final.py (6791 lines)

### E. Patch Scripts
- apply_patch.py through apply_patch6.py
- apply_v14_fixes.py (4664 lines)
- fix_v14_entrypoint.py, fix_v14_final_audit.py
- fix_import.py, fix_missing.py, fix_missing_again.py
- fix_errors.py, fix_unicode.py, fix_cookies.py
- patch_v9.py through patch_v9_16.py
- patch_v10_1.py through patch_v10_11.py
- patch_wmr.py, patch_flash.py, patch_gemini.py, patch_send.py
- patch_upload.py, patch_states.py, patch_script.py
- apply_arch.py, apply_all.py, apply_fixes.py
- fix_v20.py through fix_v20_5.py

### F. Test/Validation Scripts
- test_v14.py, test_v14_mock.py
- run_unit_tests.py (4205 lines)
- run_final_tests.py (3473 lines)
- run_arch_tests.py (4154 lines)
- test_firstfree.py
- check_*.py (40+ files)
- audit_v14.py, final_audit.py, verify.py, ast_val.py
- test_ast2.py (6408 lines)
- test_ast_v12.py, test_ast_v13.py

### G. Source Dumps/Extracts
- v11_funcs.json (196463 bytes)
- v11_syms.json (51035 bytes)
- v13_funcs.json (113710 bytes)
- v13_syms.json (132176 bytes)
- v13_classes.json (18469 bytes)
- v13_clean_ast.py (v1-v5, 98101+ bytes each)
- extracted.py (26810 bytes)
- v11_raw.py (169262 lines)
- v11_work.py (160314 lines)
- v13_work.py (123108 lines)
- v13_working.py (153524 lines)
- main_body.txt (10535 bytes)
- entrypoint_tail.txt (5937 bytes)

### H. V3-V20 Work Files
- v3_work.py through v20_work.py
- queue_worker_v3_cell_part_A/B.py
- worker_part1-4.py
- modules_block.py, top.py, middle.py, bottom.py
- auto_funcs.py, build_script.py, auto_colab.py
- user_pasted_code.py (196993 lines)

### I. Documentation/Analysis Files
- MASTER_INSTRUCTION.txt (46784 bytes)
- All .md files in root directory

### J. Backup Files
- backup/FULL_QUEUE_WORKER_V14_FINAL_before_asyncfix_*.py
- backup/FULL_QUEUE_WORKER_V14_FINAL_before_ecm_audit_*.py
- backup/FULL_QUEUE_WORKER_V14_FINAL_before_ecom_audit_*.py

### K. Other Files
- __pycache__/*.pyc (compiled caches)
- chunks/01-08_*.py (chunk files)
- secrets_and_modules.py (0 bytes - EMPTY)
- dump.txt (0 bytes - EMPTY)

## Key Findings

1. V14 N2N Final is the most complete production candidate at 3758 lines
2. V15 Forensic Rebuilt exists as a 377-line skeleton requiring completion
3. ECOM source contains the most mature browser operations (4237 lines)
4. google_login_raw.py contains proven login with 7 detection methods (1109 lines)
5. Multiple duplicate functions exist across versions (see DUPLICATE_CODE_ANALYSIS.md)
6. Edge contamination exists in some versions (apply_improvements.py, build_script.py)
7. The V15 rebuild correctly implements dependency bootstrap and FirstFreeBroker
8. The V15 rebuild lacks real Selenium, BullMQ, R2, and DB implementations
