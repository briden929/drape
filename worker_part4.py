# ============================================================================
# STEP 10: PROVEN GEMINI DOM ROUTINES (ATOMIC PROMPT, STRICT FLASH, CREATE IMAGE)
# ============================================================================
print("=" * 80)
print("🎯 STEP 10: INITIALIZING GEMINI DOM & INTERACTION ENGINE")
print("=" * 80)

class ModelLimitReached(Exception):
    pass

def start_new_chat(drv):
    for sel in ['a[aria-label="New chat"]', 'button[aria-label="New chat"]', 'div[aria-label="New chat"]', '[data-test-id="new-chat-button"]']:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.8)
                    return True
        except Exception:
            continue
    try:
        drv.get(GEMINI_APP_URL)
        time.sleep(1.2)
        return True
    except Exception:
        return False

# ----------------------------------------------------------------------------
# FLASH MODEL ROUTINES
# ----------------------------------------------------------------------------

def _get_current_model_text(drv):
    selectors = [
        "div[data-test-id='logo-pill-label-container'] span.picker-primary-text",
        "div[data-test-id='logo-pill-label-container'] span.gds-body-m",
        "span.picker-primary-text",
    ]
    for sel in selectors:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    txt = (el.text or "").strip()
                    if txt:
                        return txt
        except Exception:
            continue
    try:
        txt = drv.execute_script(
            "var el=document.querySelector("
            "  'div[data-test-id=\"logo-pill-label-container\"] span.picker-primary-text,"
            "   div[data-test-id=\"logo-pill-label-container\"] span.gds-body-m');"
            "return el ? el.textContent.trim() : '';"
        )
        return (txt or "").strip()
    except Exception:
        return ""

def _open_model_picker(drv):
    try:
        btn = drv.find_element(By.CSS_SELECTOR, "button[data-test-id='bard-mode-menu-button']")
        if btn and btn.is_displayed():
            drv.execute_script("arguments[0].click();", btn)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        el = drv.find_element(By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container']")
        if el and el.is_displayed():
            drv.execute_script("arguments[0].click();", el)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        icon = drv.find_element(By.CSS_SELECTOR,
            "div[data-test-id='logo-pill-label-container'] mat-icon[fonticon='keyboard_arrow_down'],"
            "div[data-test-id='logo-pill-label-container'] mat-icon[data-mat-icon-name='keyboard_arrow_down']")
        if icon and icon.is_displayed():
            drv.execute_script("arguments[0].click();", icon)
            time.sleep(0.45)
            return True
    except Exception:
        pass
    try:
        for btn in drv.find_elements(By.CSS_SELECTOR, "button[aria-label]"):
            lbl = (btn.get_attribute("aria-label") or "").lower()
            if ("mode picker" in lbl or "open mode" in lbl or "flash" in lbl or "pro" in lbl):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.45)
                    return True
    except Exception:
        pass
    try:
        res = drv.execute_script(
            "var spans=document.querySelectorAll('span.picker-primary-text,span.gds-body-m');"
            "for(var i=0;i<spans.length;i++){"
            "  var s=spans[i]; if(!s.offsetParent) continue;"
            "  var b=s.closest('button');"
            "  if(b&&!b.disabled){ b.click(); return 'OK'; }"
            "} return 'NO';"
        )
        if res == "OK":
            time.sleep(0.45)
            return True
    except Exception:
        pass
    return False

def _click_flash_in_picker(drv):
    def _is_valid_flash_option(el):
        try:
            txt = (el.text or "").strip().lower()
            return "flash" in txt and "lite" not in txt
        except Exception:
            return False

    for tid in ["bard-mode-option-flash", "mode-option-flash", "flash-option", "model-flash"]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, f"[data-test-id='{tid}']"):
                if el.is_displayed():
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue

    for sel in ["mat-option", "[role='option']", "[role='menuitem']", "[role='menuitemradio']", "button[class*='mode-option']", "button[class*='picker']"]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed() and _is_valid_flash_option(el):
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue

    xpaths = [
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]/ancestor-or-self::button[1]",
        "//mat-option[.//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]]",
        "//button[.//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]]",
        "//*[@role='option' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]",
        "//*[@role='menuitem' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'flash') and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lite'))]",
    ]
    for xp in xpaths:
        try:
            for el in drv.find_elements(By.XPATH, xp):
                if el.is_displayed():
                    drv.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    return True
        except Exception:
            continue

    try:
        res = drv.execute_script("""
            var candidates = document.querySelectorAll('mat-option, [role="option"], [role="menuitem"], [role="menuitemradio"], button');
            for (var i = 0; i < candidates.length; i++) {
                var el = candidates[i];
                if (!el.offsetParent) continue;
                var txt = (el.textContent || '').trim().toLowerCase();
                if (txt.indexOf('flash') === -1) continue;
                if (txt.indexOf('lite') !== -1) continue;
                if (txt.length > 60) continue;
                var dis = el.getAttribute('disabled') || el.getAttribute('aria-disabled') === 'true';
                if (dis) return 'DISABLED';
                el.click(); return 'OK:' + txt;
            } return 'NO';
        """)
        if res and res.startswith("OK"):
            time.sleep(0.4)
            return True
        if res == "DISABLED":
            raise ModelLimitReached("Flash disabled in picker")
    except ModelLimitReached:
        raise
    except Exception:
        pass
    return False

