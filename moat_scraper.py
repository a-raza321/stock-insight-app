import re
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
    Exact logic as provided by user.
    """
    ticker = ticker.upper().strip()
    url = f"https://www.gurufocus.com/term/moat-score/{ticker}"

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.get(url)

        wait = WebDriverWait(driver, 15)
        try:
            main_content = wait.until(EC.presence_of_element_located((By.TAG_NAME, "body"))).text
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
                driver.quit()
                return f"{score} ({rating})"

            # Fallback
            fallback_selectors = ["h1", ".term-value", ".definition-section h1"]
            for selector in fallback_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if "Moat Score" in el.text:
                        txt = el.text.strip()
                        driver.quit()
                        return txt

            driver.quit()
            return "N/A"
        except:
            driver.quit()
            return "N/A"
    except:
        return "N/A"
