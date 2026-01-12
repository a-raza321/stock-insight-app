import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import numpy as np
from bs4 import BeautifulSoup
import warnings
import time
from datetime import datetime
import re
import json

warnings.filterwarnings("ignore")

# Configuration
API_KEY = ""
MODEL_NAME = "gemini-2.5-flash-preview-09-2025"

st.set_page_config(
    page_title="Stock Insight Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS maintained as per requirement
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
    [data-testid="stMetricValue"] { color: #1e1e1e !important; }
    [data-testid="stMetricLabel"] { color: #555555 !important; }
    .stMarkdown, p, span, h1, h2, h3 { color: #1e1e1e !important; }
    hr { border: 0.5px solid #eeeeee !important; }
    .report-card { background-color: #f8f9fa; padding: 20px; border-radius: 12px; border: 1px solid #e9ecef; margin-bottom: 20px; white-space: pre-wrap; }
    </style>
""", unsafe_allow_html=True)

# Enhanced session management for Streamlit Cloud
if 'session' not in st.session_state:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://finance.yahoo.com",
        "Referer": "https://finance.yahoo.com/",
        "DNT": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    })
    # Initial hit to get cookies
    try:
        session.get("https://finance.yahoo.com", timeout=10)
    except:
        pass
    st.session_state.session = session

def format_ticker(ticker):
    return ticker.strip().upper()

def format_large_number(val, is_currency=True):
    if not isinstance(val, (int, float)): return val
    try:
        abs_val = abs(val)
        prefix = "$" if is_currency else ""
        if abs_val >= 1_000_000_000_000:
            return f"{prefix}{val / 1_000_000_000_000:.3f}T"
        elif abs_val >= 1_000_000_000:
            return f"{prefix}{val / 1_000_000_000:.2f}B"
        elif abs_val >= 1_000_000:
            return f"{prefix}{val / 1_000_000:.2f}M"
        return f"{prefix}{val:,.2f}" if is_currency else f"{val:,.0f}"
    except:
        return val

def get_insider_sentiment(val_str):
    if val_str in ["N/A", "-", ""]: return "N/A"
    try:
        val = float(val_str.replace("%", "").replace(",", ""))
        if val > 0: return "Net Buying"
        if val < 0: return "Net Selling"
        return "Neutral"
    except:
        return "N/A"

def scrape_yahoo_insider_stat(ticker):
    """
    CLOUD-OPTIMIZED Direct HTML Scraper for Yahoo Finance Insider Ownership.
    Bypasses blocks by rotating logic and handling Streamlit Cloud session states.
    """
    insider_pct = "N/A"
    urls = [
        f"https://finance.yahoo.com/quote/{ticker}/key-statistics",
        f"https://finance.yahoo.com/quote/{ticker}/holders"
    ]

    for url in urls:
        try:
            # Small delay to prevent burst triggers on shared IPs
            time.sleep(0.5)
            resp = st.session_state.session.get(url, timeout=12)
            
            # If 404, the ticker might be unique or Yahoo changed structure
            if resp.status_code != 200: continue
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 1. SEARCH VIA JSON METADATA (Hidden Store)
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'root.App.main' in script.string:
                    try:
                        # Extract the JSON block from the script
                        match = re.search(r'root\.App\.main\s*=\s*(\{.*?\});', script.string)
                        if match:
                            data = json.loads(match.group(1))
                            stores = data.get('context', {}).get('dispatcher', {}).get('stores', {})
                            quote_summary = stores.get('QuoteSummaryStore', {})
                            
                            # Multiple paths for reliability
                            targets = [
                                quote_summary.get('majorHoldersBreakdown', {}).get('heldPercentInsiders', {}).get('fmt'),
                                quote_summary.get('defaultKeyStatistics', {}).get('heldPercentInsiders', {}).get('fmt')
                            ]
                            for t in targets:
                                if t: return t
                    except:
                        continue

            # 2. SEARCH VIA TABLE ROWS
            # Standard tables
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    row_text = row.get_text().lower()
                    if "held by insiders" in row_text:
                        tds = row.find_all("td")
                        if len(tds) >= 2:
                            val = tds[1].get_text(strip=True)
                            if "%" in val: return val
            
            # 3. FALLBACK: REGEX ON BODY
            match = re.search(r'Held by Insiders.*?(\d+\.\d+%)', soup.get_text(), re.IGNORECASE | re.DOTALL)
            if match: return match.group(1)

        except Exception:
            continue
            
    return insider_pct

def scrape_finviz_comprehensive(ticker):
    """
    Scrapes the Finviz snapshot table for metrics previously required.
    """
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    results = []
    # Finviz needs strict headers
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200: return results
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="snapshot-table2")
        if not table: return results
        
        data_map = {}
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            for i in range(0, len(cols), 2):
                key = cols[i].text.strip()
                val = cols[i+1].text.strip()
                if key:
                    data_map[key] = val
        
        metrics_to_pick = {
            "Insider Trans": "Net Insider Buying vs Selling %",
            "Inst Own": "Institutional Ownership %",
            "Short Float": "Short Float %",
            "Insider Own": "Insider Ownership %"
        }

        for f_key, display_name in metrics_to_pick.items():
            if f_key in data_map:
                results.append({"Metric Name": display_name, "Source": "Finviz", "Value": data_map[f_key]})
                if f_key == "Insider Trans":
                    results.append({"Metric Name": "Net Insider Activity", "Source": "Finviz", "Value": get_insider_sentiment(data_map[f_key])})
    except:
        pass
    return results

def fetch_yfinance_comprehensive(ticker):
    """
    Fetches core metrics with specific focus on fixing Shares Outstanding and 
    Insider Ownership via aggressive fallbacks.
    """
    all_rows = []
    
    # HIGHEST PRIORITY: Scrape Insider Ownership first via the new multi-layered method
    ins_val = scrape_yahoo_insider_stat(ticker)
    
    try:
        stock = yf.Ticker(ticker)
        
        # 1. ATTEMPT INFO
        info = {}
        try:
            info = stock.info
            if not info or len(info) < 5: info = {}
        except:
            info = {}

        # 2. PRICE & MARKET CAP
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not current_price:
            try: current_price = stock.fast_info.get('last_price') or stock.fast_info.get('lastPrice')
            except: current_price = None

        m_cap = info.get('marketCap')
        if not m_cap:
            try: m_cap = stock.fast_info.get('market_cap') or stock.fast_info.get('marketCap')
            except: m_cap = None

        # 3. SHARES OUTSTANDING
        shares = info.get('sharesOutstanding')
        if not shares:
            try: shares = stock.fast_info.get('shares_outstanding') or stock.fast_info.get('sharesOutstanding')
            except: shares = None
        
        if not shares and m_cap and current_price:
            try: shares = float(m_cap) / float(current_price)
            except: shares = "N/A"

        # 4. INSIDER OWNERSHIP % (Final check if scraping didn't find it but info did)
        if ins_val == "N/A":
            raw_ins = info.get('heldPercentInsiders') or info.get('held_percent_insiders')
            if raw_ins and raw_ins != 'N/A' and isinstance(raw_ins, (int, float)):
                ins_val = f"{float(raw_ins) * 100:.2f}%"

        # Build basic metrics table
        high_52 = info.get('fiftyTwoWeekHigh') or stock.fast_info.get('yearHigh') or 'N/A'
        low_52 = info.get('fiftyTwoWeekLow') or stock.fast_info.get('yearLow') or 'N/A'

        basic_metrics = [
            ("Company Name", info.get('longName', ticker), False),
            ("Current Stock Price", current_price if current_price else "N/A", True),
            ("Market Cap", m_cap if m_cap else "N/A", True),
            ("Shares Outstanding", shares if shares else "N/A", False),
            ("52 Week High", high_52, True),
            ("52 Week Low", low_52, True)
        ]
        
        for name, val, is_curr in basic_metrics:
            all_rows.append({"Metric Name": name, "Source": "Yahoo Finance", "Value": format_large_number(val, is_currency=is_curr)})

        # Crucial Requirement: Maintain source as "Yahoo Finance"
        all_rows.append({"Metric Name": "Total Insider Ownership %", "Source": "Yahoo Finance", "Value": ins_val})

        # Financial Statements
        q_bs = stock.quarterly_balance_sheet
        q_cf = stock.quarterly_cashflow
        
        if not q_bs.empty:
            bs = q_bs.iloc[:, 0]
            total_assets = bs.get('Total Assets', 0)
            total_liabilities = bs.get('Total Liabilities Net Minority Interest', bs.get('Total Liabilities', 0))
            cash = bs.get('Cash And Cash Equivalents', bs.get('Cash Cash Equivalents And Short Term Investments', 0))
            
            all_rows.append({"Metric Name": "Total Assets", "Source": "Yahoo Finance", "Value": format_large_number(float(total_assets), True)})
            all_rows.append({"Metric Name": "Total Liabilities", "Source": "Yahoo Finance", "Value": format_large_number(float(total_liabilities), True)})

            if total_liabilities and float(total_liabilities) != 0:
                al_ratio = round(float(total_assets) / float(total_liabilities), 2)
                all_rows.append({"Metric Name": "Assets / Liabilities Ratio", "Source": "Derived", "Value": al_ratio})

            all_rows.append({"Metric Name": "Cash & Cash Equivalents (Latest Quarter)", "Source": "Yahoo Finance", "Value": format_large_number(float(cash), True)})

        if not q_cf.empty:
            op_cash = 0
            for key in ['Total Cash From Operating Activities', 'Operating Cash Flow', 'Cash Flow From Continuing Operating Activities']:
                if key in q_cf.index:
                    op_cash = q_cf.loc[key].iloc[0]
                    break
            
            if op_cash < 0 and not q_bs.empty:
                current_cash = bs.get('Cash And Cash Equivalents', bs.get('Cash Cash Equivalents And Short Term Investments', 0))
                monthly_burn = abs(float(op_cash)) / 3
                runway = round(float(current_cash) / monthly_burn, 1) if monthly_burn > 0 else 0
                all_rows.append({"Metric Name": "Runway", "Source": "Derived", "Value": f"{runway} months"})
            elif op_cash > 0:
                all_rows.append({"Metric Name": "Runway", "Source": "Derived", "Value": "Cash flow positive"})

    except Exception as e:
        if "Too Many Requests" in str(e) or "429" in str(e):
            st.warning("Yahoo Finance Rate Limit Detected: Falling back to scraping methods for basic metrics.")
        else:
            if not any(row['Metric Name'] == "Total Insider Ownership %" for row in all_rows):
                all_rows.append({"Metric Name": "Total Insider Ownership %", "Source": "Yahoo Finance", "Value": ins_val})
    return all_rows

def main():
    if 'report_data' not in st.session_state: st.session_state.report_data = None

    if st.session_state.report_data is None:
        st.markdown(
            '<div class="main-header"><h1>Stock Insight Pro</h1><p>Institutional-Grade Stock Analysis</p></div>',
            unsafe_allow_html=True)
        
        _, center_col, _ = st.columns([1, 1.5, 1])
        with center_col:
            ticker_input = st.text_input("Ticker", placeholder="e.g. TSLA, NVDA", key="ticker_box", label_visibility="collapsed")
            if st.button("Generate Comprehensive Report") and ticker_input:
                ticker = format_ticker(ticker_input)
                status_text = st.empty()
                status_text.info(f"Gathering data for {ticker}...")
                
                try:
                    yf_data = fetch_yfinance_comprehensive(ticker)
                    fv_data = scrape_finviz_comprehensive(ticker)
                    
                    st.session_state.report_data = yf_data + fv_data
                    st.session_state.current_ticker = ticker
                    status_text.empty()
                    st.rerun()
                except Exception as e:
                    status_text.error(f"Analysis failed: {e}")
    else:
        col_title, col_reset = st.columns([8, 2])
        col_title.title(f"📊 {st.session_state.current_ticker} Comprehensive Report")
        if col_reset.button("New Analysis"):
            st.session_state.report_data = None
            st.rerun()

        st.subheader("Consolidated Market Data (Yahoo Finance & Finviz)")
        if st.session_state.report_data:
            df = pd.DataFrame(st.session_state.report_data)
            df['Value'] = df['Value'].astype(str)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No metric data found.")

if __name__ == "__main__":
    main()
