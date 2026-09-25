# Test Evidence Matrix

## Test Classification

### STATIC TESTS (No runtime execution)
| Test | What It Proves | What It Does NOT Prove | Trust Level |
|------|---------------|----------------------|-------------|
| ast_val.py | AST is parseable | No browser/runtime behavior | Low |
| check_ast.py | AST structure valid | No execution | Low |
| check_classes.py | Class definitions exist | No runtime behavior | Low |
| test_ast2.py (6408 lines) | AST validates functions | No browser/runtime | Low |
| test_ast_v12.py | V12 AST valid | No execution | Low |
| test_ast_v13.py | V13 AST valid | No execution | Low |
| py_compile checks | Syntax valid | No execution | Low |
| check_dup.py / check_dups.py | No duplicate definitions | No execution | Low |
| check_edge.py | No Edge references | No runtime | Low |
| check_moji.py | No mojibake | No runtime | Low |

### MOCK TESTS (Simulated, no browser)
| Test | What It Proves | What It Does NOT Prove | Trust Level |
|------|---------------|----------------------|-------------|
| test_v14_mock.py | State machine transitions | No real browser | Low |
| test_firstfree.py | First-Free ordering | No real browser | Low |
| test_bounds.py | Boundary conditions | No execution | Low |

### RUNTIME TESTS (Limited environment)
| Test | What It Proves | What It Does NOT Prove | Trust Level |
|------|---------------|----------------------|-------------|
| run_unit_tests.py | Basic import/structure | No Chrome/Google/Gemini | Medium |
| run_final_tests.py | Integration structure | No real R2/DB/Redis | Medium |
| run_arch_tests.py | Architecture patterns | No browser execution | Medium |
| FULL_QUEUE_WORKER_V14_N2N_TEST.py | N2N structure | No real browser | Low |

### STATIC ANALYSIS (AST/Code inspection)
| Test | What It Proves | Trust Level |
|------|---------------|-------------|
| SECURITY_FORENSICS.md scan | No hardcoded secrets found | Medium |
| DUPLICATE_CODE_ANALYSIS.md | Function duplication map | Medium |
| check_cdp.py | CDP event patterns | Medium |
| check_broker.py | Broker implementation | Medium |

### PROVEN BY REAL RUNTIME (Colab)
| Test | What It Proves | Trust Level |
|------|---------------|-------------|
| google_login_raw.py | Login detection works | HIGH (proven in Colab) |
| ecom_source.py | ECOM browser operations work | HIGH (proven in Colab) |
| V14 N2N bootstrap | Dependency install works | MEDIUM (Colab tested) |

### BLOCKED BY ENVIRONMENT
| Test | Status |
|------|--------|
| Real Gemini generation | No Gemini API access in environment |
| Real WMR processing | No WMR service in environment |
| Real R2 upload | No R2 credentials in environment |
| Real DB connection | No PostgreSQL in environment |
| Real BullMQ/Redis | No Redis server in environment |
| Full end-to-end job | Requires all above services |

## Critical Distinction

**PREVIOUS AUDIT REPORTS REPORTED "STATIC PASS"** while real Chrome/Google/Gemini/WMR/R2/DB/Redis/full-job execution was NOT performed.

This distinction is MANDATORY:
- STATIC PASS = code parses and has correct structure
- RUNTIME PROOF = Chrome launched, Gemini generated, WMR processed, R2 uploaded, DB updated

Current V15 Forensic Rebuilt has ONLY been validated by static analysis and py_compile.

## Test Count by Type
- Static/AST: ~30+ scripts
- Mock: ~5 scripts  
- Runtime (limited): ~10 scripts
- Browser (proven): 2 (google_login_raw.py, ecom_source.py)
- Blocked: All full-end-to-end tests
