import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import sys
import os
import warnings
import requests
import tempfile

print("hello")

warnings.filterwarnings("ignore")
sys.stderr = open(os.devnull, 'w')


def search_company(driver, company_name):
    """Search for company and return the correct URL"""
    try:
        driver.get("https://simplywall.st/")

        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='search-search-field']"))
        )

        search_box.click()
        search_box.clear()
        search_box.send_keys(company_name)

        time.sleep(2.5)

        try:
            first_suggestion = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH,
                                            "//div[contains(@class, 'dropdown') or contains(@class, 'popover') or contains(@class, 'results') or contains(@role, 'listbox')]//a[contains(@href, '/stocks/') and not(contains(@href, 'market-cap'))][1]"))
            )
        except:
            try:
                first_suggestion = WebDriverWait(driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH,
                                                "//ul//li//a[contains(@href, '/stocks/') and not(contains(@href, 'market-cap'))][1]"))
                )
            except:
                first_suggestion = WebDriverWait(driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH,
                                                "//a[contains(@href, '/stocks/') and contains(@href, 'nasdaq') or contains(@href, 'nyse')][1]"))
                )

        first_suggestion.click()

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )

        return driver.current_url
    except Exception as e:
        return None


def scrape_risk_rewards_sws(company_name):
    def create_options():
        """Helper to create a fresh options object for every driver attempt"""
        options = uc.ChromeOptions()
        # REQUIRED CLOUD SETTINGS
        options.add_argument('--headless=new')  # Essential for Streamlit Cloud
        options.add_argument('--no-sandbox')    # Essential for Linux/Container environments
        options.add_argument('--disable-dev-shm-usage') # Prevents crashes due to limited memory in /dev/shm
        options.add_argument('--disable-gpu')   # Recommended for headless mode
        
        # ANTI-BOT SETTINGS
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        options.add_argument('--window-size=1920,1080')

        options.add_argument('--disable-images')
        options.add_argument('--blink-settings=imagesEnabled=false')
        options.add_argument('--disable-extensions')
        options.page_load_strategy = 'eager'

        # Streamlit Cloud workaround: Use temporary directory for user data
        tmp_dir = tempfile.mkdtemp()
        options.add_argument(f"--user-data-dir={tmp_dir}")
        return options

    # Detect Chromium binary for Streamlit Cloud
    chrome_path = None
    possible_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/lib/chromium-browser/chromium-browser"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            chrome_path = path
            break

    try:
        # Initialize driver with a fresh options object
        driver = uc.Chrome(
            options=create_options(),
            browser_executable_path=chrome_path,
            use_subprocess=True,
            headless=True
        )
    except Exception as e:
        # Fallback: Initialize driver with another fresh options object if the first attempt fails
        # This avoids the RuntimeError: you cannot reuse the ChromeOptions object
        driver = uc.Chrome(options=create_options(), headless=True)

    wait = WebDriverWait(driver, 15)
    data = {"company": "", "rewards": [], "risks": []}

    try:
        url = search_company(driver, company_name)

        if not url:
            sys.stdout.write(f"\nCould not find company: {company_name}\n")
            sys.stdout.flush()
            return data

        time.sleep(1)
        driver.execute_script("window.scrollBy(0, 800)")

        try:
            data["company"] = wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            ).text.strip()
        except:
            pass

        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH, "//blockquote//a | //div[contains(@class, 'highlight')]//a"))
            )
        except:
            pass

        all_links = driver.find_elements(By.XPATH, "//blockquote//a | //div[contains(@class, 'highlight')]//a")

        risk_keywords = [
            "debt", "leverage", "liabilities", "borrowing", "owe",
            "unprofitable", "loss", "losses", "negative earnings", "negative income",
            "negative cash", "burn rate", "cash burn", "non-cash earnings",
            "volatile", "volatility", "unstable", "fluctuat", "swing",
            "dilut", "shares issued", "share count increased",
            "insider selling", "insiders sold", "directors sold", "insider",
            "decline", "declining", "decreased", "fell", "dropped", "falling",
            "underperform", "miss", "below expectation",
            "one-off", "unusual items", "non-recurring", "impacting financial",
            "restatement", "writedown", "impairment", "non-cash",
            "lawsuit", "litigation", "investigation", "regulatory",
            "competition", "market share loss",
            "risk", "concern", "warning", "challenge", "pressure", "threat",
            "weakness", "problem", "issue", "difficulty"
        ]

        reward_keywords = [
            "growth", "grew", "growing", "grow", "increase", "increased", "increasing",
            "expansion", "expand",
            "earnings", "profit", "profitable", "became profitable", "margin",
            "revenue", "sales",
            "forecast", "expect", "projected", "estimate", "analysts",
            "guidance", "outlook",
            "undervalued", "good value", "fair value", "trading below",
            "discount", "attractive", "cheap", "bargain",
            "outperform", "beat", "exceeded", "surpass", "strong",
            "robust", "solid", "positive", "improving", "recovered",
            "dividend", "yield", "buyback", "shareholder return",
            "market leader", "competitive advantage", "market share gain",
            "innovation", "new product",
            "compared to peers", "better than", "above average", "leading"
        ]

        for link in all_links:
            text = link.text.strip()
            if not text or len(text) < 10:
                continue

            text_lower = text.lower()
            is_risk = any(keyword in text_lower for keyword in risk_keywords)
            is_reward = any(keyword in text_lower for keyword in reward_keywords)

            if is_risk:
                if text not in data["risks"]:
                    data["risks"].append(text)
            elif is_reward:
                if text not in data["rewards"]:
                    data["rewards"].append(text)

    finally:
        try:
            driver.quit()
        except:
            pass

    sys.stdout.write(f"\nCompany: {data['company']}\n\n")
    sys.stdout.write("Rewards:\n")
    if data["rewards"]:
        for r in data["rewards"]:
            sys.stdout.write(f"- {r}\n")
    else:
        sys.stdout.write("- No rewards found\n")

    sys.stdout.write("\nRisks:\n")
    if data["risks"]:
        for r in data["risks"]:
            sys.stdout.write(f"- {r}\n")
    else:
        sys.stdout.write("- No risks found\n")

    sys.stdout.flush()
    return data


