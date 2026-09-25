import os
import re

FINAL = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis\FULL_QUEUE_WORKER_FINAL.py"

with open(FINAL, "r", encoding="utf-8") as f:
    text = f.read()

replacement = """        # 3. WebP Conversion
        ctx.webp_path = f"/content/downloads/final_output/{job_id}.webp"
        os.makedirs(os.path.dirname(ctx.webp_path), exist_ok=True)
        # Use PIL to convert to webp as fallback if cwebp is missing, or just use PIL directly
        import subprocess
        subprocess.run(['cwebp', '-q', '80', ctx.clean_png_path, '-o', ctx.webp_path], capture_output=True)
        if not os.path.exists(ctx.webp_path):
            from PIL import Image
            with Image.open(ctx.clean_png_path) as img:
                img.save(ctx.webp_path, "WEBP", quality=80)
        
        validate_image_file(ctx.webp_path)
        await ctx.transition(JobState.WEBP_READY)
        
        # 4. R2 & DB via V9 backend modules
        import sys
        target_user_id = ctx.payload.get("userId", "system")
        if "fashion_studio" in sys.modules:
            fs = sys.modules["fashion_studio"]
            res = fs.upload_and_record(
                image_path=ctx.clean_png_path,
                webp_path=ctx.webp_path,
                user_id=target_user_id,
                gen_id=job_id
            )
        else:
            print("[WARN] fashion_studio module not found. Skipping R2/DB.")
            
        if "credits" in sys.modules:
            try:
                sys.modules["credits"].deduct_credits(target_user_id, 1, "generation", f"job_{job_id}")
            except Exception as e:
                print(f"[WARN] Credit deduction failed: {e}")
                
        await ctx.transition(JobState.COMPLETED)
        return {"status": "completed"}"""

text = re.sub(r'# 3\. WebP Conversion.*?return \{"status": "completed"\}', replacement, text, flags=re.DOTALL)

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
