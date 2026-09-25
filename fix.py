import re
with open('v16_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

wmr_click = '''
def _wmr_click_download(drv: webdriver.Chrome, prefix: str) -> bool:
    try:
        js = """
        var res = document.querySelector('.result-container, .output-container, div[class*="result"]');
        if (!res) return false;
        var btns = res.querySelectorAll('button, a');
        for (var i=0; i<btns.length; i++) {
            var t = (btns[i].textContent || '').toLowerCase().trim();
            if (t === 'download png') {
                btns[i].click();
                return true;
            }
        }
        return false;
        """
        return safe_execute_script(drv, js)
    except:
        return False
'''

text = text.replace('class WmrWorker:', wmr_click + '\nclass WmrWorker:')

with open('v16_work.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Injected _wmr_click_download")
