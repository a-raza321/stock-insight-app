import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import sys
import os
import warnings

# Suppress warnings and stderr globally
warnings.filterwarnings("ignore")
sys.stderr = open(os.devnull, 'w')


def search_company(driver, company_name):
    """Search for company and return the correct URL"""
    try:
        # Go to SimplyWall.St search
        driver.get("https://simplywall.st/")

        # Find and click search box with reduced timeout
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='search-search-field']"))
        )

        # Click and type immediately
        search_box.click()
        search_box.clear()
        search_box.send_keys(company_name)

        # Wait for dropdown with reduced timeout
        time.sleep(2.5)  # Minimum time for dropdown to appear

        # Get ALL suggestions
        try:
            all_suggestions = WebDriverWait(driver, 8).until(
                EC.presence_of_all_elements_located((By.XPATH,
                                                     "//div[contains(@class, 'dropdown') or contains(@class, 'popover') or contains(@class, 'results') or contains(@role, 'listbox')]//a[contains(@href, '/stocks/') and not(contains(@href, 'market-cap'))]"))
            )
        except:
            try:
                all_suggestions = WebDriverWait(driver, 6).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//ul//li//a[contains(@href, '/stocks/') and not(contains(@href, 'market-cap'))]"))
                )
            except:
                all_suggestions = WebDriverWait(driver, 6).until(
                    EC.presence_of_all_elements_located((By.XPATH,
                                                         "//a[contains(@href, '/stocks/') and contains(@href, 'nasdaq') or contains(@href, 'nyse')]"))
                )

        # Find exact match or best match
        company_upper = company_name.upper().strip()
        exact_match = None

        for suggestion in all_suggestions:
            # Check both the text AND the href URL for ticker match
            suggestion_text = suggestion.text.upper().strip()
            suggestion_href = suggestion.get_attribute('href').upper()

            # Method 1: Check if ticker is in the URL (most reliable)
            # URL format: /stocks/us/capital-markets/nasdaq-myo/myomo
            if f"/{company_upper.lower()}/" in suggestion_href.lower():
                exact_match = suggestion
                break

            # Method 2: Check for exact ticker match in text
            # Format could be: "Myomo NYSEAM:MYO" or "MYO" or "NYSEAM:MYO"
            words = suggestion_text.replace(':', ' ').split()
            for word in words:
                if word == company_upper:
                    exact_match = suggestion
                    break

            if exact_match:
                break

        # Click exact match if found, otherwise first suggestion
        target = exact_match if exact_match else all_suggestions[0]
        target.click()

        # Wait for page navigation
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )

        return driver.current_url
    except Exception as e:
        return None


