import os
import re

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

# Fix Gemini registry
text = re.sub(
    r"download_registry\[ctx.gemini_download_guid\] = \{.*?\}",
    "DOWNLOAD_REGISTRY[ctx.gemini_download_guid] = DownloadRecord(guid=ctx.gemini_download_guid, job_id=job_id, resource_id=self.resource_id, resource_type='GEMINI', staging_dir=str(staging_dir), expected_filename=f'{ctx.gemini_download_guid}.png')",
    text, flags=re.DOTALL
)

# Fix WMR registry
text = re.sub(
    r"download_registry\[ctx.wmr_download_guid\] = \{.*?\}",
    "DOWNLOAD_REGISTRY[ctx.wmr_download_guid] = DownloadRecord(guid=ctx.wmr_download_guid, job_id=job_id, resource_id=resource_id, resource_type='WMR', staging_dir=str(staging_dir), expected_filename=f'{ctx.wmr_download_guid}.png')",
    text, flags=re.DOTALL
)

# Also fix the download monitor loop to use DOWNLOAD_REGISTRY
text = text.replace("global download_registry", "global DOWNLOAD_REGISTRY")
text = text.replace("for guid, rec in list(download_registry.items()):", "for guid, rec in list(DOWNLOAD_REGISTRY.items()):")
text = text.replace("rec['ctx']", "JOB_CONTEXTS[rec.job_id]")
text = text.replace("rec['staging_dir']", "Path(rec.staging_dir)")
text = text.replace("rec['type']", "rec.resource_type")
text = text.replace("download_registry.pop(guid, None)", "DOWNLOAD_REGISTRY.pop(guid, None)")
text = text.replace("job_dir = rec['job_dir']", "job_dir = Path(f'/content/downloads/final_output/{rec.resource_id}/{rec.job_id}')")
text = text.replace("incoming_dir = rec['incoming_dir']", "incoming_dir = Path(f'/content/downloads/incoming/{rec.resource_id}/{rec.job_id}')")
text = text.replace("files_before = rec['files_before']", "files_before = set()")

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
