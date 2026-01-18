import os
import sys
import re
import subprocess
import streamlit as st
from playwright.sync_api import sync_playwright

# Streamlit Cloud helper: Ensure Playwright browsers are installed
def install_playwright():
    try:
        # Check if chromium is already available
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Error installing Playwright browsers: {e}")

def get_iv_rank_advanced(ticker):
    """
    Uses Playwright to scrape IV Rank from Unusual Whales.
    Handles 'NaN' placeholders by waiting for actual numeric data.
    Returns the result string for capture by other scripts.
    """
    ticker = ticker.upper().strip()
    url = f"https://unusualwhales.com/stock/{ticker}/volatility"

    # In Streamlit, we want to ensure browsers exist before starting
    install_playwright()

    with sync_playwright() as p:
        # Use --no-sandbox and --disable-dev-shm-usage for cloud environments
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # Increased timeout for cloud environment latency
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            iv_rank = None
            max_retries = 15 # Increased retries for slower cloud execution

            for i in range(max_retries):
                content = page.content()

                # Regex to find "IV Rank" followed by a number
                match = re.search(r"IV Rank\s+([\d\.]+)", content)

                if match:
                    iv_rank = match.group(1)
                    break

                try:
                    locator = page.get_by_text("IV Rank", exact=False).first
                    if locator.is_visible():
                        parent_text = locator.evaluate("el => el.parentElement.innerText")
                        val_match = re.search(r"(\d+\.\d+|\d+)", parent_text)
                        if val_match:
                            iv_rank = val_match.group(1)
                            break
                except:
                    pass

                page.wait_for_timeout(2000)  # Wait 2s in cloud environments

            if iv_rank:
                return f"Success! The IV Rank for {ticker} is: {iv_rank}"
            else:
                return f"Could not find valid IV Rank for {ticker}. The value remained NaN or the page structure is blocked."

        except Exception as e:
            return f"An error occurred: {str(e)}"
        finally:
            browser.close()

def main():
    st.set_page_config(page_title="IV Rank Scraper", page_icon="📈")
    st.title("Unusual Whales IV Rank Scraper")
    st.write("Enter a ticker symbol below to fetch the current IV Rank.")

    user_ticker = st.text_input("Enter a stock ticker (e.g., AAPL, TSLA):", "").upper().strip()

    if st.button("Get IV Rank"):
        if user_ticker:
            with st.spinner(f"Scraping data for {user_ticker}... This may take a minute."):
                result = get_iv_rank_advanced(user_ticker)
                
                if "Success" in result:
                    st.success(result)
                else:
                    st.error(result)
        else:
            st.warning("Please enter a valid ticker.")

if __name__ == "__main__":
    main()
