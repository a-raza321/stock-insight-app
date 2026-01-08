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

warnings.filterwarnings("ignore")
os.environ["WDM_LOG_LEVEL"] = "0"


def scrape_ceo_data(company):
    company = company.upper()

    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")

    driver = None
    ceo_shares_count = None  # Variable to store the numeric value for calculation

    try:
        driver = uc.Chrome(options=options, suppress_welcome=True)
        wait = WebDriverWait(driver, 10)

        driver.get("https://finance.yahoo.com/")
        time.sleep(1)

        # ---------------- SEARCH COMPANY ----------------
        search = wait.until(EC.presence_of_element_located((By.ID, "ybar-sbq")))
        search.clear()
        search.send_keys(company)
        search.submit()
        time.sleep(2)

        # ---------------- CLICK HOLDERS TAB ----------------
        try:
            holders_tab = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[normalize-space()='Holders']"))
            )
            holders_tab.click()
            time.sleep(1)
        except TimeoutException:
            pass

        # ---------------- CLICK INSIDER ROSTER TAB ----------------
        try:
            insider_tab = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Insider Roster')]"))
            )
            driver.execute_script("arguments[0].click();", insider_tab)
            time.sleep(2)
        except TimeoutException:
            driver.get(f"https://finance.yahoo.com/quote/{company}/insider-roster")
            time.sleep(2)

        # ---------------- SCROLL ----------------
        for _ in range(6):
            driver.execute_script("window.scrollBy(0, 700);")
            time.sleep(0.3)

        # ---------------- SCRAPE INSIDER TABLE ----------------
        try:
            tbody = wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
            rows = tbody.find_elements(By.TAG_NAME, "tr")

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 4:
                    continue

                first_cell = cols[0]
                name = first_cell.find_element(By.TAG_NAME, "p").text.strip()
                full_text = first_cell.text
                title = full_text.replace(name, "").strip()

                if "Chief Executive Officer" in title:
                    shares = cols[3].text.strip()
                    if shares == "--" or not shares:
                        shares = "Not Available"
                    else:
                        # Clean the string to convert it to a float for calculation
                        try:
                            ceo_shares_count = float(shares.replace(',', ''))
                        except ValueError:
                            ceo_shares_count = None

                    return calculate_ownership(company, ceo_shares_count)

        except TimeoutException:
            pass

        # ---------------- PROFILE PAGE FALLBACK ----------------
        driver.get(f"https://finance.yahoo.com/quote/{company}/profile")
        time.sleep(2)

        rows = driver.find_elements(By.XPATH, "//section//table//tbody/tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 2:
                continue

            name = cols[0].text.strip()
            title = cols[1].text.strip()
            if "Chief Executive Officer" in title:
                return calculate_ownership(company, None)

        return "N/A"

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def calculate_ownership(ticker, ceo_shares):
    """
    Calculates ownership percentage: (CEO Shares / Shares Outstanding) * 100
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        shares_outstanding = info.get('sharesOutstanding')

        if shares_outstanding and ceo_shares:
            percentage = (ceo_shares / shares_outstanding) * 100
            return f"{percentage:.4f}%"
        else:
            return "N/A"
    except Exception:
        return "N/A"


# TICKER RECEPTION: Called from app.py
def run_process(ticker_from_app):
    if ticker_from_app:
        # Pass the ticker from app.py into the scrape function and return result
        return scrape_ceo_data(ticker_from_app)
    return "N/A"


if __name__ == "__main__":
    company = input("Enter company name or ticker: ").strip()
    if company:
        print(run_process(company))

    sys.stderr = open(os.devnull, 'w')
