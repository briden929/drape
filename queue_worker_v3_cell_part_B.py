

# ============================================================================
# STEP 9: CHROME MULTI-TAB POOL & AGGRESSIVE PIPELINE DISPATCHER
# ============================================================================
print("=" * 80)
print(f"📑 STEP 9: CONFIGURING CHROME MULTI-TAB POOL ({MAX_CONCURRENT_TABS} TABS)")
print("=" * 80)

class ChromeTabSlot:
    def __init__(self, tab_id, handle):
        self.tab_id = tab_id
        self.handle = handle
        self.download_dir = CHROME_DL_BASE / f'tab_{tab_id}'
        self.edge_dl_dir = EDGE_DL_BASE / f'tab_{tab_id}'
        self.is_busy = False
        self.current_job_id = None
        self.urls_before = set()
        self.chat_urls = set()

class ChromeMultiTabManager:
    def __init__(self, driver, max_tabs):
        self.driver = driver
        self.max_tabs = max_tabs
        self.lock = None  # Instantiated in main() under running loop
        self.slots = []

    def init_tabs(self):
        initial_handle = self.driver.current_window_handle
        slot1 = ChromeTabSlot(1, initial_handle)
        self.slots.append(slot1)
        self._set_tab_download_behavior(initial_handle, slot1.download_dir)
        print(f"  ✅ Tab 1 ready with dedicated download folder: {slot1.download_dir}")
        
        for i in range(2, self.max_tabs + 1):
            before = set(self.driver.window_handles)
            self.driver.execute_cdp_cmd('Target.createTarget', {'url': GEMINI_APP_URL})
            time.sleep(0.5)
            deadline = time.time() + 5.0
            new_handle = None
            while time.time() < deadline:
                diff = set(self.driver.window_handles) - before
                if diff:
                    new_handle = list(diff)[0]
                    break
                time.sleep(0.2)
            if not new_handle:
                new_handle = self.driver.window_handles[-1]
            
            slot = ChromeTabSlot(i, new_handle)
            self._set_tab_download_behavior(new_handle, slot.download_dir)
            self.slots.append(slot)
            print(f"  ✅ Tab {i} ready with dedicated download folder: {slot.download_dir}")

    def _set_tab_download_behavior(self, handle, dl_path):
        self.driver.switch_to.window(handle)
        try:
            self.driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': str(dl_path.resolve())
            })
        except Exception:
            pass

    async def acquire_idle_slot(self):
        while True:
            for s in self.slots:
                if not s.is_busy:
                    s.is_busy = True
                    return s
            await asyncio.sleep(0.2)

    def release_slot(self, slot):
        slot.is_busy = False
        slot.current_job_id = None
        slot.urls_before.clear()
        slot.chat_urls.clear()

tab_manager = ChromeMultiTabManager(chrome_driver, MAX_CONCURRENT_TABS)
tab_manager.init_tabs()
print(f"  ✅ All {MAX_CONCURRENT_TABS} Chrome tabs ready for aggressive pipelining.\n")


# ============================================================================
# STEP 10: PROVEN GEMINI DOM ROUTINES (HOVER-DOWNLOAD & DIRECT-FETCH)
# ============================================================================

def start_new_chat(drv):
    for sel in ['a[aria-label="New chat"]', 'button[aria-label="New chat"]', 'div[aria-label="New chat"]', '[data-test-id="new-chat-button"]']:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(1.0)
                    return True
        except Exception:
            continue
    return False

