# V15 JOB PAYLOAD CONTRACT

## Required Payload Fields

```json
{
    "id": "unique_job_id",
    "generation_id": "unique_generation_id",
    "prompt": "Gemini generation prompt",
    "refs": ["reference_image_url_1", "reference_image_url_2"],
    "user_id": "user_identifier",
    "retry_count": 0,
    "attachments": ["file_path_1", "file_path_2"]
}
```

## Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique job identifier |
| generation_id | string | Yes | Unique generation identifier |
| prompt | string | Yes | Gemini generation prompt text |
| refs | array | No | Reference image URLs or paths |
| user_id | string | Yes | User identifier |
| retry_count | integer | No | Number of retries |
| attachments | array | No | File paths for upload |

## State Transitions

The job payload flows through 19 states:
QUEUED -> GEMINI_RESERVED -> GEMINI_GENERATING -> RAW_DOWNLOAD_START -> GEMINI_RELEASED -> RAW_DOWNLOADING -> RAW_READY -> RAW_VALIDATED -> WMR_QUEUEED -> WMR_RESERVED -> WMR_PROCESSING -> WMR_DOWNLOAD_START -> WMR_RELEASED -> CLEAN_READY -> WEBP_READY -> R2_READY -> DB_FINALIZING -> DB_READY -> CREDITS_SETTLED -> COMPLETED

## Resource Allocation

- Gemini: T0-T3 (4 resources, First-Free-Wins)
- WMR: W0-T0 through W3-T1 (8 resources, Global First-Free-Wins)
- BullMQ: 8 concurrent jobs max

## Failure Handling

- Any state can transition to FAILED
- T resource released at DOWNLOAD START
- WMR resource released at DOWNLOAD PNG START
- Credits failure: warning only, job continues
- DB failure: isolated to single job
- Browser failure: only affects assigned resource
