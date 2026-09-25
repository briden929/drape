# FINAL ARCHITECTURE

- **Gemini Pool**: 4 persistent Chrome profiles (T0-T3). Driven directly by asyncio tasks.
- **WMR Pool**: 4 persistent Chrome profiles (W0-W3). 2 tabs per profile. Driven by background ThreadPools to prevent Selenium blocking the event loop.
- **Broker**: Global `FirstFreeBroker` enforcing strict release-order FIFO allocation.
- **Download Registry**: Maps Chrome CDP `guid` to `job_id`.
