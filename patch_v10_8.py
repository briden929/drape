import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        var imgs = document.querySelectorAll('img');
        for (var i = 0; i < imgs.length; i++) {
            var alt = (imgs[i].getAttribute('alt') || '').toLowerCase();
            var src = imgs[i].getAttribute('src') || '';
            if (alt.indexOf('after') !== -1 && (src.indexOf('blob:') === 0 || src.indexOf('data:') === 0)) {
                return 'DONE';
            }
        }'''

replacement = '''        // Wait strictly for Download PNG button as per architecture
        // Do not use after-image detection as a shortcut for readiness'''

if target in text:
    text = text.replace(target, replacement)
    with open('v10_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched WMR status logic')
else:
    print('Target not found')
