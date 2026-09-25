from selenium import webdriver
options = webdriver.ChromeOptions()
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
print("Capability test ok")
