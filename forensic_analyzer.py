import os
import re

directory = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"

reports = {
    "WMR_FORENSICS.md": {
        "keywords": ["wmr", "watermark", "WMR", "Download PNG", "W0", "W1"],
        "title": "# WMR Forensics Report\n\n",
        "content": ""
    },
    "GEMINI_FORENSICS.md": {
        "keywords": ["gemini", "Gemini", "T0", "T1", "T2", "T3", "generate image", "flash"],
        "title": "# Gemini Forensics Report\n\n",
        "content": ""
    },
    "BULLMQ_REDIS_FORENSICS.md": {
        "keywords": ["bullmq", "BullMQ", "redis", "Redis", "queue", "Queue"],
        "title": "# BullMQ & Redis Forensics Report\n\n",
        "content": ""
    },
    "R2_DB_CREDITS_FORENSICS.md": {
        "keywords": ["r2", "R2", "boto3", "postgres", "supabase", "Supabase", "credit", "Credit"],
        "title": "# R2, DB & Credits Forensics Report\n\n",
        "content": ""
    },
    "SECURITY_FORENSICS.md": {
        "keywords": ["auth", "login", "cookie", "token", "password", "security", "credentials"],
        "title": "# Security Forensics Report\n\n",
        "content": ""
    }
}

file_matches = {key: [] for key in reports.keys()}

for root, dirs, files in os.walk(directory):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for report_file, report_data in reports.items():
                        for keyword in report_data["keywords"]:
                            if keyword in content:
                                # Find context
                                lines = content.split('\n')
                                for i, line in enumerate(lines):
                                    if keyword in line:
                                        file_matches[report_file].append((file, i+1, line.strip()))
                                        break # Just one match per keyword per file is enough for summary
            except Exception as e:
                pass

for report_file, matches in file_matches.items():
    report_path = os.path.join(directory, report_file)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(reports[report_file]["title"])
        f.write("## Findings\n\n")
        
        # limit to 100 matches to avoid huge files
        unique_files = set([m[0] for m in matches])
        f.write(f"Found evidence in {len(unique_files)} files.\n\n")
        
        for file, line_num, line_content in matches[:100]:
            f.write(f"- **{file}:{line_num}** -> `{line_content[:200]}`\n")
        
        if len(matches) > 100:
            f.write(f"\n... and {len(matches) - 100} more matches omitted for brevity.\n")
