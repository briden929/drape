# Source of Truth Matrix

## Subsystem Analysis

### Dependency Bootstrap
| Subsystem | Best File | Exact Function | Version | Why Preferred | Tested |
|-----------|-----------|---------------|---------|---------------|--------|
| Python deps bootstrap | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `bootstrap_dependencies()` | V14 N2N | 4-phase bootstrap: check, install, verify, invalidate caches | Static |
| System deps bootstrap | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `verify_system_dependencies()` | V14 N2N | Checks Chrome, Xvfb, x11vnc, websockify, fluxbox | Static |
| Colab detection | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `is_running_in_notebook()` | V14 N2N | Checks for IPython environment | Static |

### Chrome Creation
| Subsystem | Best File | Exact Function | Version | Why Preferred | Tested |
|-----------|-----------|---------------|---------|---------------|--------|
| Gemini driver creation | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `create_gemini_driver(tid)` | V14 N2N | Profile cloning, CDP injection, download prefs | Static |
| WMR driver creation | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `create_wmr_chrome_driver(worker_id)` | V14 N2N | Isolated profiles, Chrome-only, staging dirs | Static |
| Chrome options | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | ChromeOptions configuration | V14 N2N | --no-sandbox, --disable-dev-shm-usage, --user-data-dir | Static |

### Gemini T0-T3 Lifecycle
| Subsystem | Best File | Exact Function | Version | Why Preferred | Tested |
|-----------|-----------|---------------|---------|---------------|--------|
| Profile management | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `create_gemini_driver()` | V14 N2N | Clones master profile, removes SingletonLock | Static |
| Resource assignment | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `FirstFreeBroker.acquire()` | V14 N2N | Sequential ordering via heapq | Static |
| Resource release | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `FirstFreeBroker.release()` | V14 N2N | Monotonic sequence preserves release order | Static |

### Gemini Login Detection
| Subsystem | Best File | Exact Function | Version | Why Preferred | Tested |
|-----------|-----------|---------------|---------|---------------|--------|
| Login detection | google_login_raw.py | `comprehensive_login_check()` | V11 | 7 detection methods, confidence scoring | Runtime (Colab) |
| Google account auth | google_login_raw.py | `verify_google_account_auth()` | V11 | Multi-method verification | Static |
| Cookie persistence | google_login_raw.py | Cookie loading/saving | V11 | Pickle-based cookie persistence | Static |

### File Upload / Download
| Subsystem | Best File | Exact Function | Version | Why Preferred | Tested |
|-----------|-----------|---------------|---------|---------------|--------|
| CDP download behavior | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `set_tab_download_dir()` | V14 N2N | `Browser.setDownloadBehavior` with `allowAndName` | Static |
| Download GUID | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `Browser.downloadWillBegin` | V14 N2N | CDP event for GUID correlation | Static |
| Download directory | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `get_chrome_job_dir()` | V14 N2N | Per-T-slot job directories | Static |

### WMR Pipeline
| Subsystem | Best File | Exact Function | Version | Why Preferred | Tested |
|-----------|-----------|---------------|---------|---------------|--------|
| WMR driver creation | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `create_wmr_chrome_driver()` | V14 N2N | W0-W3 isolated profiles | Static |
| WMR staging | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `get_wmr_staging_dir()` | V14 N2N | Per-profile staging directories | Static |
| WMR download PNG | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `_wmr_click_download()` | V14 N2N | Exact "Download PNG" button click | Static |
| WMR resource release | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `WMR_BROKER.release()` | V14 N2N | Release at DOWNLOAD START confirmed | Static |

### Download Ownership
| Subsystem | Best File | Exact Function | Version | Why Preferred | Tested |
|-----------|-----------|---------------|---------|---------------|--------|
| GUID correlation | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `DownloadRegistry` class | V14 N2N | GUID -> job_id mapping | Static |
| Download tracking | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `Browser.downloadWillBegin` | V14 N2N | CDP event-based tracking | Static |

### R2/DB/Credits
| Subsystem | Best File | Exact Function | Version | Why Preferred | Tested |
|-----------|-----------|---------------|---------|---------------|--------|
| R2 upload | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `boto3` client | V14 N2N | Environment variable credentials | Static |
| DB connection | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `psycopg2` connection pool | V14 N2N | Threaded connections, idempotent updates | Static |
| Credits settlement | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `credits.decrement_credits()` | V14 N2N | Post-completion, failure isolation | Static |
| BullMQ completion | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `process_bullmq_job()` | V14 N2N | Return status after all stages complete | Static |

### Asyncio/Colab
| Subsystem | Best File | Exact Function | Version | Why Preferred | Tested |
|-----------|-----------|---------------|---------|---------------|--------|
| Colab event loop | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `is_running_in_notebook()` | V14 N2N | Checks IPython, uses `loop.create_task()` | Static |
| Standalone entrypoint | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `asyncio.run(main())` | V14 N2N | Only when not in notebook | Static |
| Thread-safe futures | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `resolve_future_once()` | V14 N2N | `loop.call_soon_threadsafe()` for Selenium | Static |
| Double-start guard | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | `_worker_started` flag | V14 N2N | Prevents duplicate worker initialization | Static |
