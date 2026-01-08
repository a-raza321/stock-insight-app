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


def get_ceo_ownership(ticker):
    ticker = ticker.upper()

    # 1. Get Shares Outstanding using yfinance
    shares_outstanding = None
    try:
        stock = yf.Ticker(ticker)
        shares_outstanding = stock.info.get('sharesOutstanding')
    except:
        pass

    if not shares_outstanding:
        return "N/A"

    # 2. Scrape CEO Shares Owned using the provided logic
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")

    driver = None
    ceo_shares_owned = None

    try:
        driver = uc.Chrome(options=options, suppress_welcome=True)
        wait = WebDriverWait(driver, 10)

        driver.get("https://finance.yahoo.com/")
        time.sleep(1)

        # ---------------- SEARCH COMPANY ----------------
        search = wait.until(EC.presence_of_element_located((By.ID, "ybar-sbq")))
        search.clear()
        search.send_keys(ticker)
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
            driver.get(f"https://finance.yahoo.com/quote/{ticker}/insider-roster")
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
                    shares_str = cols[3].text.strip().replace(",", "")
                    if shares_str and shares_str != "--":
                        try:
                            ceo_shares_owned = float(shares_str)
                            break
                        except ValueError:
                            pass
        except TimeoutException:
            pass

        # ---------------- PROFILE PAGE FALLBACK (If shares not in roster) ----------------
        if ceo_shares_owned is None:
            driver.get(f"https://finance.yahoo.com/quote/{ticker}/profile")
            time.sleep(2)
            rows = driver.find_elements(By.XPATH, "//section//table//tbody/tr")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 2: continue
                title = cols[1].text.strip()
                if "Chief Executive Officer" in title:
                    # Note: Profile page usually doesn't show share count,
                    # but we keep the navigation logic as requested.
                    break

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    # 3. Calculate Percentage
    if ceo_shares_owned is not None and shares_outstanding:
        percentage = (ceo_shares_owned / shares_outstanding) * 100
        return f"{percentage:.4f}%"

    return "N/A"


if __name__ == "__main__":
    ticker_input = input("Enter ticker: ").strip()
    if ticker_input:
        print(get_ceo_ownership(ticker_input))
    else:
        print("N/A")

    sys.stderr = open(os.devnull, 'w')
