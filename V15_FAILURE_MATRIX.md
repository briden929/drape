# V15 FAILURE MATRIX

## Failure Isolation Analysis

| Failure Type | Impact | Isolation | Recovery |
|--------------|--------|-----------|----------|
| T0 browser crash | T0 only | T1, T2, T3 unaffected | Recreate T0 driver |
| W0 crash | W0 only | W1, W2, W3 unaffected | Recreate W0 driver |
| Single job failure | Job only | Other jobs unaffected | Retry or mark FAILED |
| Raw download failure | T resource released | Job marked FAILED | T available for next job |
| WMR download failure | WMR resource released | Job marked FAILED | WMR tab available |
| DB failure | Job fails | Other jobs unaffected | Retry DB operation |
| R2 failure | Job fails | Other jobs unaffected | Retry R2 upload |
| Credits failure | Warning only | Job continues | Log warning |
| BullMQ disconnect | Job processing paused | Worker continues | Reconnect to Redis |
| Chrome crash | Single driver affected | Other drivers unaffected | Recreate driver |
| Worker crash | All jobs fail | Depends on state | Graceful shutdown |
| Event loop crash | All async tasks fail | None | Restart worker |

## Failure Propagation Prevention

1. **T resource crash isolation:** Each T driver is independent. Crash in T0 does not affect T1, T2, T3.
2. **WMR crash isolation:** Each WMR profile is independent. Crash in W0 does not affect W1, W2, W3.
3. **Job failure isolation:** Each job runs in its own context. Failure in one job does not affect others.
4. **Download lifecycle separation:** T resource release at DOWNLOAD START, not download completion. WMR resource release at DOWNLOAD PNG START.
5. **Credits failure isolation:** Credits failure does not block job completion.
6. **DB failure isolation:** DB failure is isolated to single job.
7. **Browser recovery:** Failed browser recreated without affecting other browsers.

## Historical Failures

### Bug: Global Browser Failure (V9-V13)
- Single browser crash killed entire worker
- Fixed in V14 N2N: Per-resource driver independence

### Bug: Global WMR Failure (V9-V13)
- Single WMR crash killed entire worker
- Fixed in V14 N2N: Per-profile WMR independence

### Bug: Credits Failure Blocking Job (V9-V13)
- Credits failure caused job to fail entirely
- Fixed in V14 N2N: Credits failure is warning only

### Bug: T Resource Permanent Occupation (V9-V13)
- T resource not released until raw download completed
- Fixed in V14 N2N: T released at DOWNLOAD START

### Bug: WMR Resource Permanent Occupation (V9-V13)
- WMR resource not released until WMR download completed
- Fixed in V14 N2N: WMR released at DOWNLOAD PNG START
