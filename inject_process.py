with open('gemini_process_job.py', 'r', encoding='utf-8') as f:
    process_body = f.read()

# Make sure process_body uses self._ensure_driver properly
process_body = process_body.replace('if not self.driver:', '# _ensure_driver handles this\n        drv = self._ensure_driver()')
process_body = process_body.replace('self.driver.execute_script("window.open', 'drv.execute_script("window.open')
process_body = process_body.replace('self.driver.switch_to.window', 'drv.switch_to.window')
process_body = process_body.replace('self.current_window_handle = self.driver.current_window_handle', 'self.current_window_handle = drv.current_window_handle')
process_body = process_body.replace('self.driver.get(', 'drv.get(')

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V12_FINAL.py', 'r', encoding='utf-8') as f:
    v12 = f.read()
    
import re
# Replace the stub _process_job
v12 = re.sub(r'    def _process_job\(self, item\):.*?(?=    def quit\(self\):)', process_body + '\n', v12, flags=re.DOTALL)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V12_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(v12)
