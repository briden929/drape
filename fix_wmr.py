with open('v15_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
# We need to find `_wmr_check_status` and replace the Save logic
wmr_check = '''def _wmr_check_status(drv: webdriver.Chrome):
    try:
        # Strict targeting: must be inside the results container
        js = """
        var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
        if (!res) return null;
        var btns = res.querySelectorAll('button, a');
        for (var i=0; i<btns.length; i++) {
            var t = (btns[i].textContent || '').toLowerCase().trim();
            if (t === 'download png') {
                return 'READY';
            }
        }
        return 'PROCESSING';
        """
        return safe_execute_script(drv, js)
    except:
        return None
'''

text = re.sub(r'def _wmr_check_status\(.*?return None\n', wmr_check, text, flags=re.DOTALL)

with open('v15_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patched WMR check status")
