# FINAL FAILURE MATRIX

| SCENARIO | IMPACT | RECOVERY |
|---|---|---|
| T0 crashes | Job fails, T0 marked dead | T0 Chrome killed and restarted |
| R2 upload fails | Job fails | BullMQ retry triggered |
| DB disconnects | Reconnect | Idempotent updates |
| Credits fail | Job marked failed | Settlement rolled back |
