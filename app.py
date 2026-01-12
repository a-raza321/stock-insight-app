import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import datetime
import time
import random

# --- Page Configuration ---
st.set_page_config(page_title="CEO Value Analysis", layout="centered")

# Custom CSS for high contrast and styling
st.markdown("""
    <style>
    .main {
        background-color: #FFFFFF;
    }
    h1 {
        color: #000000;
        text-align: center;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 800;
    }
    .stButton>button {
        width: 100%;
        background-color: #000000;
        color: #FFFFFF;
        border-radius: 5px;
        height: 3em;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #333333;
        color: #FFFFFF;
    }
    /* Simple black table styling */
    table {
        color: black;
        border-collapse: collapse;
        width: 100%;
    }
    th {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        text-align: left !important;
    }
    </style>
    """, unsafe_allow_html=True)

def get_finviz_data(ticker):
    """Scrapes data from Finviz snapshot table."""
    try:
        url = f"https://finviz.com/quote.ashx?t={ticker.upper()}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Finviz stores data in a table with class 'snapshot-table2'
        table = soup.find('table', class_='snapshot-table2')
        if not table:
            return None
        
        rows = table.find_all('tr')
        data = {}
        for row in rows:
            cols = row.find_all('td')
            for i in range(0, len(cols), 2):
                label = cols[i].text.strip()
                value = cols[i+1].text.strip()
                data[label] = value
        
        return data
    except Exception:
        return None

def fetch_yf_data_with_retry(ticker, max_retries=5):
    """Fetches yfinance data with exponential backoff and custom session."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    })
    
    for attempt in range(max_retries):
        try:
            yt = yf.Ticker(ticker, session=session)
            info = yt.info
            if not info or 'currentPrice' not in info:
                # If data is empty, sometimes yfinance doesn't raise exception but returns empty dict
                raise ValueError("Incomplete data received from Yahoo Finance.")
            return yt, info
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff with jitter: (2^attempt) + random(0, 1)
                wait_time = (2 ** attempt) + random.random()
                time.sleep(wait_time)
                continue
            else:
                raise e

def generate_report(ticker):
    ticker = ticker.upper().strip()
    if not ticker:
        st.error("Please enter a valid ticker symbol.")
        return

    with st.spinner(f"Fetching data for {ticker}..."):
        # --- Yahoo Finance Data ---
        try:
            yt, info = fetch_yf_data_with_retry(ticker)
            
            # Helper to safely get info
            def g_yf(key): return info.get(key, "N/A")

            # Get latest expiration date
            exp_dates = yt.options
            latest_exp = exp_dates[0] if exp_dates else "N/A"

            yf_metrics = [
                {"Metric Name": "Current Stock Value", "Source": "Yahoo Finance", "Value": f"${g_yf('currentPrice')}"},
                {"Metric Name": "Market Cap", "Source": "Yahoo Finance", "Value": f"{g_yf('marketCap'):,}" if isinstance(g_yf('marketCap'), int) else g_yf('marketCap')},
                {"Metric Name": "All Insider Ownership %", "Source": "Yahoo Finance", "Value": f"{g_yf('heldPercentInsiders') * 100:.2f}%" if isinstance(g_yf('heldPercentInsiders'), float) else g_yf('heldPercentInsiders')},
                {"Metric Name": "Latest Expiration Date", "Source": "Yahoo Finance", "Value": latest_exp},
            ]
        except Exception as e:
            if "Rate limited" in str(e) or "429" in str(e):
                st.error("Yahoo Finance rate limit hit. Please wait a few minutes before trying again.")
            else:
                st.error(f"Error fetching Yahoo Finance data: {e}")
            yf_metrics = []

        # --- Finviz Data ---
        fv_data = get_finviz_data(ticker)
        if fv_data:
            fv_metrics = [
                {"Metric Name": "Net Insider Activity (Buying/Selling)", "Source": "Finviz", "Value": fv_data.get('Insider Trans', "N/A")},
                {"Metric Name": "Net Buying/Selling %", "Source": "Finviz", "Value": fv_data.get('Inst Trans', "N/A")},
                {"Metric Name": "Short Float %", "Source": "Finviz", "Value": fv_data.get('Short Float', "N/A")},
                {"Metric Name": "Institutional Ownership %", "Source": "Finviz", "Value": fv_data.get('Inst Own', "N/A")},
                {"Metric Name": "Insider Ownership %", "Source": "Finviz", "Value": fv_data.get('Insider Own', "N/A")},
            ]
        else:
            st.warning("Could not retrieve Finviz data. Ticker might be incorrect or site is blocking requests.")
            fv_metrics = []

        # Combine and Display
        all_data = yf_metrics + fv_metrics
        if all_data:
            df = pd.DataFrame(all_data)
            st.markdown(df.to_html(index=False, escape=False), unsafe_allow_html=True)
        else:
            st.error("No metrics could be retrieved.")

# --- App Interface ---
st.markdown("<h1>CEO Value Analysis</h1>", unsafe_allow_html=True)

# Layout for input and button
col1, col2 = st.columns([3, 1])

with col1:
    ticker_input = st.text_input("Enter Ticker Symbol (e.g., TSLA, AAPL)", placeholder="Ticker here...")

with col2:
    st.write("##") # Spacing
    btn = st.button("Generate Report")

if btn:
    generate_report(ticker_input)
