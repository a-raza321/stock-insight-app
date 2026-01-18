import sys
import re
from playwright.sync_api import sync_playwright


def get_iv_rank_advanced(ticker):
    """
    Uses Playwright to scrape IV Rank from Unusual Whales.
    Handles 'NaN' placeholders by waiting for actual numeric data.
    Returns the result string for capture by other scripts.
    """
    ticker = ticker.upper().strip()
    url = f"https://unusualwhales.com/stock/{ticker}/volatility"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded")

            iv_rank = None
            max_retries = 10

            for i in range(max_retries):
                # We search for text containing "IV Rank"
                # Unusual Whales often displays this in a card or header
                content = page.content()

                # Regex to find "IV Rank" followed by a number (including decimals)
                # This ignores "NaN" because \d requires at least one digit
                match = re.search(r"IV Rank\s+([\d\.]+)", content)

                if match:
                    iv_rank = match.group(1)
                    break

                # Alternate strategy: Look for specific card headers in their UI
                try:
                    # Looking for the div that contains 'IV Rank' text
                    locator = page.get_by_text("IV Rank", exact=False).first
                    if locator.is_visible():
                        parent_text = locator.evaluate("el => el.parentElement.innerText")
                        # Extract number from parent text like "IV Rank\n24.5"
                        val_match = re.search(r"(\d+\.\d+|\d+)", parent_text)
                        if val_match:
                            iv_rank = val_match.group(1)
                            break
                except:
                    pass

                page.wait_for_timeout(1000)  # Wait 1s and try again

            if iv_rank:
                return f"Success! The IV Rank for {ticker} is: {iv_rank}"
            else:
                return f"Could not find valid IV Rank for {ticker}. The value remained NaN or the page structure is blocked."

        except Exception as e:
            return f"An error occurred: {str(e)}"
        finally:
            browser.close()


def main():
    # Example usage when running the script directly
    if len(sys.argv) > 1:
        user_ticker = sys.argv[1]
    else:
        user_ticker = input("Enter a stock ticker: ")

    if user_ticker:
        result = get_iv_rank_advanced(user_ticker)
        print(result)


if __name__ == "__main__":
    main()