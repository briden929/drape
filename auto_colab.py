import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# YOUR NOTEBOOK LINK
COLAB_URL = "https://colab.research.google.com/drive/1QSdis_FfJA6FzeONzISmBCTpYNNgnc18"

def main():
    print("🚀 Starting Auto-Colab Runner...")
    
    # Setup Chrome
    opts = Options()
    opts.add_argument("--start-maximized")
    # We don't use headless because Colab needs a real browser session
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    
    try:
        # 1. Open Notebook
        print(f"🌐 Opening {COLAB_URL}")
        driver.get(COLAB_URL)
        time.sleep(5) # Wait for page load
        
        # 2. Click Connect Button
        print("🔌 Looking for Connect button...")
        try:
            # Try to find the Connect button (selectors vary by Colab version)
            connect_btn = driver.find_element(By.CSS_SELECTOR, "colab-connect-button")
            connect_btn.click()
            print("✅ Clicked Connect!")
        except Exception as e:
            print(f"⚠️ Could not find Connect button automatically: {e}")
            print("👉 Please click 'Connect' manually in the browser.")
            
        time.sleep(10) # Wait for runtime to connect
        
        # 3. Click "Show Code"
        print("📄 Expanding code...")
        try:
            show_code = driver.find_element(By.XPATH, "//div[contains(text(), 'Show code')]")
            show_code.click()
            print("✅ Code expanded!")
        except:
            print("⚠️ Code might already be expanded.")
            
        # 4. Click Play Button (Run cell)
        print("▶️ Running script...")
        try:
            # Find the play button for the first cell
            play_btn = driver.find_element(By.CSS_SELECTOR, "colab-run-button")
            play_btn.click()
            print("✅ Script started! You can minimize this window now.")
        except Exception as e:
            print(f"️ Could not click Play: {e}")
            
        print("🎉 Automation complete. Keep this browser window open!")
        print(" Tip: You can minimize the window, but don't close it.")
        
        # Keep script running so browser stays open
        input("Press Enter to close the browser and stop...")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()