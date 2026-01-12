import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import warnings
import time
import re
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")

st.set_page_config(page_title="Stock Insight Pro", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS
st.markdown("""
    <style>
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: #ffffff; }
    .block-container { padding-top: 1rem !important; max-width: 1200px; }
    .main-header { text-align: center; margin-bottom: 2rem; color: #1e1e1e; }
    .stTextInput > div > div > input { color: #1e1e1e !important; background-color: #ffffff !important; }
    .stButton > button { color: #ffffff !important; background-color: #007bff !important; width: 100%; border-radius: 8px; font-weight: bold; }
    .stMarkdown, p, span, h1, h2, h3 { color: #1e1e1e !important; }
    </style>
""", unsafe_allow_html=True)

# Session management for cloud deployment
if 'session' not in st.session_state:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
    try: session.get("https://finance.yahoo.com", timeout=5)
    except: pass
    st.session_state.session = session

def scrape_yahoo_insider(ticker):
    """Robust scraper for Insider Ownership %"""
    urls = [f"https://finance.yahoo.com/quote/{ticker}/key-statistics", f"https://finance.yahoo.com/quote/{ticker}/holders"]
    for url in urls:
        try:
            time.sleep(1)
            resp = st.session_state.session.get(url, timeout=10)
            if resp.status_code != 200: continue
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Method 1: JSON Store
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'root.App.main' in script.string:
                    match = re.search(r'root\.App\.main\s*=\s*(\{.*?\});', script.string)
                    if match:
                        data = json.loads(match.group(1))
                        stores = data.get('context', {}).get('dispatcher', {}).get('stores', {}).get('QuoteSummaryStore', {})
                        val = stores.get('majorHoldersBreakdown', {}).get('heldPercentInsiders', {}).get('fmt') or \
                              stores.get('defaultKeyStatistics', {}).get('heldPercentInsiders', {}).get('fmt')
                        if val: return val
            
            # Method 2: Table Search
            for row in soup.find_all("tr"):
                if "held by insiders" in row.get_text().lower():
                    tds = row.find_all("td")
                    if len(tds) >= 2 and "%" in tds[1].text: return tds[1].text.strip()
        except: continue
    return "N/A"

def fetch_data(ticker_input):
    ticker = ticker_input.strip().upper()
    rows = []
    
    # 1. Yahoo Finance Data (Ticker, Price, Insider %)
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info.get('last_price') or stock.info.get('currentPrice', 'N/A')
        insider = scrape_yahoo_insider(ticker)
        if insider == "N/A":
            raw = stock.info.get('heldPercentInsiders')
            if isinstance(raw, (int, float)): insider = f"{raw*100:.2f}%"
        
        rows.append({"Metric Name": "Ticker", "Source": "Yahoo Finance", "Value": ticker})
        rows.append({"Metric Name": "Current Stock Price", "Source": "Yahoo Finance", "Value": f"${price:,.2f}" if isinstance(price, (int, float)) else price})
        rows.append({"Metric Name": "Total Insider Ownership %", "Source": "Yahoo Finance", "Value": insider})
    except Exception as e:
        logger.error(f"Yahoo error: {e}")

    # 2. Finviz Data (Keep as is)
    try:
        fv_url = f"https://finviz.com/quote.ashx?t={ticker}"
        resp = requests.get(fv_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", class_="snapshot-table2")
            if table:
                data_map = {}
                for tr in table.find_all("tr"):
                    tds = tr.find_all("td")
                    for i in range(0, len(tds), 2):
                        data_map[tds[i].text.strip()] = tds[i+1].text.strip()
                
                picks = {"Insider Trans": "Net Insider Buying vs Selling %", "Inst Own": "Institutional Ownership %", 
                         "Short Float": "Short Float %", "Insider Own": "Insider Ownership %"}
                for k, v in picks.items():
                    if k in data_map:
                        rows.append({"Metric Name": v, "Source": "Finviz", "Value": data_map[k]})
    except Exception as e:
        logger.error(f"Finviz error: {e}")
        
    return rows

def main():
    if 'report_data' not in st.session_state: st.session_state.report_data = None

    if st.session_state.report_data is None:
        st.markdown('<div class="main-header"><h1>Stock Insight Pro</h1><p>Streamlined Insider & Market Analysis</p></div>', unsafe_allow_html=True)
        _, center_col, _ = st.columns([1, 1.5, 1])
        with center_col:
            ticker_input = st.text_input("Ticker", placeholder="e.g. TSLA", key="ticker_box", label_visibility="collapsed")
            if st.button("Generate Report") and ticker_input:
                with st.spinner(f"Fetching data for {ticker_input.upper()}..."):
                    st.session_state.report_data = fetch_data(ticker_input)
                    st.session_state.current_ticker = ticker_input.upper()
                    st.rerun()
    else:
        col_title, col_reset = st.columns([8, 2])
        col_title.title(f"📊 {st.session_state.current_ticker} Report")
        if col_reset.button("New Analysis"):
            st.session_state.report_data = None
            st.rerun()

        df = pd.DataFrame(st.session_state.report_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
