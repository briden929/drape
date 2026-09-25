import re

with open('v10_work.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''    log(f"{prefix} RECOVERING tab T{tid}: {reason}")

    # Close the stuck physical tab entirely — fresh tab created for next job
    try:
        if info.get("handle"):
            chrome_driver.switch_to.window(info["handle"])
            chrome_driver.close()
    except Exception:
        pass'''

replacement = '''    log(f"{prefix} RECOVERING tab T{tid}: {reason}")

    # Save debug artifacts
    try:
        if info.get("handle"):
            chrome_driver.switch_to.window(info["handle"])
            debug_dir = Path("debug") / job_id
            debug_dir.mkdir(parents=True, exist_ok=True)
            chrome_driver.save_screenshot(str(debug_dir / "error.png"))
            with open(debug_dir / "url.txt", "w", encoding="utf-8") as df: df.write(chrome_driver.current_url)
            with open(debug_dir / "body.txt", "w", encoding="utf-8") as df: df.write(chrome_driver.find_element(By.TAG_NAME, "body").text)
            with open(debug_dir / "page.html", "w", encoding="utf-8") as df: df.write(chrome_driver.page_source)
    except Exception:
        pass

    # Close the stuck physical tab entirely — fresh tab created for next job
    try:
        if info.get("handle"):
            chrome_driver.switch_to.window(info["handle"])
            chrome_driver.close()
    except Exception:
        pass'''

if target in text:
    text = text.replace(target, replacement)
    with open('v10_work.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched debug artifacts')
else:
    print('Target not found')