def _verify_flash_selected(drv, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            txt = _get_current_model_text(drv)
            if txt and "flash" in txt.lower() and "lite" not in txt.lower():
                return True
        except Exception:
            pass
        time.sleep(0.15)
    return False

def ensure_flash_mode(drv):
    current = _get_current_model_text(drv)
    if current and "flash" in current.lower() and "lite" not in current.lower():
        return True
    for attempt in range(1, 4):
        if not _open_model_picker(drv):
            time.sleep(0.4)
            continue
        time.sleep(0.3)
        try:
            clicked = _click_flash_in_picker(drv)
        except ModelLimitReached:
            try:
                drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception:
                pass
            raise
        if clicked and _verify_flash_selected(drv, timeout=2.5):
            return True
        try:
            drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError("Flash mode could not be verified in model picker")

# ----------------------------------------------------------------------------
# CREATE IMAGE SEPARATE ROUTINES
# ----------------------------------------------------------------------------

def click_plus_button(drv):
    try:
        res = drv.execute_script("""
            var btns = document.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                var b = btns[i];
                if (b.offsetParent === null) continue;
                var lbl = (b.getAttribute('aria-label') || '').toLowerCase();
                if (lbl.indexOf('upload') !== -1 || lbl.indexOf('tools') !== -1 || lbl.indexOf('plus') !== -1) {
                    b.click(); return 'OK';
                }
                var icon = b.querySelector('mat-icon[fonticon="plus"], mat-icon[data-mat-icon-name="plus"]');
                if (icon) { b.click(); return 'OK'; }
            } return 'NO';
        """)
        if res == 'OK':
            time.sleep(0.3)
            return True
    except Exception:
        pass
    for sel in ['button[aria-label="Upload and tools"]', 'button[jslog*="300142"]', 'button[aria-haspopup="menu"][aria-label*="Upload"]']:
        try:
            for btn in drv.find_elements(By.CSS_SELECTOR, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            continue
    return False

def click_upload_files_in_drawer(drv):
    for sel in [
        "button[data-test-id='local-images-files-uploader-button']",
        "//span[contains(text(),'Upload files')]/ancestor::button",
        "//div[contains(text(),'Upload files')]/ancestor::button",
    ]:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            for btn in drv.find_elements(by, sel):
                if btn.is_displayed():
                    drv.execute_script("arguments[0].click();", btn)
                    time.sleep(0.2)
                    return True
        except Exception:
            continue
    try:
        res = drv.execute_script("""
            var btns = document.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].offsetParent !== null && btns[i].textContent.toLowerCase().indexOf('upload files') !== -1) {
                    btns[i].click(); return 'OK';
                }
            } return 'NO';
        """)
        if res == 'OK':
            time.sleep(0.2)
            return True
    except Exception:
        pass
    return False

def find_file_input(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if inputs:
        return inputs[0]
    try:
        drv.execute_script("""
            document.querySelectorAll('input[type=\"file\"]').forEach(function(el){
                el.style.cssText='display:block!important;opacity:1!important;position:fixed!important;top:0;left:0;z-index:99999;width:200px;height:50px;';
                el.removeAttribute('hidden'); el.removeAttribute('disabled');
            });
        """)
    except Exception:
        pass
    time.sleep(0.1)
    inputs = drv.find_elements(By.CSS_SELECTOR, "input[type='file']")
    return inputs[0] if inputs else None

def is_create_image_mode(drv):
    try:
        editors = drv.find_elements(By.CSS_SELECTOR, "div.ql-editor[data-placeholder='Describe your image']")
        if not any(e.is_displayed() for e in editors):
            return False
        
        signals = [
            "mat-icon[data-mat-icon-name='image_create']",
            "mat-icon[fonticon='image_create']",
            "button[aria-label*='Aspect ratio']",
            "//span[contains(text(), 'Aspect ratio')]",
            "//button[contains(., 'Images')]",
            "//div[contains(., 'Images') and contains(@class, 'chip')]"
        ]
        for sig in signals:
            by = By.XPATH if sig.startswith("//") else By.CSS_SELECTOR
            for el in drv.find_elements(by, sig):
                if el.is_displayed():
                    return True
        return len(editors) > 0
    except Exception:
        return False

def ensure_create_image_mode(drv, tid=0):
    if is_create_image_mode(drv):
        log(f"[T{tid}] CREATE IMAGE VERIFIED")
        return True

    for attempt in range(1, 3):
        if click_plus_button(drv):
            time.sleep(0.3)
            try:
                btns = drv.find_elements(By.CSS_SELECTOR, "button[role='menuitemcheckbox'].toolbox-drawer-item-list-button")
                for btn in btns:
                    if btn.is_displayed() and "create image" in btn.text.lower():
                        drv.execute_script("arguments[0].click();", btn)
                        time.sleep(0.4)
                        break
                else:
                    for icon in drv.find_elements(By.CSS_SELECTOR, "mat-icon[data-mat-icon-name='image_create'], mat-icon[fonticon='image_create']"):
                        if icon.is_displayed():
                            btn = drv.execute_script("var e=arguments[0];while(e&&e.tagName!=='BUTTON')e=e.parentElement;return e;", icon)
                            if btn and btn.is_displayed():
                                drv.execute_script("arguments[0].click();", btn)
                                time.sleep(0.4)
                                break
            except Exception:
                pass

        time.sleep(0.5)
        if is_create_image_mode(drv):
            log(f"[T{tid}] CREATE IMAGE VERIFIED")
            return True

    raise RuntimeError(f"Tab T{tid}: Failed to activate Create image mode.")

def upload_reference_images(drv, abs_paths, tid=0):
    valid_paths = [p for p in abs_paths if p and os.path.exists(p)]
    expected_count = len(valid_paths)
    if expected_count == 0:
        log(f"[T{tid}] No reference images to upload.")
        return True

    if not click_plus_button(drv):
        log(f"[T{tid}] Failed to click plus button for upload.", file=sys.stderr)
        return False
    time.sleep(0.25)

    if not click_upload_files_in_drawer(drv):
        try:
            drv.execute_script("var b=document.querySelector('button.hidden-local-file-image-selector-button, button[xapfileselectortrigger]'); if(b) b.click();")
            time.sleep(0.15)
        except Exception:
            pass

    fi = find_file_input(drv)
    if not fi:
        log(f"[T{tid}] File input not found.", file=sys.stderr)
        return False

    try:
        fi.send_keys("\n".join(valid_paths))
    except Exception as e:
        log(f"[T{tid}] File input send_keys failed: {e}", file=sys.stderr)
        return False

    # Verify attachment chips count (Part P)
    t0 = time.time()
    verified = False
    chip_count = 0
    while time.time() - t0 < 12.0:
        chips = []
        for sel in [
            "button[aria-label='close attachment']",
            "gem-media-attachment",
            "uploader-file-preview",
            ".attachment-preview-wrapper",
            "div[data-test-id='uploaded-img']",
            "mat-icon[fonticon='close']"
        ]:
            try:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        chips.append(el)
            except Exception:
                pass
        chip_count = len(set(chips))
        if chip_count >= expected_count:
            verified = True
            log(f"[T{tid}] ✅ ATTACHED {expected_count}/{expected_count}")
            break
        time.sleep(0.3)

    if not verified:
        log(f"[T{tid}] ATTACHMENT_FAILED: Expected {expected_count} attachments, verified {chip_count}/{expected_count}", file=sys.stderr)
        return False
    return True

# ----------------------------------------------------------------------------
# ATOMIC PROMPT INJECTION & VERIFICATION
# ----------------------------------------------------------------------------

def normalize_prompt_text(text):
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    lines = [line.rstrip() for line in t.split("\n")]
    return "\n".join(lines).strip()

def _set_clipboard_xclip(text):
    disp = os.environ.get("DISPLAY", ":99")
    env = {**os.environ, "DISPLAY": disp}
    try:
        proc = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=env)
        proc.communicate(input=text.encode("utf-8"), timeout=5)
        return proc.returncode == 0
    except Exception:
        return False

def get_quill_editor(drv):
    for sel in [
        "div.ql-editor[data-placeholder='Describe your image']",
        "div.ql-editor[contenteditable='true']",
        "rich-textarea div[contenteditable='true']",
        "div[contenteditable='true']",
    ]:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return el
        except Exception:
            pass
    return None

def _verify_editor_prompt(drv, editor, expected_text, tid=0):
    try:
        actual_raw = editor.text or ""
        if not actual_raw:
            actual_raw = drv.execute_script("return (arguments[0].textContent || '');", editor) or ""

        expected_norm = normalize_prompt_text(expected_text)
        actual_norm = normalize_prompt_text(actual_raw)

        exp_len = len(expected_norm)
        act_len = len(actual_norm)

        log(f"[T{tid}] PROMPT LENGTH expected={exp_len} actual={act_len}")

        if exp_len == 0:
            return act_len == 0

        coverage = act_len / exp_len
        if coverage < 0.98 or coverage > 1.05:
            log(f"[T{tid}] PROMPT LENGTH MISMATCH: coverage={coverage:.2%}")
            return False

        prefix_len = min(80, exp_len)
        if actual_norm[:prefix_len] != expected_norm[:prefix_len]:
            log(f"[T{tid}] PROMPT START MISMATCH: '{actual_norm[:30]}' != '{expected_norm[:30]}'")
            return False
        log(f"[T{tid}] PROMPT START VERIFIED")

        suffix_len = min(80, exp_len)
        if actual_norm[-suffix_len:] != expected_norm[-suffix_len:]:
            log(f"[T{tid}] PROMPT END MISMATCH: '{actual_norm[-30:]}' != '{expected_norm[-30:]}'")
            return False
        log(f"[T{tid}] PROMPT END VERIFIED")

        log(f"[T{tid}] PROMPT COMPLETE VERIFIED")
        return True
    except Exception as e:
        log(f"[T{tid}] Prompt verification error: {e}")
        return False

PROMPT_EMPTY = "PROMPT_EMPTY"
PROMPT_INJECTING = "PROMPT_INJECTING"
PROMPT_VERIFYING = "PROMPT_VERIFYING"
PROMPT_READY = "PROMPT_READY"
PROMPT_FAILED = "PROMPT_FAILED"

def _inject_prompt_atomic(drv, text, tid=0):
    editor = get_quill_editor(drv)
    if not editor:
        log(f"[T{tid}] PROMPT_FAILED: Quill editor element not found in DOM.")
        return False

    for attempt in range(1, 3):
        try:
            drv.execute_script("arguments[0].focus();", editor)
            time.sleep(0.1)

            # Select all and delete in one operation
            ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            time.sleep(0.05)
            ActionChains(drv).send_keys(Keys.DELETE).perform()
            drv.execute_script("document.execCommand('selectAll',false,null); document.execCommand('delete',false,null);")
            time.sleep(0.1)

            # Primary: Chrome CDP Input.insertText in ONE atomic browser operation
            cdp_ok = False
            try:
                drv.execute_cdp_cmd("Input.insertText", {"text": text})
                cdp_ok = True
            except Exception as cdp_err:
                log(f"[T{tid}] CDP Input.insertText notice ({cdp_err}), trying single xclip Ctrl+V...")

            # Fallback: xclip clipboard ONE TIME only
            if not cdp_ok:
                if _set_clipboard_xclip(text):
                    drv.execute_script("arguments[0].focus();", editor)
                    ActionChains(drv).click(editor).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
                else:
                    log(f"[T{tid}] xclip clipboard setting failed.", file=sys.stderr)

            time.sleep(0.3)

            # Verify complete prompt
            if _verify_editor_prompt(drv, editor, text, tid=tid):
                return True
            else:
                log(f"[T{tid}] Prompt verification failed on attempt {attempt}. Clearing editor...")
                drv.execute_script("arguments[0].focus(); document.execCommand('selectAll',false,null); document.execCommand('delete',false,null);", editor)
                time.sleep(0.3)
        except Exception as e:
            log(f"[T{tid}] Exception during prompt injection (attempt {attempt}): {e}")
            try:
                drv.execute_script("arguments[0].focus(); document.execCommand('selectAll',false,null); document.execCommand('delete',false,null);", editor)
            except Exception:
                pass
            time.sleep(0.3)

    log(f"[T{tid}] PROMPT_FAILED: Failed to inject and verify prompt after 2 atomic attempts.")
    return False

# ----------------------------------------------------------------------------
# SEND & GENERATION VERIFICATION
# ----------------------------------------------------------------------------

def _click_send_button(drv):
    try:
        res = drv.execute_script("""
            var sels = ['mat-icon[fonticon="arrow_upward"]', 'mat-icon[data-mat-icon-name="arrow_upward"]', 'mat-icon[fonticon="send"]', 'button[aria-label="Send message"]'];
            for (var s = 0; s < sels.length; s++) {
                var els = document.querySelectorAll(sels[s]);
                for (var i = 0; i < els.length; i++) {
                    var b = els[i].tagName === 'BUTTON' ? els[i] : els[i].closest('button');
                    if (b && !b.disabled && b.offsetParent !== null) { b.click(); return 'OK'; }
                }
            } return 'NO';
        """)
        if res == 'OK':
            return True
    except Exception:
        pass
    for xp in [
        "//mat-icon[@data-mat-icon-name='arrow_upward']/ancestor::button",
        "//mat-icon[@fonticon='arrow_upward']/ancestor::button",
        "//button[@aria-label='Send message']",
    ]:
        try:
            for btn in drv.find_elements(By.XPATH, xp):
                if btn.is_displayed() and btn.is_enabled():
                    drv.execute_script("arguments[0].click();", btn)
                    return True
        except Exception:
            continue
    return False

def verify_generation_started(drv, timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            stop = drv.execute_script("""
                var sels = ['button[aria-label="Stop generating"]', 'button[aria-label="Cancel"]', 'mat-icon[fonticon="stop"]', 'mat-icon[data-mat-icon-name="stop"]'];
                for (var s = 0; s < sels.length; s++) {
                    var els = document.querySelectorAll(sels[s]);
                    for (var i = 0; i < els.length; i++) {
                        if (els[i].offsetParent !== null) return true;
                    }
                } return false;
            """)
            if stop:
                return True

            loading = drv.execute_script("""
                var el = document.querySelector('image-loading-overlay [data-test-id="image-loading-overlay"]');
                if (el && el.offsetParent !== null) {
                    return !el.classList.contains('done-generating');
                } return false;
            """)
            if loading:
                return True

            in_prog = drv.execute_script("""
                var el = document.querySelector('model-response .generating-sparkle, model-response .loading');
                return el !== null && el.offsetParent !== null;
            """)
            if in_prog:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

# ----------------------------------------------------------------------------
# IMAGE DETECTION & INSTANT MEMORY CAPTURE ROUTINES
# ----------------------------------------------------------------------------

def snapshot_urls(drv):
    try:
        return set(drv.execute_script(
            "return Array.from(document.querySelectorAll('img[src^=\"blob:\"],img[src*=\"googleusercontent\"]')).map(i=>i.src).filter(s=>s&&s.length>10);"
        ) or [])
    except Exception:
        return set()

def _thumb_up_visible(drv):
    try:
        return drv.execute_script("""
            var icons = document.querySelectorAll('mat-icon[data-mat-icon-name="thumb_up"], mat-icon[fonticon="thumb_up"]');
            for (var i = 0; i < icons.length; i++) {
                if (icons[i].offsetParent !== null) return true;
            } return false;
        """)
    except Exception:
        return False

def _send_btn_enabled(drv):
    try:
        return drv.execute_script("""
            var sels = ['mat-icon[fonticon="arrow_upward"]', 'mat-icon[data-mat-icon-name="arrow_upward"]', 'mat-icon[fonticon="send"]', 'button[aria-label="Send message"]'];
            for (var s = 0; s < sels.length; s++) {
                var els = document.querySelectorAll(sels[s]);
                for (var i = 0; i < els.length; i++) {
                    var b = els[i].tagName === 'BUTTON' ? els[i] : els[i].closest('button');
                    if (b && !b.disabled && b.offsetParent !== null) return true;
                }
            } return false;
        """)
    except Exception:
        return False

def _is_gemini_processing(drv):
    try:
        stop = drv.execute_script("""
            var sels = ['button[aria-label="Stop generating"]', 'button[aria-label="Cancel"]', 'mat-icon[fonticon="stop"]', 'mat-icon[data-mat-icon-name="stop"]'];
            for (var s = 0; s < sels.length; s++) {
                var els = document.querySelectorAll(sels[s]);
                for (var i = 0; i < els.length; i++) {
                    if (els[i].offsetParent !== null) return true;
                }
            } return false;
        """)
        if stop:
            return True
        loading = drv.execute_script("""
            var el = document.querySelector('image-loading-overlay [data-test-id="image-loading-overlay"]');
            if (el && el.offsetParent !== null) {
                return !el.classList.contains('done-generating');
            } return false;
        """)
        return bool(loading)
    except Exception:
        return False

def _has_generated_image(drv, urls_before):
    try:
        blob_srcs = drv.execute_script("""
            var srcs = [];
            var imgs = document.querySelectorAll('img[src^="blob:https://gemini.google.com"]');
            for (var i = imgs.length - 1; i >= 0; i--) {
                var img = imgs[i]; if (!img.offsetParent) continue;
                var src = img.getAttribute('src') || '';
                var tid = img.getAttribute('data-test-id') || '';
                if (tid.indexOf('uploaded-img') !== -1 || tid === 'image-preview') continue;
                if (src.length > 10) srcs.push(src);
            } return srcs;
        """) or []
        for src in blob_srcs:
            if src not in urls_before:
                return src
    except Exception:
        pass

    for sel in ["generated-image img", "single-image img", "img[src*='googleusercontent']", "model-response img"]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                if not img.is_displayed():
                    continue
                src = img.get_attribute("src") or ""
                tid = img.get_attribute("data-test-id") or ""
                if len(src) < 10 or "uploaded-img" in tid or tid == "image-preview":
                    continue
                if src in urls_before:
                    continue
                if src.startswith("blob:https://gemini.google.com") or "googleusercontent" in src:
                    return src
        except Exception:
            continue
    return None

def check_gemini_error(drv):
    try:
        b = drv.find_element(By.TAG_NAME, "body").text.lower()
        u = drv.current_url.lower()
        if any(w in b for w in ["encountered an error", "something went wrong", "unable to complete your request"]):
            return "error"
        if any(w in u for w in ["google.com/sorry", "recaptcha"]):
            return "sorry"
    except Exception:
        pass
    return None

def check_text_error(drv):
    try:
        b = drv.find_element(By.TAG_NAME, "body").text.lower()
        if any(w in b for w in ["cannot create images of", "can't create images of", "unable to create that image"]):
            return "refusal"
        if any(w in b for w in ["image-generation limit", "daily limit", "rate limit", "too many requests"]):
            return "limit"
    except Exception:
        pass
    return None

def nb_check_image(drv, urls_before, chat_urls):
    rc = check_text_error(drv)
    if rc:
        return ("REFUSED" if rc == "refusal" else "LIMIT"), None
    ge = check_gemini_error(drv)
    if ge:
        return "ERROR", None

    img_src = _has_generated_image(drv, urls_before)
    if img_src and img_src not in chat_urls:
        return "SUCCESS", img_src

    if _thumb_up_visible(drv):
        img_src2 = _has_generated_image(drv, urls_before)
        if img_src2 and img_src2 not in chat_urls:
            return "SUCCESS", img_src2
        if not _is_gemini_processing(drv):
            return "TIMEOUT", None

    return "WAITING", None

def _direct_fetch_cdp(drv, save_path, urls_before):
    try:
        blob = drv.execute_script("""
            var imgs = document.querySelectorAll(
                'single-image img, generated-image img, img[src^="blob:https://gemini.google.com"], img[src*="googleusercontent"]'
            );
            for (var i = imgs.length - 1; i >= 0; i--) {
                var s = imgs[i].getAttribute('src') || '';
                var tid = imgs[i].getAttribute('data-test-id') || '';
                if (tid.indexOf('uploaded-img') !== -1 || tid === 'image-preview') continue;
                if (s && s.length > 10) return s;
            } return null;
        """)
        if not blob or blob in urls_before:
            return False

        expr = f"""
            (function() {{
                var src = {json.dumps(blob)};
                return fetch(src)
                    .then(function(r) {{ return r.blob(); }})
                    .then(function(b) {{
                        return new Promise(function(resolve) {{
                            var fr = new FileReader();
                            fr.onloadend = function() {{ resolve(fr.result.split(',')[1]); }};
                            fr.onerror = function() {{ resolve(null); }};
                            fr.readAsDataURL(b);
                        }});
                    }}).catch(function(e) {{
                        try {{
                            var imgs = document.querySelectorAll('single-image img, generated-image img, img[src*="googleusercontent"]');
                            for (var i = imgs.length - 1; i >= 0; i--) {{
                                var img = imgs[i];
                                if (img.offsetParent !== null && (img.naturalWidth > 100 || img.width > 100)) {{
                                    var canvas = document.createElement('canvas');
                                    canvas.width = img.naturalWidth;
                                    canvas.height = img.naturalHeight;
                                    var ctx = canvas.getContext('2d');
                                    ctx.drawImage(img, 0, 0);
                                    return canvas.toDataURL('image/png').split(',')[1];
                                }}
                            }}
                        }} catch (ex) {{}}
                        return null;
                    }});
            }})()
        """
        res = drv.execute_cdp_cmd("Runtime.evaluate", {
            "expression": expr,
            "awaitPromise": True,
            "returnByValue": True
        })
        if res and "result" in res and "value" in res["result"] and res["result"]["value"]:
            b64_val = res["result"]["value"]
            data = base64.b64decode(b64_val)
            if len(data) > 5000:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                Path(save_path).write_bytes(data)
                return True
    except Exception:
        pass
    return False

def _hover_and_dl_single_click(drv, urls_before, chat_urls):
    def _try_hover(img):
        try:
            drv.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'});", img)
            time.sleep(0.15)
            ActionChains(drv).move_to_element(img).perform()
            time.sleep(0.2)
            for sel in [
                "button[data-test-id='download-generated-image-button']",
                "//mat-icon[@data-mat-icon-name='download']/ancestor::button",
                "//mat-icon[@fonticon='download']/ancestor::button",
                "button[aria-label*='Download']",
            ]:
                by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                for btn in reversed(drv.find_elements(by, sel)):
                    if btn.is_displayed() and btn.is_enabled():
                        drv.execute_script("arguments[0].click();", btn)
                        return True
        except Exception:
            pass
        return False

    candidates = []
    seen = set()
    for sel in ["single-image img", "generated-image img", "img[src^='blob:https://gemini.google.com']", "img[src*='googleusercontent']"]:
        try:
            for img in drv.find_elements(By.CSS_SELECTOR, sel):
                src = img.get_attribute("src") or ""
                tid = img.get_attribute("data-test-id") or ""
                if ("uploaded-img" in tid or tid == "image-preview" or src in urls_before or src in chat_urls or src in seen or len(src) < 10):
                    continue
                seen.add(src)
                candidates.append(img)
        except Exception:
            continue

    for img in reversed(candidates):
        try:
            if img.is_displayed() and _try_hover(img):
                return True
        except Exception:
            continue

    try:
        clicked = drv.execute_script("""
            var btns = document.querySelectorAll('button[data-test-id="download-generated-image-button"], button[aria-label*="Download"]');
            for (var i = btns.length - 1; i >= 0; i--) {
                var b = btns[i];
                if (b.offsetParent !== null && !b.disabled) {
                    b.scrollIntoView({block:'center'}); b.click(); return 'OK';
                }
            } return null;
        """)
        if clicked:
            return True
    except Exception:
        pass
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
        try:
            params = json.loads(params)
        except Exception:
            params = {}

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
        cur.execute(
            """
            INSERT INTO dead_letter_jobs
                (queue_name, job_name, generation_id, payload_summary, failed_reason,
                 attempts_made, status, worker_id, error_stack)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, 'open', %s, %s)
            """,
            (QUEUE_NAME, 'process-generation', gen['id'], summary, failed_reason[:4000], attempts_made, WORKER_ID, (error_stack or '')[:8000])
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# STEP 12: CENTRAL ASYNC SCHEDULER & PIPELINE COORDINATOR
# ============================================================================

job_queue = asyncio.Queue()
active_downloads = {}
counters = {"completed": 0, "failed": 0}
last_status_print = 0.0

def find_first_idle_tab():
    # Strict lowest-ID priority (T0 -> T1 -> T2 -> T3)
    for tid in range(MAX_CONCURRENT_TABS):
        if tab_states[tid]["state"] == S_IDLE:
            return tid
    return None

def _free_tab(tid, job_id):
    info = tab_states[tid]
    info["state"] = S_IDLE
    info["job"] = None
    info["job_id"] = None
    info["gen"] = None
    info["prompt"] = None
    info["target_src"] = None
    info["download_started"] = False
    info["stuck_polls"] = 0
    info["start_time"] = 0.0
    info["future"] = None
    log(f"[T{tid}][{job_id}] TAB FREED! Immediately available for next queued job.")

async def poll_active_downloads():
    now = time.time()
    for job_id, dinfo in list(active_downloads.items()):
        if dinfo["state"] != "WAITING":
            continue

        raw_path = dinfo["raw_path"]
        job_dir = dinfo["download_dir"]
        files_before = dinfo.get("files_before", set())

        # Direct file check (written via direct memory fetch)
        if raw_path.exists() and raw_path.stat().st_size > 5000:
            dinfo["state"] = "COMPLETE"
            log(f"[{job_id}] DOWNLOAD CONFIRMED ({raw_path.stat().st_size // 1024} KB) -> Immediate handoff to Edge WMR.")
            asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
            continue

        # Check isolated job directory
        found_file = None
        if job_dir.exists():
            for fn in os.listdir(job_dir):
                if fn.endswith(('.crdownload', '.tmp', '.part', '.download')):
                    continue
                if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    continue
                fp = job_dir / fn
                try:
                    if str(fp) in files_before:
                        continue
                    if fp.stat().st_size >= 5000:
                        found_file = fp
                        break
                except Exception:
                    pass

        # Fallback candidate check if not in isolated job_dir (e.g. root Colab downloads)
        if not found_file:
            for cd in [Path('/content/downloads'), Path('/root/Downloads')]:
                if not cd.exists():
                    continue
                for fn in os.listdir(cd):
                    if fn.endswith(('.crdownload', '.tmp', '.part', '.download')):
                        continue
                    if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        continue
                    fp = cd / fn
                    try:
                        if str(fp) in files_before:
                            continue
                        if fp.stat().st_size >= 5000 and (now - fp.stat().st_mtime) < 180:
                            found_file = fp
                            break
                    except Exception:
                        pass
                if found_file:
                    break

        if found_file:
            cur_sz = found_file.stat().st_size
            if cur_sz == dinfo.get("last_size", -1):
                dinfo["stable_checks"] = dinfo.get("stable_checks", 0) + 1
                if dinfo["stable_checks"] >= 2:  # Stable across 2 consecutive polls
                    img_ok = False
                    try:
                        with Image.open(found_file) as im:
                            im.verify()
                        img_ok = True
                    except Exception:
                        img_ok = False

                    if img_ok:
                        raw_path.parent.mkdir(parents=True, exist_ok=True)
                        if str(found_file) != str(raw_path):
                            try:
                                shutil.move(str(found_file), str(raw_path))
                            except Exception:
                                shutil.copy2(str(found_file), str(raw_path))
                                try:
                                    os.remove(str(found_file))
                                except Exception:
                                    pass
                        dinfo["state"] = "COMPLETE"
                        log(f"[{job_id}] DOWNLOAD COMPLETE & STABLE ({raw_path.stat().st_size // 1024} KB) -> Enqueuing for Edge WMR.")
                        asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
            else:
                dinfo["last_size"] = cur_sz
                dinfo["stable_checks"] = 0

        elif now - dinfo["started_at"] > 90.0:
            dinfo["state"] = "FAILED"
            log(f"[{job_id}] ⚠️ Filesystem download timed out after 90s!", file=sys.stderr)
            asyncio.create_task(_handle_job_failure(job_id, dinfo, "Download timed out waiting for file on disk"))

async def _finalize_and_clean_job(job_id, dinfo):
    raw_path = dinfo["raw_path"]
    tid = dinfo["tab_id"]
    gen = dinfo["gen"]
    prompt = dinfo["prompt"]
    job = dinfo["job"]

    try:
        cleaned_path, webp_path = await edge_wmr_worker.remove_watermark_async(job_id, tid, raw_path)

        log(f"[{WORKER_ID}] {job_id}: [STEP_R2_UPLOAD] Pushing final assets to R2 bucket {R2_BUCKET_NAME}...")
        result = sys.modules['fashion_studio'].push_generation(
            image_path=str(cleaned_path),
            prompt=prompt,
            user_id=gen['user_id'],
            gen_id=job_id,
            webp_path=str(webp_path) if webp_path else None,
            force=True,
            params=gen.get('params') or {}
        )

        try:
            sys.modules['credits'].settle_look(job_id)
            log(f"[{WORKER_ID}] {job_id}: [STEP_CREDITS_SETTLE] Credits settled successfully.")
        except Exception as e:
            log(f"[{WORKER_ID}] {job_id}: settle_look warning: {e}", file=sys.stderr)

        counters["completed"] += 1
        log(f"[{WORKER_ID}] {job_id}: [STEP_COMPLETE] Job complete! Output URL: {result.get('output_url')}")
        if dinfo.get("future") and not dinfo["future"].done():
            dinfo["future"].set_result(result)

    except Exception as e:
        counters["failed"] += 1
        log(f"[{WORKER_ID}] {job_id}: Finalization failed: {e}", file=sys.stderr)
        try:
            record_dead_letter(gen, str(e), 1, 1, traceback.format_exc())
            sys.modules['credits'].refund_look(job_id, str(e)[:500])
        except Exception:
            pass
        if dinfo.get("future") and not dinfo["future"].done():
            dinfo["future"].set_exception(e)
    finally:
        active_downloads.pop(job_id, None)

async def _handle_job_failure(job_id, dinfo, reason):
    counters["failed"] += 1
    gen = dinfo["gen"]
    job_id = dinfo["job_id"] if "job_id" in dinfo else job_id
    try:
        record_dead_letter(gen, reason, 1, 1, traceback.format_exc())
        sys.modules['credits'].refund_look(job_id, reason[:500])
    except Exception:
        pass
    if dinfo.get("future") and not dinfo["future"].done():
        dinfo["future"].set_exception(RuntimeError(reason))
    active_downloads.pop(job_id, None)

async def assign_jobs_to_idle_tabs():
    while not job_queue.empty():
        tid = find_first_idle_tab()
        if tid is None:
            break

        job_envelope = await job_queue.get()
        info = tab_states[tid]
        info["state"] = S_SUBMITTING
        info["job"] = job_envelope["job"]
        info["job_id"] = job_envelope["job_id"]
        info["gen"] = job_envelope["gen"]
        info["prompt"] = job_envelope["prompt"]
        info["refs"] = job_envelope["refs"]
        info["future"] = job_envelope["future"]
        info["download_started"] = False
        info["stuck_polls"] = 0
        info["start_time"] = time.time()

        log(f"[T{tid}][{info['job_id']}] ASSIGNED -> Submitting prompt & refs...")
        asyncio.create_task(_submit_job_to_tab(tid))

async def _submit_job_to_tab(tid):
    info = tab_states[tid]
    job_id = info["job_id"]
    try:
        async with chrome_lock:
            chrome_driver.switch_to.window(info["handle"])
            # Healthy tab reuse: do NOT reload Gemini whole page
            start_new_chat(chrome_driver)

            # 1. Switch & verify Flash mode
            try:
                ensure_flash_mode(chrome_driver)
            except ModelLimitReached:
                _recover_stuck_tab(tid, "ModelLimitReached: Flash limit")
                return
            except Exception as e:
                _recover_stuck_tab(tid, f"Flash verification failed: {e}")
                return

            # 2. Activate & verify Create Image mode separately
            try:
                ensure_create_image_mode(chrome_driver, tid=tid)
            except Exception as e:
                _recover_stuck_tab(tid, f"Create Image activation failed: {e}")
                return

            # 3. Upload reference images and verify exact count
            ref_paths = [str(Path(p).resolve()) for p in info["refs"] if p and os.path.exists(p)]
            if not upload_reference_images(chrome_driver, ref_paths, tid=tid):
                _recover_stuck_tab(tid, f"Attachment count mismatch ({len(ref_paths)} references)")
                return

            # 4. Atomic prompt injection (CDP Input.insertText + normalized fingerprint verification)
            if not _inject_prompt_atomic(chrome_driver, info["prompt"], tid=tid):
                _recover_stuck_tab(tid, "Prompt atomic insertion verification failed")
                return

            info["urls_before"] = snapshot_urls(chrome_driver)
            info["chat_urls"] = set()

            # 5. Click Send button
            if not _click_send_button(chrome_driver):
                _recover_stuck_tab(tid, "Failed to click send button")
                return

            # 6. Verify generation started
            if not verify_generation_started(chrome_driver):
                _recover_stuck_tab(tid, "Generation started signal not detected after Send")
                return

            info["state"] = S_GEN_WAITING
            info["next_poll"] = time.time() + 1.2
            log(f"[T{tid}][{job_id}] PROMPT SENT & GENERATION STARTED! Tab T{tid} generating in background.")
    except Exception as e:
        log(f"[T{tid}][{job_id}] Submission error: {e}", file=sys.stderr)
        _recover_stuck_tab(tid, f"Submission error: {e}")

async def poll_active_tabs():
    now = time.time()
    for tid in range(MAX_CONCURRENT_TABS):
        info = tab_states[tid]
        if info["state"] != S_GEN_WAITING:
            continue
        if now < info["next_poll"]:
            continue

        async with chrome_lock:
            chrome_driver.switch_to.window(info["handle"])

            # Independent per-tab timeout
            if now - info["start_time"] > GENERATION_TIMEOUT_S:
                log(f"[T{tid}][{info['job_id']}] HARD TIMEOUT after {GENERATION_TIMEOUT_S}s! Resetting tab T{tid} only.")
                _recover_stuck_tab(tid, "Generation timed out")
                continue

            status, new_src = nb_check_image(chrome_driver, info["urls_before"], info["chat_urls"])

            # Part J: Download click EXACTLY ONCE
            if status == 'SUCCESS' and not info["download_started"]:
                job_id = info["job_id"]
                info["download_started"] = True
                log(f"[T{tid}][{job_id}] IMAGE DETECTED! Initiating immediate capture...")

                job_dir = JOBS_DOWNLOAD_BASE / job_id
                job_dir.mkdir(parents=True, exist_ok=True)
                raw_path = job_dir / f"{job_id}_raw.png"
                files_before = set(os.listdir(job_dir)) if job_dir.exists() else set()

                # A: Instant direct memory / canvas capture (<150ms)
                direct_ok = _direct_fetch_cdp(chrome_driver, str(raw_path), info["urls_before"])
                if direct_ok:
                    info["urls_before"].add(new_src)
                    log(f"[T{tid}][{job_id}] INSTANT DIRECT CAPTURE ({raw_path.stat().st_size // 1024} KB) -> Immediate handoff to Edge WMR.")
                    dinfo = {
                        "job_id": job_id, "tab_id": tid, "job": info["job"], "gen": info["gen"],
                        "prompt": info["prompt"], "download_dir": job_dir, "raw_path": raw_path,
                        "files_before": files_before, "started_at": time.time(), "last_size": raw_path.stat().st_size,
                        "stable_checks": 3, "state": "COMPLETE", "future": info.get("future")
                    }
                    active_downloads[job_id] = dinfo
                    # Tab freed immediately!
                    _free_tab(tid, job_id)
                    asyncio.create_task(_finalize_and_clean_job(job_id, dinfo))
                else:
                    # B: Single-click hover download into isolated job directory
                    set_tab_download_dir(chrome_driver, job_dir)
                    hover_ok = _hover_and_dl_single_click(chrome_driver, info["urls_before"], info["chat_urls"])
                    info["urls_before"].add(new_src)
                    log(f"[T{tid}][{job_id}] DOWNLOAD CLICKED (success={hover_ok}) -> Handing off to disk watcher.")
                    active_downloads[job_id] = {
                        "job_id": job_id, "tab_id": tid, "job": info["job"], "gen": info["gen"],
                        "prompt": info["prompt"], "download_dir": job_dir, "raw_path": raw_path,
                        "files_before": files_before, "started_at": time.time(), "last_size": -1,
                        "stable_checks": 0, "state": "WAITING", "future": info.get("future")
                    }
                    # Tab freed immediately!
                    _free_tab(tid, job_id)

                # Immediately assign next queued job to this newly freed tab!
                if not job_queue.empty():
                    asyncio.create_task(assign_jobs_to_idle_tabs())
                continue

            elif status == 'ERROR':
                log(f"[T{tid}][{info['job_id']}] Gemini reported generation error.")
                _recover_stuck_tab(tid, "Gemini reported error")
                continue

            elif status == 'REFUSED':
                log(f"[T{tid}][{info['job_id']}] Prompt refused by Gemini.")
                _recover_stuck_tab(tid, "Prompt refused")
                continue

            elif status == 'LIMIT':
                log(f"[T{tid}][{info['job_id']}] Image generation limit reached.")
                _recover_stuck_tab(tid, "Limit reached")
                continue

            else:  # WAITING
                if _send_btn_enabled(chrome_driver) and not _is_gemini_processing(chrome_driver):
                    info["stuck_polls"] += 1
                    if info["stuck_polls"] >= 8:
                        log(f"[T{tid}][{info['job_id']}] SOFT STUCK detected on tab T{tid}! Resetting tab T{tid} only.")
                        _recover_stuck_tab(tid, "Soft stuck detected")
                        continue
                else:
                    info["stuck_polls"] = 0

                elapsed = now - info["start_time"]
                interval = 1.0 if elapsed < 20 else (2.0 if elapsed < 180 else 0.8)
                info["next_poll"] = now + interval

def _recover_stuck_tab(tid, reason):
    info = tab_states[tid]
    job_id = info["job_id"]
    gen = info["gen"]
    future = info.get("future")

    # Full reload ONLY on recovery
    try:
        chrome_driver.switch_to.window(info["handle"])
        chrome_driver.get(GEMINI_APP_URL)
        time.sleep(1.0)
    except Exception:
        pass

    info["state"] = S_IDLE
    info["job"] = None
    info["job_id"] = None
    info["gen"] = None
    info["prompt"] = None
    info["download_started"] = False
    info["stuck_polls"] = 0
    info["start_time"] = 0.0
    info["future"] = None

    counters["failed"] += 1
    if gen:
        try:
            record_dead_letter(gen, reason, 1, 1, traceback.format_exc())
            sys.modules['credits'].refund_look(job_id, reason[:500])
        except Exception:
            pass
    if future and not future.done():
        future.set_exception(RuntimeError(reason))

    log(f"[T{tid}] TAB T{tid} RECOVERED & FREED. Ready for next job.")
    if not job_queue.empty():
        asyncio.create_task(assign_jobs_to_idle_tabs())

def print_pipeline_status():
    global last_status_print
    now = time.time()
    if now - last_status_print < 15.0:
        return
    last_status_print = now

    gen_count = sum(1 for st in tab_states if st["state"] == S_GEN_WAITING)
    dl_waiting_count = sum(1 for d in active_downloads.values() if d.get("state") == "WAITING")
    wmr_count = edge_wmr_worker.work_queue.qsize() if hasattr(edge_wmr_worker, "work_queue") else 0
    fin_count = sum(1 for d in active_downloads.values() if d.get("state") in ("COMPLETE", "FINALIZING"))

    print("\n" + "=" * 70)
    print(f"📊 PIPELINE STATUS [{time.strftime('%H:%M:%S')}]")
    print(f"  QUEUE: {job_queue.qsize()} | GENERATING: {gen_count} | DOWNLOAD_WAITING: {dl_waiting_count} | WMR: {wmr_count} | FINALIZING: {fin_count} | COMPLETED: {counters['completed']} | FAILED: {counters['failed']}")

    print("  TABS:")
    for tid in range(MAX_CONCURRENT_TABS):
        st = tab_states[tid]
        state = st["state"]
        jid = st["job_id"][:8] if st["job_id"] else "---"
        elapsed = f"{int(now - st['start_time'])}s" if st["start_time"] > 0 else "0s"
        print(f"    T{tid} = {state:<13} Job={jid} ({elapsed})")

    if active_downloads:
        print("  DOWNLOADS:")
        for jid, dinfo in list(active_downloads.items()):
            dst = dinfo.get("state", "UNKNOWN")
            el = f"{now - dinfo['started_at']:.1f}s"
            print(f"    Job {jid[:8]} = {dst} ({el})")
    print("=" * 70 + "\n")

async def central_scheduler_loop():
    while True:
        try:
            # STEP 1 — POLL ACTIVE FILE DOWNLOADS
            await poll_active_downloads()

            # STEP 2 — ASSIGN IDLE TABS (lowest-ID priority)
            await assign_jobs_to_idle_tabs()

            # STEP 3 — POLL ALL GENERATING TABS
            await poll_active_tabs()

            # STEP 4 — STATUS DISPLAY
            print_pipeline_status()
        except Exception as e:
            log(f"Scheduler loop error: {e}", file=sys.stderr)
        # STEP 5 — SHORT SCHEDULER SLEEP
        await asyncio.sleep(0.1)


# ============================================================================
# STEP 13: BULLMQ WORKER & MAIN ENTRYPOINT
# ============================================================================
from bullmq import Worker

async def process_bullmq_job(job, job_token):
    gen_id = job.data.get('generationId') or job.data.get('id') or (job.id if job else None)
    log(f"[{WORKER_ID}] picked up generation {gen_id} (attempt {job.attemptsMade + 1})")

    gen = fetch_generation(gen_id)
    if gen is None:
        log(f"[{WORKER_ID}] {gen_id}: row not found in DB, skipping")
        return {'skipped': 'row_not_found'}

    try:
        prompt, garment_path, model_path, holo_path = resolve_prompt_and_refs(gen)
    except Exception as e:
        log(f"[{WORKER_ID}] {gen_id}: failed resolving refs: {e}", file=sys.stderr)
        raise

    loop = asyncio.get_running_loop()
    done_future = loop.create_future()

    job_envelope = {
        "job_id": gen_id,
        "job": job,
        "gen": gen,
        "prompt": prompt,
        "refs": [p for p in (garment_path, holo_path, model_path) if p],
        "future": done_future
    }

    await job_queue.put(job_envelope)
    return await done_future

async def main():
    log(f"[{WORKER_ID}] connecting to {REDIS_URL} queue={QUEUE_NAME!r} prefix={REDIS_KEY_PREFIX!r}")

    worker = Worker(
        QUEUE_NAME,
        process_bullmq_job,
        {
            'connection': REDIS_URL,
            'prefix': REDIS_KEY_PREFIX,
            'concurrency': 8
        }
    )

    scheduler_task = asyncio.create_task(central_scheduler_loop())
    log(f"[{WORKER_ID}] waiting for jobs (Ctrl+C to stop)...")

    try:
        await scheduler_task
    except (KeyboardInterrupt, asyncio.CancelledError):
        log(f"\n[{WORKER_ID}] Stopping worker gracefully...")
    finally:
        await worker.close()
        try:
            chrome_driver.quit()
        except Exception:
            pass
        if edge_wmr_worker.driver:
            try:
                edge_wmr_worker.driver.quit()
            except Exception:
                pass

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
