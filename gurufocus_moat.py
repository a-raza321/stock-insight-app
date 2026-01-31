import os
import re
import time
import random
import subprocess
from playwright.sync_api import sync_playwright
from google.cloud import bigquery
from google.oauth2 import service_account
import streamlit as st
import requests
PROXY_HOST = "gw.dataimpulse.com"
PROXY_PORT = "823"
PROXY_USER = st.secrets["PROXY_USER"]
PROXY_PASS = st.secrets["PROXY_PASS"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]


def get_moat_score(ticker: str):

    ticker = ticker.upper().strip()
    result = "N/A"

    # --- TIER 1: DATABASE CHECK ---
    print(f"[INFO] TIER 1: Querying BigQuery for {ticker}...")
    try:

        SERVICE_ACCOUNT_JSON = dict(st.secrets["SERVICE_ACCOUNT_JSON"])
        TABLE_ID = st.secrets["TABLE_ID"]
        if "private_key" in SERVICE_ACCOUNT_JSON:
            SERVICE_ACCOUNT_JSON["private_key"] = SERVICE_ACCOUNT_JSON["private_key"].replace("\\n", "\n")
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as temp_key_file:
            json.dump(SERVICE_ACCOUNT_JSON, temp_key_file)
            temp_key_path = temp_key_file.name

        credentials = service_account.Credentials.from_service_account_file(temp_key_path)
        client = bigquery.Client(credentials=credentials, project=SERVICE_ACCOUNT_JSON["project_id"])

        
        
        # Initialize BigQuery Client
        # credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON)
        # client = bigquery.Client(credentials=credentials, project=credentials.project_id)

        # SQL Query for BigQuery
        query = f"""
                SELECT moat_number 
                FROM `{TABLE_ID}` 
                WHERE UPPER(ticker) = @ticker
            """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticker", "STRING", ticker)
            ]
        )

        query_job = client.query(query, job_config=job_config)
        results = query_job.result()

        # Check for results
        for row in results:
            if row.moat_number is not None:
                result = str(row.moat_number)
                print(f"[SUCCESS] Moat Score found in BigQuery for {ticker}: {result}")
                return result

    except Exception as e:
        print(f"[ERROR] BigQuery access failed: {e}")

    print(f"[INFO] Ticker {ticker} not found in database. Escalating to Tier 2 (Scraping)...")

    # --- TIER 2: PLAYWRIGHT SCRAPING ---
    url = f"https://www.gurufocus.com/stock/{ticker}/summary"
    proxy_server = f"http://gw.dataimpulse.com:823"
    max_retries = 1

    for attempt in range(1, max_retries + 1):
        ua = random.choice(USER_AGENTS)
        print(f"[INFO] TIER 2: Scraping attempt {attempt}/{max_retries} for {ticker}...")

        with sync_playwright() as p:
            browser = None
            try:
                launch_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                try:
                    browser = p.chromium.launch(
    headless=True,
    proxy={
        "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
        "username": PROXY_USER,
        "password": PROXY_PASS
    },
    args=launch_args
)
                except Exception as e:
                    if "executable doesn't exist" in str(e).lower():
                        print("[INFO] Installing Playwright Chromium dependencies...")
                        subprocess.run(["playwright", "install", "chromium"], check=True)
                        browser = p.chromium.launch(headless=True, proxy={"server": proxy_server}, args=launch_args)
                    else:
                        raise e

                context = browser.new_context(user_agent=ua, viewport={'width': 1920, 'height': 1080})
                page = context.new_page()

                response = page.goto(url, wait_until="load", timeout=60000)
                if response and response.status < 400:
                    # Allow dynamic content to load
                    page.wait_for_timeout(5000)

                    # Search specifically for the Moat Score table row
                    row = page.locator("tr").filter(has_text=re.compile(r"Moat Score", re.IGNORECASE)).first
                    raw_val = row.inner_text() if row.count() > 0 else page.content()

                    digit_match = re.search(r"Moat Score.*?(\d+)", raw_val, re.IGNORECASE | re.DOTALL)
                    if not digit_match and row.count() > 0:
                        digit_match = re.search(r"(\d+)", raw_val)

                    if digit_match:
                        result = digit_match.group(1)
                        print(f"[SUCCESS] Obtained score via scraping for {ticker}: {result}")
                        browser.close()
                        return result
                else:
                    status = response.status if response else "No Response"
                    print(f"[WARN] Page load issues (Status: {status}).")

                browser.close()
            except Exception as e:
                print(f"[ERROR] Playwright failure on attempt {attempt}: {e}")
                if browser:
                    browser.close()


        time.sleep(2)

    print(f"[INFO] Scraping failed for {ticker}. Escalating to Tier 3 (Gemini LLM)...")

    # --- TIER 3: GEMINI LLM WITH SEARCH ---
    print(f"[INFO] TIER 3: Initiating Gemini Search-Grounding for {ticker}...")
    system_prompt = (
        "You are a financial data extraction agent. You must search GuruFocus to find the 'Moat Score'. "
        "Strictly retrieve the score from GuruFocus. Return ONLY the integer value. "
        "If multiple values are found, return the most recent summary score. If not found, return 'N/A'."
    )
    user_query = f"What is the current GuruFocus Moat Score for the ticker {ticker}?"
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "tools": [{"google_search": {}}]
    }


    for i in range(5):
        try:
            resp = requests.post(api_url, json=payload, timeout=30)
            if resp.status_code == 200:
                resp_json = resp.json()
                text = resp_json.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'N/A')

                # Extract digits from LLM response
                match = re.search(r"(\d+)", text)
                if match:
                    result = match.group(1)
                    print(f"[SUCCESS] This value is get by gemini for {ticker}: {result}")
                    return result
                break
            elif resp.status_code == 429:
                print(f"[WARN] Gemini API Rate Limited. Backing off...")
                time.sleep(2 ** i)
            else:
                print(f"[ERROR] Gemini API returned status {resp.status_code}")
                break
        except Exception as api_err:
            print(f"[ERROR] API request error: {api_err}")
            time.sleep(2 ** i)

    print(f"[FINAL] All methods exhausted for {ticker}. Returning N/A.")
    return "N/A"


if __name__ == "__main__":

    ticker_to_test = "meta"
    # final_score = get_moat_score(ticker_to_test)
    # print(f"\n[Final Output] {ticker_to_test}: {final_score}")


