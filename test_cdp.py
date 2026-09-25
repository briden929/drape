import undetected_chromedriver as uc
import time, json

options = uc.ChromeOptions()
options.add_argument("--headless=new")
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

driver = uc.Chrome(options=options)
driver.execute_cdp_cmd('Browser.setDownloadBehavior', {
    'behavior': 'allowAndName',
    'downloadPath': '/tmp',
    'eventsEnabled': True
})

driver.get("data:text/html,<a id='dl' href='data:text/plain,hello' download='test.txt'>Download</a>")
time.sleep(1)
driver.find_element("id", "dl").click()
time.sleep(2)

logs = driver.get_log("performance")
for log in logs:
    msg = json.loads(log["message"])["message"]
    if msg["method"].startswith("Browser.download"):
        print(msg)
        
driver.quit()
