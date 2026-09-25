import json
with open(r'C:\Users\PC\.gemini\antigravity\brain\81552632-81a7-4eef-a137-f9f74093c534\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for line in reversed(lines):
    data = json.loads(line)
    if data.get('source') == 'USER_EXPLICIT':
        with open(r'C:\Users\PC\.gemini\antigravity\scratch\user_prompt_v14_rebuild.txt', 'w', encoding='utf-8') as out:
            out.write(data['content'])
        break
