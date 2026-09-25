# FINAL SOURCE OF TRUTH MATRIX

| SUBSYSTEM | SOURCE FILE | FUNCTION | WHY SELECTED |
|---|---|---|---|
| Dependency Bootstrap | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | bootstrap_dependencies | Safe importlib cache invalidation |
| Chrome Initialization | FULL_QUEUE_WORKER_V11.py | _create_driver | Tested options, CDP attached |
| Gemini Login | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | get_authentication_state | 2-stage state machine avoids false positive |
| Gemini Chat/Prompt | FULL_QUEUE_WORKER_V11.py | _wmr_prompt_and_send | Robust FileInputMissing exception |
| Gemini Download | FULL_QUEUE_WORKER_V11.py | _wmr_click_download | GUID correlation via CDP |
| WMR Driver | FULL_QUEUE_WORKER_V11.py | WmrDriverThread | Dedicated thread prevents asyncio block |
| BullMQ | FULL_QUEUE_WORKER_V14_N2N_FINAL.py | process_bullmq_job | Idempotent context manager |
