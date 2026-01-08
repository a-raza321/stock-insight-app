import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import warnings
import sys
import os
import time
import yfinance as yf
import tempfile

warnings.filterwarnings("ignore")
os.environ["WDM_LOG_LEVEL"] = "0"

def scrape_ceo_data(company):
    company = company.upper()

    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    options.add_argument("--window-size=1920,1080")
    
    # Streamlit Cloud workaround: Use a temporary directory for user data
    tmp_dir = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={tmp_dir}")

    driver = None
    ceo_shares_count = None

    try:
        # Detect Chromium binary path for Streamlit Cloud
        chrome_path = None
        if os.path.exists("/usr/bin/chromium"):
            chrome_path = "/usr/bin/chromium"
        elif os.path.exists("/usr/bin/chromium-browser"):
            chrome_path = "/usr/bin/chromium-browser"

        # Initialize the Chrome driver using the previous uc approach
        # Note: use_subprocess=False and a specific browser_executable_path are key for Cloud
        driver = uc.Chrome(
            options=options, 
            browser_executable_path=chrome_path,
            suppress_welcome=True,
            use_subprocess=False,
            headless=True
        )
        
        wait = WebDriverWait(driver, 15) 

        # Step 1: Search Company
        driver.get("https://finance.yahoo.com/")
        time.sleep(2)

        try:
            consent_button = driver.find_elements(By.XPATH, "//button[@name='agree']|//button[contains(@class,'btn-primary')]")
            if consent_button:
                consent_button[0].click()
                time.sleep(1)
        except:
            pass

        search = wait.until(EC.presence_of_element_located((By.ID, "ybar-sbq")))
        search.clear()
        search.send_keys(company)
        search.submit()
        time.sleep(3)

        # Step 2: Navigate to Insider Roster directly
        current_url = driver.current_url.split('?')[0]
        if "/quote/" in current_url:
            ticker_from_url = current_url.split("/quote/")[1].split("/")[0]
            insider_url = f"https://finance.yahoo.com/quote/{ticker_from_url}/insider-roster"
            driver.get(insider_url)
        else:
            driver.get(f"https://finance.yahoo.com/quote/{company}/insider-roster")
            
        time.sleep(3)

        # Step 3: Scrape Insider Table
        try:
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)
            
            tbody = wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
            rows = tbody.find_elements(By.TAG_NAME, "tr")

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 4:
                    continue

                first_cell = cols[0]
                try:
                    name_p = first_cell.find_elements(By.TAG_NAME, "p")
                    name = name_p[0].text.strip() if name_p else ""
                    full_text = first_cell.text
                    title = full_text.replace(name, "").strip()
                except:
                    title = first_cell.text

                if "Chief Executive Officer" in title or "CEO" in title:
                    shares_text = cols[3].text.strip()
                    if shares_text and shares_text != "--":
                        try:
                            ceo_shares_count = float(shares_text.replace(',', ''))
                        except ValueError:
                            ceo_shares_count = None
                    
                    return calculate_ownership(company, ceo_shares_count)

        except Exception:
            pass

        # Step 4: Profile Page Fallback
        driver.get(f"https://finance.yahoo.com/quote/{company}/profile")
        time.sleep(2)

        profile_rows = driver.find_elements(By.XPATH, "//section//table//tbody/tr")
        for row in profile_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                title = cols[1].text.strip()
                if "Chief Executive Officer" in title or "CEO" in title:
                    return calculate_ownership(company, None)

        return "N/A"

    except Exception as e:
        return "N/A"

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def calculate_ownership(ticker, ceo_shares):
    try:
        stock = yf.Ticker(ticker)
        shares_outstanding = stock.info.get('sharesOutstanding')

        if shares_outstanding and ceo_shares:
            percentage = (ceo_shares / shares_outstanding) * 100
            return f"{percentage:.4f}%"
        elif shares_outstanding is None:
            return "Data Unavailable"
        else:
            return "N/A"
    except Exception:
        return "N/A"

def run_process(ticker_from_app):
    if ticker_from_app:
        return scrape_ceo_data(ticker_from_app)
    return "N/A"
