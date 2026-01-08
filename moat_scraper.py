import re
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def get_moat_score_selenium(ticker):
    """
    Retrieves the Moat Score by visiting the dedicated Term Definition page.
    Optimized for Streamlit Cloud (Linux) environments.
    """
    ticker = ticker.upper().strip()
    url = f"https://www.gurufocus.com/term/moat-score/{ticker}"

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Streamlit Cloud workaround: Detect binary location if it exists
    # Standard path for Chromium in the Streamlit Cloud Linux environment
    if os.path.exists("/usr/bin/chromium"):
        chrome_options.binary_location = "/usr/bin/chromium"
    elif os.path.exists("/usr/bin/chromium-browser"):
        chrome_options.binary_location = "/usr/bin/chromium-browser"

    driver = None
    try:
        # Initializing Service with ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Set page load timeout to handle slow cloud networking
        driver.set_page_load_timeout(30)
        driver.get(url)

        wait = WebDriverWait(driver, 20)
        try:
            # Wait for the main body or a specific text container
            main_content = wait.until(EC.presence_of_element_located((By.TAG_NAME, "body"))).text

            # Use regex to find the specific pattern "Moat Score of X"
            match = re.search(r"Moat Score of (\d+)", main_content)

            if match:
                score = match.group(1)
                rating = "Unknown"
                if "Wide Moat" in main_content:
                    rating = "Wide Moat"
                elif "Narrow Moat" in main_content:
                    rating = "Narrow Moat"
                elif "No Moat" in main_content:
                    rating = "No Moat"
                return f"{score} ({rating})"

            # Fallback Logic: check specific selectors if regex fails
            fallback_selectors = ["h1", ".term-value", ".definition-section h1", ".t-title"]
            for selector in fallback_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if "Moat Score" in el.text:
                        return el.text.strip()

            return "N/A"
        except Exception:
            return "N/A"

    except Exception:
        return "N/A"

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


if __name__ == "__main__":
    ticker = input("Enter ticker: ")
    print(get_moat_score_selenium(ticker))