def click_plus_button(drv):
    for sel in ['button[aria-label="Upload and tools"]', 'button[aria-haspopup="menu"][aria-label*="Upload"]', 'button[jslog*="300142"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue
    try:
        result = drv.execute_script('''
            var btns=document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                var b=btns[i];
                if(b.offsetParent!==null){
                    var lbl=(b.getAttribute('aria-label')||'').toLowerCase();
                    if(lbl.indexOf('upload')!==-1||lbl.indexOf('tools')!==-1){
                        b.click();return 'OK';
                    }
                    var icon=b.querySelector('mat-icon[fonticon="plus"],mat-icon[data-mat-icon-name="plus"]');
                    if(icon){b.click();return 'OK';}
                }
            } return 'NO';
        ''')
        if result == 'OK':
            time.sleep(0.4)
            return True
    except Exception:
        pass
    return False

def click_create_image(drv):
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button"):
            if btn.is_displayed() and 'Create image' in btn.text:
                drv.execute_script("arguments[0].click();", btn)
                time.sleep(0.35)
                return True
    except Exception:
        pass
    try:
        for icon in drv.find_elements(By.CSS_SELECTOR, "mat-icon[data-mat-icon-name='image_create'],mat-icon[fonticon='image_create']"):
            if not icon.is_displayed():
                continue
            btn = drv.execute_script("var e=arguments[0]; while(e&&e.tagName!=='BUTTON') e=e.parentElement; return e;", icon)
            if btn and btn.is_displayed():
                drv.execute_script("arguments[0].click();", btn)
                time.sleep(0.35)
                return True
    except Exception:
        pass
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[jslog*='271906']"):
            if btn.is_displayed():
                drv.execute_script("arguments[0].click();", btn)
                time.sleep(0.35)
                return True
    except Exception:
        pass
    for cand in drv.find_elements(By.CSS_SELECTOR, "button, [role='menuitem'], [role='menuitemcheckbox']"):
        try:
            if not cand.is_displayed(): continue
            lbl = (cand.text or cand.get_attribute('aria-label') or '').strip().lower()
            if 'create image' in lbl or 'create images' in lbl:
                drv.execute_script("arguments[0].click();", cand)
                time.sleep(0.4)
                return True
        except Exception:
            continue
    return False

def in_image_mode(drv):
    try:
        if drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder='Describe your image']"):
            return True
        for c in drv.find_elements(By.CSS_SELECTOR, "button[aria-label='Deselect Images'], span.gds-body-s"):
            if c.is_displayed() and 'Images' in c.text:
                return True
    except Exception:
        pass
    return False

def activate_create_image_mode(drv, attempts=3):
    if in_image_mode(drv):
        return True
    for _ in range(attempts):
        if not click_plus_button(drv):
            time.sleep(0.5)
            continue
        if not click_create_image(drv):
            try: drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            except Exception: pass
            time.sleep(0.5)
            continue
        deadline = time.time() + 4.0
        while time.time() < deadline:
            if in_image_mode(drv):
                return True
            time.sleep(0.15)
        try: drv.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except Exception: pass
        time.sleep(0.5)
    return False

def click_upload_files_in_drawer(drv):
    for sel in ["button[data-test-id='local-images-files-uploader-button']"]:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    for xp in ["//span[contains(text(),'Upload files')]/ancestor::button", "//div[contains(text(),'Upload files')]/ancestor::button"]:
        try:
            for btn in drv.find_elements(By.XPATH, xp):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    try:
        result = drv.execute_script('''
            var btns=document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].offsetParent!==null && btns[i].textContent.toLowerCase().indexOf('upload files')!==-1){
                    btns[i].click();return 'OK';
                }
            } return 'NO';
        ''')
        if result == 'OK':
            time.sleep(0.3)
            return True
    except Exception:
        pass
    return False

def find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs:
        return inputs[0]
    try:
        drv.execute_script('''
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                el.removeAttribute('hidden');
                el.removeAttribute('disabled');
            });
        ''')
    except Exception:
        pass
    time.sleep(0.1)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def wait_for_attachment_chip(drv, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, 'button[aria-label="close attachment"]'):
                if el.is_displayed(): return True
            for chip in drv.find_elements(By.CSS_SELECTOR, 'gem-media-attachment, uploader-file-preview'):
                if chip.is_displayed(): return True
            for w in drv.find_elements(By.CSS_SELECTOR, '.attachment-preview-wrapper, uploader-file-preview-container'):
                if w.is_displayed(): return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

def upload_images(drv, image_paths, timeout=30):
    paths = [str(Path(p).resolve()) for p in image_paths if p and os.path.exists(p)]
    if not paths:
        return True
    
    # Try attaching together
    try:
        if click_plus_button(drv):
            click_upload_files_in_drawer(drv)
            finp = find_file_input(drv)
            if finp:
                finp.send_keys('\n'.join(paths))
                if wait_for_attachment_chip(drv, timeout=timeout):
                    time.sleep(1.2 * len(paths))
                    return True
    except Exception:
        pass
    
    # Single attach fallback
    for p in paths:
        if click_plus_button(drv):
            click_upload_files_in_drawer(drv)
            finp = find_file_input(drv)
            if finp:
                finp.send_keys(p)
                wait_for_attachment_chip(drv, timeout=timeout)
                time.sleep(1.0)
    return True

