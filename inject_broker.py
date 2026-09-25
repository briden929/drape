import os
import re

ROOT = r"C:\Users\PC\.gemini\antigravity\scratch\Reddis"
FINAL = os.path.join(ROOT, "FULL_QUEUE_WORKER_FINAL.py")

with open(FINAL, 'r', encoding='utf-8') as f:
    text = f.read()

broker_injection = """
    def fail(self, resource_id: str):
        with self.lock:
            if resource_id in self.pool:
                self.pool[resource_id]['state'] = 'DEAD'
                print(f"[BROKER] Marked {resource_id} DEAD")

    def recover(self, resource_id: str):
        with self.lock:
            if resource_id in self.pool:
                self.pool[resource_id]['state'] = 'FREE'
                self.seq += 1
                self.pool[resource_id]['seq'] = self.seq
                print(f"[BROKER] Recovered {resource_id}")

    def is_free(self, resource_id: str) -> bool:
        with self.lock:
            return self.pool.get(resource_id, {}).get('state') == 'FREE'

    def snapshot(self):
        with self.lock:
            return {
                "total": len(self.pool),
                "free": sum(1 for v in self.pool.values() if v['state'] == 'FREE'),
                "dead": sum(1 for v in self.pool.values() if v['state'] == 'DEAD')
            }
"""

if "def snapshot" not in text:
    text = re.sub(r'(class FirstFreeBroker:.*?)(?=class )', r'\1' + broker_injection + "\n\n", text, flags=re.DOTALL)

with open(FINAL, "w", encoding="utf-8") as f:
    f.write(text)
