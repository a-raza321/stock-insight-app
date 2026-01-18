import requests
from bs4 import BeautifulSoup
import re

def clean_filename(text):
    """Clean the company name for formatting purposes."""
    text = text.split("\n")[0]
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = text.replace(" ", "_")
    return text

def interpret_insider_activity(value):
    """
    Convert Insider Trans % into Buying / Selling signal.
    """
    if value == "N/A":
        return "N/A"

    try:
        # Remove percentage sign and convert to float
        percent = float(value.replace("%", ""))
        if percent > 0:
            return "Net Insider Buying"
        elif percent < 0:
            return "Net Insider Selling"
        else:
            return "Neutral"
    except (ValueError, AttributeError):
        return "N/A"

def scrape_finviz(ticker):
    """
    Scrapes stock data from Finviz and returns the results as a dictionary.
    """
    ticker = ticker.upper()
    url = f"https://finviz.com/quote.ashx?t={ticker}"

    # Headers are necessary as Finviz blocks default python-requests user agents
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"error": f"Failed to fetch Finviz page (Status Code: {response.status_code})"}
    except Exception as e:
        return {"error": f"An error occurred during the request: {e}"}

    soup = BeautifulSoup(response.text, "html.parser")
    # The 'snapshot-table2' contains the key financial metrics
    table = soup.find("table", class_="snapshot-table2")

    if not table:
        return {"error": "Finviz data table not found. Invalid ticker or layout change."}

    # Parse table data into a dictionary
    finviz_data = {}
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        for i in range(0, len(cols), 2):
            key = cols[i].text.strip()
            value = cols[i + 1].text.strip()
            finviz_data[key] = value

    # Extract specific metrics
    insider_trans = finviz_data.get("Insider Trans", "N/A")
    insider_activity = interpret_insider_activity(insider_trans)
    company_name = finviz_data.get("Company", "N/A").split("\n")[0]

    extracted_data = {
        "Ticker": ticker,
        "Company": company_name,
        "Net Insider Buying vs Selling (%)": insider_trans,
        "Net Insider Activity": insider_activity,
        "Institutional Ownership (%)": finviz_data.get("Inst Own", "N/A"),
        "Short Float (%)": finviz_data.get("Short Float", "N/A")
    }

    return extracted_data