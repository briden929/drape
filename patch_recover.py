import re

with open('v11_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'with open(debug_dir / "page.html", "w", encoding="utf-8") as df: df.write(chrome_driver.page_source)'

replacement = '''with open(debug_dir / "page.html", "w", encoding="utf-8") as df: df.write(chrome_driver.page_source)
            
            # Additional DOM geometry dump requested by user
            import json
            geom = chrome_driver.execute_script("""
                var out = {url: window.location.href, buttons: [], inputs: [], menus: []};
                var els = document.querySelectorAll('button, input, [role="menuitem"], [role="dialog"], .cdk-overlay-pane');
                els.forEach(function(el) {
                    var r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) return;
                    var cx = r.x + r.width/2;
                    var cy = r.y + r.height/2;
                    var topEl = document.elementFromPoint(cx, cy);
                    var topTag = topEl ? topEl.tagName : 'NONE';
                    var topClass = topEl ? topEl.className : '';
                    out.buttons.push({
                        tag: el.tagName,
                        text: (el.innerText || '').slice(0, 30),
                        aria: el.getAttribute('aria-label'),
                        rect: {x: r.x, y: r.y, w: r.width, h: r.height},
                        topElement: topTag + '.' + topClass
                    });
                });
                return out;
            """)
            with open(debug_dir / "geom.json", "w", encoding="utf-8") as df: json.dump(geom, df, indent=2)'''

if target in text:
    text = text.replace(target, replacement)
    with open('v11_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched recovery block!')
else:
    print('Not found')
