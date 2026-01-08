import os
import time
import warnings
import sys
import tempfile
import yfinance as yf
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager

warnings.filterwarnings("ignore")

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Path for Streamlit Cloud
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Apply Stealth to mimic undetected_chromedriver behavior
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    return driver

def scrape_ceo_data(company):
    company = company.upper()
    driver = None
    ceo_shares_count = None

    try:
        driver = get_driver()
        wait = WebDriverWait(driver, 15)

        driver.get("https://finance.yahoo.com/")
        time.sleep(2)

        # Cookie Consent
        try:
            consent = driver.find_elements(By.XPATH, "//button[@name='agree']|//button[contains(@class,'btn-primary')]")
            if consent: consent[0].click()
        except: pass

        search = wait.until(EC.presence_of_element_located((By.ID, "ybar-sbq")))
        search.send_keys(company)
        search.submit()
        time.sleep(3)

        # Direct Navigation to Insider Roster
        curr_url = driver.current_url.split('?')[0]
        ticker = curr_url.split("/quote/")[1].split("/")[0] if "/quote/" in curr_url else company
        driver.get(f"https://finance.yahoo.com/quote/{ticker}/insider-roster")
        time.sleep(3)

        try:
            driver.execute_script("window.scrollBy(0, 800);")
            tbody = wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
            rows = tbody.find_elements(By.TAG_NAME, "tr")

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 4: continue
                
                title_cell = cols[0].text
                if "Chief Executive Officer" in title_cell or "CEO" in title_cell:
                    shares_text = cols[3].text.replace(',', '')
                    try:
                        ceo_shares_count = float(shares_text)
                    except:
                        ceo_shares_count = None
                    return calculate_ownership(company, ceo_shares_count)
        except: pass

        # Fallback to Profile
        driver.get(f"https://finance.yahoo.com/quote/{company}/profile")
        time.sleep(2)
        rows = driver.find_elements(By.XPATH, "//section//table//tbody/tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2 and ("Chief Executive Officer" in cols[1].text or "CEO" in cols[1].text):
                return calculate_ownership(company, None)

        return "N/A"
    except:
        return "N/A"
    finally:
        if driver: driver.quit()

def calculate_ownership(ticker, ceo_shares):
    try:
        stock = yf.Ticker(ticker)
        so = stock.info.get('sharesOutstanding')
        if so and ceo_shares:
            return f"{(ceo_shares / so) * 100:.4f}%"
        return "N/A"
    except:
        return "N/A"

def run_process(ticker_from_app):
    return scrape_ceo_data(ticker_from_app) if ticker_from_app else "N/A"