def get_gemini_analysis(data):
    """Analyses the scraped risks and rewards using Gemini API"""
    api_key = "" # Execution environment provides this at runtime
    model = "gemini-2.5-flash-preview-09-2025"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    rewards_txt = "\n".join(data['rewards']) if data['rewards'] else "No specific rewards identified."
    risks_txt = "\n".join(data['risks']) if data['risks'] else "No specific risks identified."

    prompt = f"""
    Analyse the following scraped financial rewards and risks for {data['company']}.

    Rewards Found:
    {rewards_txt}

    Risks Found:
    {risks_txt}

    Generate a risk/reward summary in bullet points. 
    Each bullet point must be less than 15 words.
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    for delay in [1, 2, 4, 8, 16]:
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                analysis = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'N/A')
                return analysis
        except:
            pass
        time.sleep(delay)

    return "Failed to generate analysis summary after multiple attempts."


if __name__ == "__main__":
    sys.stderr.close()
    sys.stderr = sys.__stderr__

    company_name = input("Enter company name (e.g., Apple, Tesla, NVIDIA, Microsoft): ").strip()
    sys.stderr = open(os.devnull, 'w')

    scraped_data = scrape_risk_rewards_sws(company_name)

    if scraped_data.get("company"):
        sys.stdout.write("\n" + "=" * 30 + "\n")
        sys.stdout.write("GEMINI RISK/REWARD SUMMARY\n")
        sys.stdout.write("=" * 30 + "\n")
        analysis_summary = get_gemini_analysis(scraped_data)
        sys.stdout.write(analysis_summary + "\n")
        sys.stdout.flush()