def type_prompt(drv, text):
    editor = None
    deadline = time.time() + 10
    while time.time() < deadline:
        for sel in ["div.ql-editor[data-placeholder='Describe your image']", "div.ql-editor[contenteditable='true']", "div[contenteditable='true']"]:
            try:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        editor = el
                        break
            except Exception:
                pass
            if editor: break
        if editor: break
        time.sleep(0.3)
    if not editor:
        raise RuntimeError('Could not find the Gemini prompt box')
    
    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", editor)
    time.sleep(0.1)
    drv.execute_script("arguments[0].focus();", editor)
    drv.execute_script("document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);")
    time.sleep(0.05)
    
    try:
        drv.execute_script("document.execCommand('insertText',false,arguments[0]);", text)
        time.sleep(0.3)
        content = drv.execute_script("return (arguments[0].textContent||'').trim();", editor) or ''
        if len(re.sub(r'\s+', '', content)) >= int(len(re.sub(r'\s+', '', text)) * 0.5):
            return True
    except Exception:
        pass
    
    drv.execute_script("arguments[0].focus();", editor)
    chunk = 500
    lines = text.split('\n')
    for li, line in enumerate(lines):
        for i in range(0, len(line), chunk):
            editor.send_keys(line[i:i + chunk])
            time.sleep(0.03)
        if li != len(lines) - 1:
            ActionChains(drv).key_down(Keys.SHIFT).send_keys(Keys.RETURN).key_up(Keys.SHIFT).perform()
            time.sleep(0.03)
    time.sleep(0.3)
    return True

def click_send(drv):
    try:
        result = drv.execute_script('''
            var icons=document.querySelectorAll('mat-icon[fonticon="arrow_upward"],mat-icon[data-mat-icon-name="arrow_upward"]');
            for(var i=0;i<icons.length;i++){
                var b=icons[i].closest('button');
                if(b&&!b.disabled&&b.offsetParent!==null){b.click();return 'OK_UP';}
            }
            var sendIcons=document.querySelectorAll('mat-icon[fonticon="send"],mat-icon[data-mat-icon-name="send"]');
            for(var i=0;i<sendIcons.length;i++){
                var b=sendIcons[i].closest('button');
                if(b&&!b.disabled&&b.offsetParent!==null){b.click();return 'OK_SEND';}
            }
            var btns=document.querySelectorAll('button[aria-label="Send message"],button[data-test-id="send-button"]');
            for(var i=0;i<btns.length;i++){
                if(!btns[i].disabled&&btns[i].offsetParent!==null){btns[i].click();return 'OK_ARIA';}
            }
            return 'NO';
        ''')
        if result and result.startswith('OK'):
            return True
    except Exception:
        pass
    for sel in ["button[aria-label='Send message']", "button[data-test-id='send-button']", "button[aria-label*='Send']"]:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].click();", btn)
                    return True
        except Exception:
            continue
    return False

def snapshot_urls(drv):
    try:
        return set(drv.execute_script('return Array.from(document.querySelectorAll(\'img[src^="blob:"],img[src*="googleusercontent"]\')).map(i=>i.src).filter(s=>s&&s.length>10);') or [])
    except Exception:
        return set()

def _response_done(drv):
    try:
        for sel in ["button[aria-label='Good response']", "button[aria-label='Bad response']", ".message-actions button"]:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return True
    except Exception:
        pass
    return False

def _send_btn_enabled(drv):
    try:
        return drv.execute_script("""
            var sels=['mat-icon[fonticon="send"]',
                      'mat-icon[data-mat-icon-name="send"]',
                      'mat-icon[fonticon="arrow_upward"]',
                      'mat-icon[data-mat-icon-name="arrow_upward"]',
                      'button[aria-label="Send message"]'];
            for(var s=0;s<sels.length;s++){
                var els=document.querySelectorAll(sels[s]);
                for(var i=0;i<els.length;i++){
                    var b=els[i].tagName==='BUTTON'?els[i]:els[i].closest('button');
                    if(b&&!b.disabled&&b.offsetParent!==null)return true;
                }
            } return false;""")
    except Exception:
        return False