def scrape_risk_rewards(company_name):
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.add_argument('--window-size=1920,1080')
    # Performance optimizations
    options.add_argument('--disable-images')
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-gpu')
    options.page_load_strategy = 'eager'  # Don't wait for all resources

    driver = uc.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    data = {"company": "", "rewards": [], "risks": []}

    try:

        url = search_company(driver, company_name)

        if not url:
            return data


        time.sleep(1)
        driver.execute_script("window.scrollBy(0, 800)")


        try:
            data["company"] = wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            ).text.strip()
        except:
            pass

        # Wait for risk/reward links to appear
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH, "//blockquote//a | //div[contains(@class, 'highlight')]//a"))
            )
        except:
            pass

        # Get all clickable links
        all_links = driver.find_elements(By.XPATH, "//blockquote//a | //div[contains(@class, 'highlight')]//a")

        # RISK KEYWORDS - Highly specific patterns for accurate classification
        risk_keywords = [
            # Dilution (HIGH PRIORITY)
            "shareholders have been substantially diluted",
            "shareholders have been diluted",
            "substantial dilution",
            "share dilution",
            "diluted in the past year",
            "shares outstanding increased",

            # Coverage issues (HIGH PRIORITY)
            "interest payments are not well covered",
            "interest payments are not covered",
            "debt is not well covered",
            "interest coverage",
            "not well covered by earnings",
            "dividend is not well covered",
            "dividend is not covered",
            "payout ratio exceeds",

            # Equity and Balance Sheet
            "negative shareholders equity",
            "negative equity",
            "shareholders equity",

            # Cash runway
            "less than 1 year of cash runway",
            "cash runway",
            "running out of cash",
            "insufficient cash",

            # Debt concerns
            "high debt",
            "significant debt",
            "excessive leverage",
            "debt levels",
            "liabilities exceed",

            # Profitability issues
            "unprofitable",
            "currently unprofitable",
            "not forecast to become profitable",
            "negative earnings",
            "negative income",
            "losses",
            "loss-making",
            "negative cash flow",
            "cash burn",

            # Performance decline
            "revenue declined",
            "earnings declined",
            "falling revenue",
            "falling earnings",
            "decreased significantly",

            # Volatility
            "volatile",
            "highly volatile",
            "volatile share price",
            "unstable",
            "significant fluctuations",
            "earnings volatility",

            # Insider activity (HIGH PRIORITY)
            "significant insider selling",
            "insider selling",
            "insiders sold",
            "directors sold",

            # Earnings quality
            "high level of non-cash earnings",
            "non-cash earnings",
            "earnings quality",
            "unusual items",

            # General risks
            "concerning",
            "worrying",
            "risk",
            "warning"
        ]

        # REWARD KEYWORDS - Positive indicators
        reward_keywords = [
            # Valuation (HIGH PRIORITY)
            "below our estimate of its fair value",
            "trading at a discount",
            "below estimate",
            "undervalued",
            "attractive valuation",
            "good value compared to peers",
            "trading at good value",
            "cheap compared to",

            # Growth (HIGH PRIORITY) - but exclude if negative context
            "earnings are forecast to grow",
            "revenue is forecast to grow",
            "expected to grow",
            "growth forecast",
            "analysts expect growth",
            "analysts in good agreement",
            "stock price will rise",
            "analysts predict",
            "price target",

            # Financial strength
            "strong balance sheet",
            "healthy balance sheet",
            "low debt levels",
            "debt free",

            # Profitability
            "high profit margins",
            "improving margins",
            "earnings growth",
            "became profitable",
            "turning profitable",

            # Cash flow
            "strong cash flow",
            "positive cash flow",
            "generating cash",

            # Dividends (only positive)
            "dividend is well covered",
            "healthy payout ratio",
            "sustainable dividend",
            "dividend growth",

            # Performance
            "outperforming",
            "beat expectations",
            "exceeded estimates",
            "strong performance",

            # Market position
            "market leader",
            "competitive advantage",
            "market share gains"
        ]

        for link in all_links:
            text = link.text.strip()
            if not text or len(text) < 10:
                continue

            text_lower = text.lower()

            # CRITICAL: Check for specific risk patterns FIRST with exact matching
            is_risk = False
            is_reward = False

            # Priority risk patterns - exact phrase matching
            high_priority_risks = [
                "shareholders have been substantially diluted",
                "shareholders have been diluted",
                "diluted in the past year",
                "interest payments are not well covered",
                "interest payments are not covered",
                "negative shareholders equity",
                "less than 1 year of cash runway",
                "significant insider selling",
                "currently unprofitable",
                "not forecast to become profitable",
                "highly volatile share price",
                "high level of non-cash earnings"
            ]

            # Check if it contains dividend + not covered (risk)
            if "dividend" in text_lower and "not well covered" in text_lower:
                is_risk = True
            # Check for unprofitable patterns FIRST (highest priority - even if contains "forecast")
            elif "unprofitable" in text_lower:
                is_risk = True
            elif "not forecast to become profitable" in text_lower:
                is_risk = True
            # Check high priority risk patterns
            elif any(pattern in text_lower for pattern in high_priority_risks):
                is_risk = True

            # If not identified as risk, check for rewards
            if not is_risk:
                # Priority reward patterns - exact phrase matching
                high_priority_rewards = [
                    "below our estimate of its fair value",
                    "earnings are forecast to grow",
                    "revenue is forecast to grow",
                    "trading at good value compared to",
                    "good value compared to peers",
                    "analysts in good agreement that stock price will rise"
                ]

                if any(pattern in text_lower for pattern in high_priority_rewards):
                    is_reward = True
                # Fallback to general reward keywords
                elif any(keyword in text_lower for keyword in reward_keywords):
                    # CRITICAL: Make sure it's not actually a risk - check for negative context
                    negative_context = [
                        "not well covered", "not covered", "diluted", "volatile",
                        "declined", "falling", "unprofitable", "not forecast to become profitable",
                        "loss", "negative", "concerning", "risk"
                    ]
                    if not any(neg_word in text_lower for neg_word in negative_context):
                        is_reward = True

            # Final fallback to general risk keywords if still not classified
            if not is_risk and not is_reward:
                if any(keyword in text_lower for keyword in risk_keywords):
                    is_risk = True

            # Add to appropriate list
            if is_risk:
                if text not in data["risks"]:
                    data["risks"].append(text)
            elif is_reward:
                if text not in data["rewards"]:
                    data["rewards"].append(text)

    finally:
        # Clean exit
        try:
            driver.quit()
        except:
            pass
        try:
            driver.service.stop()
        except:
            pass

    return data