from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re

def get_moat_score(ticker):
    """
    Fetches the Moat Score for a given ticker from GuruFocus.
    Returns the score as a string or an error message.
    """
    # 1. Setup Chrome Options for High Speed
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run without a window
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")  # Disable images for speed

    # Optional: Set a common User-Agent to avoid bot detection
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    # 2. Initialize the Driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        # Construct URL (GuruFocus uses a direct term page)
        url = f"https://www.gurufocus.com/term/moat-score/{ticker.upper()}"
        driver.get(url)

        # 3. Explicit Wait for the score element
        wait = WebDriverWait(driver, 10)

        # Locate the element containing the "Moat Score of X" text
        target_xpath = "//h1[contains(text(), 'Moat Score')] | //div[contains(@class, 'term-description')]//p"

        # Trigger the wait to ensure the page loads
        wait.until(EC.presence_of_element_located((By.XPATH, target_xpath)))
        page_text = driver.page_source

        # Fast parsing from the page source
        # The Moat Score is usually explicitly stated: "{Company} has the Moat Score of 8"
        match = re.search(r"Moat Score of (\d+)", page_text)

        if match:
            return match.group(1)
        else:
            return "Score not found (Ticker might be invalid or data unavailable)"

    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        driver.quit()