def check_text_error(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for p in ["can't create images of minors", "i'm not able to create that image", "i can't create this image", "sorry, i can't create"]:
            if p in body:
                return "refusal"
        for p in ["you've reached your image-generation limit", "reached your image-generation limit", "can't generate more images for you today", "reached your daily limit", "rate limit"]:
            if p in body:
                return "limit"
    except Exception:
        pass
    return None

def check_gemini_error(drv):
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        for sig in ["i encountered an error", "something went wrong. try again", "an error occurred. please try again"]:
            if sig in body:
                return sig
    except Exception:
        pass
    return None

def poll_gen_response(drv, urls_before, chat_urls):
    rc = check_text_error(drv)
    if rc:
        return ('REFUSED' if rc == "refusal" else 'LIMIT'), None
    if check_gemini_error(drv):
        if _send_btn_enabled(drv) or _response_done(drv):
            return 'ERROR', None

    try:
        blob_srcs = drv.execute_script("""
            var srcs=[];
            var imgs=document.querySelectorAll(
                'img[src^="blob:https://gemini.google.com"]');
            for(var i=imgs.length-1;i>=0;i--){
                var img=imgs[i]; if(!img.offsetParent) continue;
                var src=img.getAttribute('src')||'';
                var tid=img.getAttribute('data-test-id')||'';
                if(tid.includes('uploaded-img')||tid==='image-preview') continue;
                if(src.length>10) srcs.push(src);
            } return srcs;
        """) or []
        for src in blob_srcs:
            if src not in urls_before and src not in chat_urls:
                return 'SUCCESS', src
    except Exception:
        pass

    for sel in [
        "generated-image img", "single-image img",
        "img[src*='googleusercontent']",
        "model-response img", ".response-container-content img",
    ]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if not img.is_displayed():
                        continue
                    src = img.get_attribute("src") or ""
                    tid = img.get_attribute("data-test-id") or ""
                    if (len(src) < 10 or "uploaded-img" in tid or tid == "image-preview"):
                        continue
                    if src in urls_before or src in chat_urls:
                        continue
                    if (src.startswith("blob:https://gemini.google.com") or "googleusercontent" in src):
                        return 'SUCCESS', src
                except Exception:
                    continue
        except Exception:
            pass

    return 'WAITING', None


# ============================================================================
# HOVER-AND-DOWNLOAD & DIRECT-FETCH IMPLEMENTATION
# ============================================================================

def _direct_fetch(drv, save_path, target_url=None):
    # 1. Direct Python urllib fetch for public/CDN image URLs (e.g. googleusercontent)
    if target_url and target_url.startswith(('http://', 'https://')):
        try:
            req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                if len(data) > 5000:
                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(save_path).write_bytes(data)
                    return True
        except Exception:
            pass

    # 2. Extract blob via standard execute_async_script FileReader
    try:
        blob_url = target_url if (target_url and target_url.startswith('blob:')) else None
        if not blob_url:
            blob_url = drv.execute_script("""
                var imgs = document.querySelectorAll('single-image img, generated-image img, img[src^="blob:https://gemini.google.com"]');
                for (var i = imgs.length - 1; i >= 0; i--) {
                    var s = imgs[i].getAttribute('src') || '';
                    if (s.startsWith('blob:https://gemini.google.com')) return s;
                }
                return null;
            """)
        if blob_url and blob_url.startswith('blob:'):
            b64_str = drv.execute_async_script("""
                var url = arguments[0];
                var callback = arguments[arguments.length - 1];
                fetch(url)
                    .then(function(r) { return r.blob(); })
                    .then(function(b) {
                        var fr = new FileReader();
                        fr.onloadend = function() {
                            var res = fr.result || '';
                            callback(res.indexOf(',') !== -1 ? res.split(',')[1] : res);
                        };
                        fr.onerror = function() { callback(null); };
                        fr.readAsDataURL(b);
                    })
                    .catch(function(err) { callback(null); });
            """, blob_url)
            if b64_str and len(b64_str) > 1000:
                data = base64.b64decode(b64_str)
                if len(data) > 5000:
                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(save_path).write_bytes(data)
                    return True
    except Exception:
        pass

    # 3. CDP Runtime.evaluate fallback for blob
    try:
        blob_to_eval = target_url if (target_url and target_url.startswith('blob:')) else None
        if not blob_to_eval:
            blob_to_eval = drv.execute_script("""
                var imgs = document.querySelectorAll('single-image img, generated-image img, img[src^="blob:https://gemini.google.com"]');
                for (var i = imgs.length - 1; i >= 0; i--) {
                    var s = imgs[i].getAttribute('src');
                    if (s && s.startsWith('blob:https://gemini.google.com')) return s;
                } return null;
            """)
        if blob_to_eval and blob_to_eval.startswith('blob:'):
            result = drv.execute_cdp_cmd("Runtime.evaluate", {
                "expression":
                    f"fetch('{blob_to_eval}').then(r=>r.blob())"
                    ".then(b=>new Promise(resolve=>{"
                    "const fr=new FileReader();"
                    "fr.onloadend=()=>resolve(fr.result.split(',')[1]);"
                    "fr.readAsDataURL(b);}));",
                "awaitPromise": True, "returnByValue": True,
            })
            if result and "result" in result and "value" in result["result"]:
                val = result["result"]["value"]
                if val and len(val) > 1000:
                    data = base64.b64decode(val)
                    if len(data) > 5000:
                        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                        Path(save_path).write_bytes(data)
                        return True
    except Exception:
        pass

    # 4. Canvas extraction fallback
    try:
        canvas_b64 = drv.execute_script("""
            var imgs = document.querySelectorAll('single-image img, generated-image img, img[src^="blob:"], img[src*="googleusercontent"]');
            for (var i = imgs.length - 1; i >= 0; i--) {
                var img = imgs[i];
                if (!img.offsetParent) continue;
                if ((img.naturalWidth || img.width) < 100) continue;
                var tid = img.getAttribute('data-test-id') || '';
                if (tid.includes('uploaded-img') || tid === 'image-preview') continue;
                try {
                    var canvas = document.createElement('canvas');
                    canvas.width = img.naturalWidth || img.width;
                    canvas.height = img.naturalHeight || img.height;
                    var ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0);
                    return canvas.toDataURL('image/png').split(',')[1];
                } catch(e) {
                    return null;
                }
            }
            return null;
        """)
        if canvas_b64 and len(canvas_b64) > 1000:
            data = base64.b64decode(canvas_b64)
            if len(data) > 5000:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                Path(save_path).write_bytes(data)
                return True
    except Exception:
        pass

    return False

def _click_dl_btn(drv):
    selectors = [
        ("css",  "button[data-test-id='download-generated-image-button']"),
        ("css",  "button[aria-label='Download']"),
        ("css",  "button[aria-label='Download image']"),
        ("css",  "button[aria-label*='Download']"),
        ("xpath","//button[contains(@aria-label,'Download')]"),
        ("xpath","//mat-icon[contains(@fonticon,'download')]/ancestor::button"),
    ]
    for by_type, sel in selectors:
        try:
            by = By.XPATH if by_type == "xpath" else By.CSS_SELECTOR
            for btn in reversed(drv.find_elements(by, sel)):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(0.1)
                    drv.execute_script("arguments[0].click();", btn)
                    return True
        except Exception:
            continue
    return False

def _hover_and_download(drv, urls_before, target_url=None, chat_urls=None):
    def _try_hover(img):
        try:
            drv.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'});", img)
            time.sleep(0.2)
            try:
                ActionChains(drv).move_to_element(img).perform()
                time.sleep(0.3)
                if _click_dl_btn(drv):
                    return True
            except Exception:
                pass
            try:
                drv.execute_script("""
                    var el = arguments[0];
                    var targets = [el, el.parentElement, el.closest('single-image'), el.closest('generated-image'), el.closest('.response-container-content')].filter(Boolean);
                    targets.forEach(function(target) {
                        ['mouseenter','mouseover','mousemove'].forEach(function(evt) {
                            target.dispatchEvent(new MouseEvent(evt, {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: target.getBoundingClientRect().left + target.offsetWidth / 2,
                                clientY: target.getBoundingClientRect().top + target.offsetHeight / 2
                            }));
                        });
                    });
                """, img)
                time.sleep(0.3)
                if _click_dl_btn(drv):
                    return True
            except Exception:
                pass
            try:
                drv.execute_script("""
                    document.querySelectorAll('button[data-test-id="download-generated-image-button"], button[aria-label*="Download"]').forEach(function(btn) {
                        btn.style.cssText = 'display: inline-block !important; visibility: visible !important; opacity: 1 !important; pointer-events: auto !important; z-index: 99999 !important;';
                    });
                """)
                time.sleep(0.2)
                if _click_dl_btn(drv):
                    return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    try:
        drv.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        time.sleep(0.2)
    except Exception:
        pass

    # 1. Target matching element if target_url was provided
    if target_url:
        for sel in ["single-image img", "generated-image img", "img[src*='googleusercontent']", "img[src^='blob:']"]:
            try:
                for img in reversed(drv.find_elements(By.CSS_SELECTOR, sel)):
                    src = img.get_attribute("src") or ""
                    if src == target_url and img.is_displayed():
                        if _try_hover(img):
                            return True
            except Exception:
                continue

    # 2. General scan of images not in urls_before
    for sel in [
        "single-image img", "generated-image img",
        "img[src^='blob:https://gemini.google.com']",
        "img[src*='googleusercontent']",
    ]:
        try:
            for img in reversed(drv.find_elements(By.CSS_SELECTOR, sel)):
                src = img.get_attribute("src") or ""
                tid = img.get_attribute("data-test-id") or ""
                if "uploaded-img" in tid or tid == "image-preview":
                    continue
                if src in urls_before or len(src) < 10:
                    continue
                if img.is_displayed():
                    if _try_hover(img):
                        return True
        except Exception:
            continue

    # 3. Direct JavaScript button click across containers
    try:
        clicked = drv.execute_script("""
            window.scrollTo(0,document.body.scrollHeight);
            var containers=document.querySelectorAll(
                'single-image,generated-image,.response-container-content');
            for(var i=containers.length-1;i>=0;i--){
                containers[i].dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));
            }
            var btns=document.querySelectorAll(
                'button[data-test-id="download-generated-image-button"],'
                +'button[aria-label*="Download"]');
            for(var i=btns.length-1;i>=0;i--){
                var b=btns[i];
                if(b.offsetParent!==null&&!b.disabled){
                    b.scrollIntoView({block:'center'});b.click();return 'OK';
                }
            } return null;
        """)
        if clicked:
            return True
    except Exception:
        pass
    return False

def _scan_downloaded_file(candidate_dirs, files_before_map, min_size=3000):
    for d in candidate_dirs:
        if not os.path.exists(d):
            continue
        try:
            cur = set(os.listdir(d))
            before = files_before_map.get(str(d), set())
            new_files = {
                f for f in (cur - before)
                if not f.endswith(('.crdownload', '.tmp', '.part', '.download'))
                and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
            }
            if new_files:
                fn = sorted(
                    new_files,
                    key=lambda f: os.path.getmtime(os.path.join(d, f)),
                    reverse=True
                )[0]
                fp = os.path.join(d, fn)
                if os.path.getsize(fp) >= min_size:
                    return fp
        except Exception:
            pass
    return None

def download_image(drv, save_path, urls_before, chat_urls, dl_dir, target_url=None, retries=3):
    if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
        return True

    # 1. Try Direct fetch via CDP / JS / urllib
    if _direct_fetch(drv, save_path, target_url=target_url):
        return True

    time.sleep(0.2)
    os.makedirs(dl_dir, exist_ok=True)
    candidate_dirs = [
        Path(dl_dir),
        CHROME_DL_BASE,
        Path('/content/downloads'),
        Path('/root/Downloads')
    ]
    for cd in candidate_dirs:
        cd.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            files_before_map = {str(d): set(os.listdir(d)) for d in candidate_dirs if os.path.exists(d)}
            drv.execute_script("window.scrollTo(0,document.body.scrollHeight);")
            time.sleep(0.2)
            hover_ok = _hover_and_download(drv, urls_before, target_url=target_url, chat_urls=chat_urls)
            
            timeout = 14 if hover_ok else 6
            t0 = time.time()
            fp = None
            while time.time() - t0 < timeout:
                fp = _scan_downloaded_file(candidate_dirs, files_before_map)
                if fp:
                    break
                time.sleep(0.3)

            if fp and os.path.exists(fp):
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(fp, save_path)
                except Exception:
                    shutil.copy2(fp, save_path)
                    try: os.remove(fp)
                    except Exception: pass
                if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
                    return True
        except Exception:
            pass
        time.sleep(0.3)

    if _direct_fetch(drv, save_path, target_url=target_url):
        return True
    return False


# ============================================================================
# STEP 11: DATABASE FETCH & DEAD LETTER QUEUE HELPERS
# ============================================================================

def fetch_generation(gen_id):
    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT g.id, g.user_id, g.model_id, g.catalogue_item_id, g.package_id,
                   g.prompt, g.params, g.attempts, g.max_attempts, g.credits_cost,
                   ci.hologram_url, ci.thumbnail_url, ci.model_id AS ci_model_id,
                   pk.primary_outfit_name,
                   m.image_url AS model_image_url, m.angle_image_url AS model_angle_url
            FROM image_generations g
            LEFT JOIN catalogue_items ci ON ci.id = g.catalogue_item_id
            LEFT JOIN packages pk ON pk.id = COALESCE(g.package_id, ci.package_id)
            LEFT JOIN models m ON m.id = COALESCE(g.model_id, ci.model_id)
            WHERE g.id = %s
            ''', (gen_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()

def resolve_prompt_and_refs(gen):
    params = gen.get('params') or {}
    if isinstance(params, str):
        try: params = json.loads(params)
        except Exception: params = {}

    garment_url = (params.get('garmentImage') or params.get('garmentUrl') or
                   params.get('garment_image_url') or params.get('garmentImageUrl'))
    if not garment_url and isinstance(params.get('garmentImages'), list) and params['garmentImages']:
        garment_url = params['garmentImages'][0]
    
    if not garment_url:
        raise ValueError(f"Generation {gen['id']}: No garment reference found in params.")

    model_img_url = params.get('modelImage') or gen.get('model_angle_url') or gen.get('model_image_url')
    holo_url = params.get('styleImage') or gen.get('hologram_url')

    garment_path = sys.modules['fashion_studio'].download_remote_image(garment_url, REFS_CACHE_DIR)
    model_path = sys.modules['fashion_studio'].download_remote_image(model_img_url, REFS_CACHE_DIR) if model_img_url else None
    holo_path = sys.modules['fashion_studio'].download_remote_image(holo_url, REFS_CACHE_DIR) if holo_url else None

    prompt = gen.get('prompt') or sys.modules['fashion_studio'].fashion_tryon_prompt(has_model=bool(model_path))
    return (prompt, garment_path, model_path, holo_path)

def record_dead_letter(gen, failed_reason, attempts_made, max_attempts, error_stack=None):
    conn = sys.modules['db'].borrow()
    try:
        cur = conn.cursor()
        summary = json.dumps({'generationId': gen['id']})
        cur.execute("""
            INSERT INTO dead_letter_jobs
                (queue_name, job_name, generation_id, payload_summary, failed_reason,
                 attempts_made, status, worker_id, error_stack)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, 'open', %s, %s)
            """, (QUEUE_NAME, 'process-generation', gen['id'], summary, failed_reason[:4000], attempts_made, WORKER_ID, (error_stack or '')[:8000]))
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# STEP 12: AGGRESSIVE MULTI-TAB BULLMQ JOB PROCESSOR
# ============================================================================

async def process(job, job_token):
    gen_id = job.data.get('generationId') or job.data.get('id') or (job.id if job else None)
    log(f'[{WORKER_ID}] picked up generation {gen_id} (attempt {job.attemptsMade + 1})')

    gen = fetch_generation(gen_id)
    if gen is None:
        log(f'[{WORKER_ID}] {gen_id}: no image_generations row found in DB, skipping')
        return {'skipped': 'row_not_found'}

    try:
        prompt, garment_path, model_image_path, hologram_path = resolve_prompt_and_refs(gen)
    except Exception as e:
        log(f'[{WORKER_ID}] {gen_id}: failed resolving refs: {e}', file=sys.stderr)
        raise

    # 1. Acquire an idle Chrome tab
    slot = await tab_manager.acquire_idle_slot()
    tab_id = slot.tab_id
    slot.current_job_id = gen_id
    log(f'[{WORKER_ID}] {gen_id}: [STEP_TAB_ASSIGNED] Assigned to Chrome Tab {tab_id}')

    raw_download_path = slot.download_dir / f'{gen_id}.png'

    try:
        # 2. Brief submission turn under chrome lock
        async with tab_manager.lock:
            log(f'[{WORKER_ID}] {gen_id}: [STEP_CHROME_TAB{tab_id}_SUBMIT] Submitting prompt & refs to Tab {tab_id}...')
            chrome_driver.switch_to.window(slot.handle)
            start_new_chat(chrome_driver)
            activate_create_image_mode(chrome_driver)
            
            ref_list = [garment_path]
            if hologram_path: ref_list.append(hologram_path)
            if model_image_path: ref_list.append(model_image_path)
            upload_images(chrome_driver, ref_list)
            
            type_prompt(chrome_driver, prompt)
            slot.urls_before = snapshot_urls(chrome_driver)
            slot.chat_urls = set()
            
            if not click_send(chrome_driver):
                raise RuntimeError(f"Tab {tab_id}: Failed to click send button.")
            log(f'[{WORKER_ID}] {gen_id}: [STEP_CHROME_TAB{tab_id}_SENT] Prompt sent! Lock released — Tab {tab_id} generating in background.')

        # 3. Non-blocking polling loop (yields so other tabs can submit immediately!)
        deadline = time.time() + GENERATION_TIMEOUT_S
        image_downloaded = False
        target_src = None
        while time.time() < deadline:
            await asyncio.sleep(1.0)  # YIELD EVENT LOOP TO ALLOW OTHER TABS TO DISPATCH!
            
            # Check image readiness under brief lock
            async with tab_manager.lock:
                chrome_driver.switch_to.window(slot.handle)
                status, new_src = poll_gen_response(chrome_driver, slot.urls_before, slot.chat_urls)
                if status == 'SUCCESS' or target_src:
                    if status == 'SUCCESS' and not target_src:
                        target_src = new_src
                    log(f'[{WORKER_ID}] {gen_id}: [STEP_CHROME_TAB{tab_id}_READY] Image detected! Downloading to tab_{tab_id}...')
                    dl_ok = download_image(
                        chrome_driver,
                        str(raw_download_path),
                        slot.urls_before,
                        slot.chat_urls,
                        str(slot.download_dir),
                        target_url=target_src,
                        retries=2
                    )
                    if dl_ok and raw_download_path.exists() and raw_download_path.stat().st_size > 1000:
                        if target_src:
                            slot.chat_urls.add(target_src)
                        image_downloaded = True
                        log(f'[{WORKER_ID}] {gen_id}: [STEP_CHROME_TAB{tab_id}_DOWNLOADED] Saved to {raw_download_path} ({raw_download_path.stat().st_size // 1024} KB)')
                        break
                    else:
                        log(f'[{WORKER_ID}] {gen_id}: [STEP_CHROME_TAB{tab_id}_RETRY_DL] Download attempt failed, retrying on next tick...', file=sys.stderr)
                elif status == 'ERROR':
                    raise RuntimeError(f"Tab {tab_id}: Gemini reported an error during generation.")
                elif status == 'REFUSED':
                    raise RuntimeError(f"Tab {tab_id}: Gemini refused to generate image for this prompt.")
                elif status == 'LIMIT':
                    raise RuntimeError(f"Tab {tab_id}: Gemini image generation limit reached.")

        if not image_downloaded:
            raise RuntimeError(f"Tab {tab_id}: Gemini image generation or download timed out after {GENERATION_TIMEOUT_S}s.")

    except Exception as e:
        attempts_made = job.attemptsMade + 1
        max_attempts = job.opts.get('attempts') or 1
        is_final = attempts_made >= max_attempts
        log(f'[{WORKER_ID}] {gen_id}: attempt {attempts_made}/{max_attempts} failed: {e}', file=sys.stderr)
        if is_final:
            try:
                record_dead_letter(gen, str(e), attempts_made, max_attempts, traceback.format_exc())
            except Exception as dlq_err:
                log(f'[{WORKER_ID}] {gen_id}: DLQ insert failed: {dlq_err}', file=sys.stderr)
            try:
                sys.modules['credits'].refund_look(gen_id, str(e)[:500])
            except Exception as ref_err:
                log(f'[{WORKER_ID}] {gen_id}: refund failed: {ref_err}', file=sys.stderr)
        raise

    finally:
        # IMMEDIATELY RELEASE CHROME TAB FOR NEXT QUEUED JOB!
        tab_manager.release_slot(slot)
        log(f'[{WORKER_ID}] {gen_id}: [STEP_CHROME_TAB{tab_id}_FREED] Tab {tab_id} freed! Available for next queued job.')

    # 4. Independent Watermark Removal in Microsoft Edge (Immediate handoff!)
    log(f'[{WORKER_ID}] {gen_id}: [STEP_EDGE_TAB{tab_id}_WMR_START] Handing off to Microsoft Edge for watermark removal (Tab {tab_id} folder)...')
    cleaned_path, webp_path = await edge_wmr_worker.remove_watermark_async(gen_id, tab_id, raw_download_path)

    # 5. Push to Cloudflare R2
    log(f'[{WORKER_ID}] {gen_id}: [STEP_R2_UPLOAD] Pushing final assets to R2 bucket {R2_BUCKET_NAME}...')
    result = sys.modules['fashion_studio'].push_generation(
        image_path=str(cleaned_path),
        prompt=prompt,
        user_id=gen['user_id'],
        gen_id=gen_id,
        webp_path=str(webp_path) if webp_path else None,
        force=True,
        params={'garmentImage': garment_path, 'modelImage': model_image_path, 'styleImage': hologram_path}
    )

    # 6. Settle credits
    try:
        sys.modules['credits'].settle_look(gen_id)
        log(f'[{WORKER_ID}] {gen_id}: [STEP_CREDITS_SETTLE] Credits settled successfully.')
    except Exception as e:
        log(f'[{WORKER_ID}] {gen_id}: settle_look non-fatal warning: {e}', file=sys.stderr)

    log(f'[{WORKER_ID}] {gen_id}: [STEP_JOB_COMPLETE] Complete! Output URL: {result["output_url"]}\n')
    return result


# ============================================================================
# STEP 13: MAIN WORKER DAEMON LOOP
# ============================================================================
from bullmq import Worker

async def main():
    tab_manager.lock = asyncio.Lock()  # Correctly bind lock to active running event loop
    log(f'[{WORKER_ID}] connecting to {REDIS_URL} queue={QUEUE_NAME!r} prefix={REDIS_KEY_PREFIX!r}')
    
    worker = Worker(
        QUEUE_NAME,
        process,
        {
            'connection': REDIS_URL,
            'prefix': REDIS_KEY_PREFIX,
            'concurrency': MAX_CONCURRENT_TABS
        }
    )
    
    log(f'[{WORKER_ID}] waiting for jobs (Ctrl+C to stop)...')
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log(f'\n[{WORKER_ID}] Stopping worker gracefully...')
    finally:
        await worker.close()
        try: chrome_driver.quit()
        except Exception: pass
        if edge_wmr_worker.driver:
            try: edge_wmr_worker.driver.quit()
            except Exception: pass

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
