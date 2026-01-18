from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import streamlit as st

def get_moat_score(ticker):
    """
    Fetches the Moat Score for a given ticker from GuruFocus.
    Updated for Streamlit Cloud compatibility.
    """
    # 1. Setup Chrome Options for Cloud Environment
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    )
    
    # 2. Initialize the Driver 
    # Streamlit Cloud provides Chrome/ChromeDriver at these paths if configured in packages.txt
    try:
        # On Streamlit Cloud, the driver is usually in the PATH, so we don't need Service(ChromeDriverManager)
        driver = webdriver.Chrome(options=chrome_options)
    except Exception:
        # Fallback for local testing if the above fails
        from webdriver_manager.chrome import ChromeDriverManager
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
        match = re.search(r"Moat Score of (\d+)", page_text)

        if match:
            return match.group(1)
        else:
            return "Score not found (Ticker might be invalid or data unavailable)"

    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        driver.quit()

# Simple Streamlit UI for testing
st.title("Moat Score Scraper")
ticker_input = st.text_input("Enter Ticker (e.g., AAPL):", "AAPL")
if st.button("Get Score"):
    with st.spinner("Fetching data..."):
        score = get_moat_score(ticker_input)
        st.write(f"**Result for {ticker_input.upper()}:** {score}")
