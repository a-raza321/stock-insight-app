import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import numpy as np
from bs4 import BeautifulSoup
import time
import concurrent.futures
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# --- CONFIGURATION & STYLING ---
st.set_page_config(
    page_title="Stock Insight Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
    </style>
""", unsafe_allow_html=True)


# --- HELPER FUNCTIONS ---
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


# --- SCRAPERS ---
def scrape_finviz(ticker):
    """Scrapes specific previously requested metrics from Finviz snapshot table."""
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200: return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="snapshot-table2")
        if not table: return {}
        data = {}
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            for i in range(0, len(cols), 2):
                key, val = cols[i].text.strip(), cols[i + 1].text.strip()
                data[key] = val

        # Filter to only the previously requested metrics + new requested Insider Ownership %
        return {
            "Net Insider Buying vs Selling %": data.get("Insider Trans", "N/A"),
            "Net Insider Activity": get_insider_sentiment(data.get("Insider Trans", "N/A")),
            "Institutional Ownership %": data.get("Inst Own", "N/A"),
            "Short Float %": data.get("Short Float", "N/A"),
            "Insider Ownership % (Finviz)": data.get("Insider Own", "N/A")  # Newly added
        }
    except:
        return {}


def fetch_yfinance_data(ticker):
    """Fetches previously requested metrics from Yahoo Finance."""
    all_rows = []
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # General Market Data
        metrics = [
            ("Company Name", info.get('longName', ticker), False),
            ("Current Stock Price", info.get('currentPrice', info.get('regularMarketPrice', 'N/A')), True),
            ("Market Cap", info.get('marketCap', 'N/A'), True),
            ("Shares Outstanding", info.get('sharesOutstanding', 'N/A'), False),
            ("52 Week High", info.get('fiftyTwoWeekHigh', 'N/A'), True),
            ("52 Week Low", info.get('fiftyTwoWeekLow', 'N/A'), True)
        ]
        for name, val, is_curr in metrics:
            all_rows.append({"Metric Name": name, "Source": "Yahoo Finance",
                             "Value": format_large_number(val, is_currency=is_curr)})

        total_insider = info.get('heldPercentInsiders')
        ins_val = f"{total_insider * 100:.2f}%" if total_insider is not None else "N/A"
        all_rows.append({"Metric Name": "Total Insider Ownership %", "Source": "Yahoo Finance", "Value": ins_val})

        try:
            opts = stock.options
            all_rows.append({"Metric Name": "Latest Options Expiration", "Source": "Yahoo Finance",
                             "Value": opts[-1] if opts else "N/A"})
        except:
            all_rows.append({"Metric Name": "Latest Options Expiration", "Source": "Yahoo Finance", "Value": "N/A"})

        # Financial Statements
        q_bs = stock.quarterly_balance_sheet
        q_cf = stock.quarterly_cashflow
        q_is = stock.quarterly_financials

        if not q_bs.empty:
            bs = q_bs.iloc[:, 0]
            total_assets = bs.get('Total Assets', 0)
            total_liabilities = bs.get('Total Liabilities Net Minority Interest', bs.get('Total Liabilities', 0))
            cash = bs.get('Cash And Cash Equivalents', bs.get('Cash Cash Equivalents And Short Term Investments', 0))

            all_rows.append({"Metric Name": "Total Assets", "Source": "Yahoo Finance",
                             "Value": format_large_number(float(total_assets), True)})
            all_rows.append({"Metric Name": "Total Liabilities", "Source": "Yahoo Finance",
                             "Value": format_large_number(float(total_liabilities), True)})

            if total_liabilities and total_liabilities != 0:
                al_ratio = round(float(total_assets) / float(total_liabilities), 2)
                all_rows.append({"Metric Name": "Assets / Liabilities Ratio", "Source": "Derived", "Value": al_ratio})

            all_rows.append({"Metric Name": "Cash & Cash Equivalents (Latest Quarter)", "Source": "Yahoo Finance",
                             "Value": format_large_number(float(cash), True)})

            if not q_is.empty:
                is_data = q_is.iloc[:, 0]
                op_exp = is_data.get('Operating Expense', is_data.get('Total Operating Expenses', 0))
                all_rows.append({"Metric Name": "Operating Expenses (Quarterly)", "Source": "Yahoo Finance",
                                 "Value": format_large_number(float(op_exp), True)})

            if not q_cf.empty:
                op_cash = 0
                for key in ['Total Cash From Operating Activities', 'Operating Cash Flow',
                            'Cash Flow From Continuing Operating Activities']:
                    if key in q_cf.index:
                        op_cash = q_cf.loc[key].iloc[0]
                        break
                if op_cash < 0:
                    monthly_burn = abs(float(op_cash)) / 3
                    runway = round(float(cash) / monthly_burn, 1) if monthly_burn > 0 else 0
                    all_rows.append({"Metric Name": "Runway", "Source": "Derived", "Value": f"{runway} months"})
                else:
                    all_rows.append({"Metric Name": "Runway", "Source": "Derived", "Value": "Cash flow positive"})

    except Exception as e:
        st.error(f"Error fetching YFinance data: {e}")
    return all_rows


# --- MAIN EXECUTION LOGIC ---
def fetch_all_data(ticker):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_yf = executor.submit(fetch_yfinance_data, ticker)
        f_fv = executor.submit(scrape_finviz, ticker)

        yf_rows = f_yf.result()
        fv_data = f_fv.result()

    # Consolidate results
    for k, v in fv_data.items():
        yf_rows.append({"Metric Name": k, "Source": "Finviz", "Value": v})

    return yf_rows


def main():
    if 'report_data' not in st.session_state: st.session_state.report_data = None

    if st.session_state.report_data is None:
        st.markdown(
            '<div class="main-header"><h1>Stock Insight Pro</h1><p>Institutional-Grade Metrics & Financials</p></div>',
            unsafe_allow_html=True)

        _, center_col, _ = st.columns([1, 1.5, 1])
        with center_col:
            ticker_input = st.text_input("Enter Ticker", placeholder="e.g. TSLA, NVDA", key="ticker_box",
                                         label_visibility="collapsed")
            if st.button("Generate Comprehensive Report") and ticker_input:
                ticker = format_ticker(ticker_input)
                status_text = st.empty()
                status_text.info(f"Gathering data for {ticker} from Yahoo Finance and Finviz...")

                try:
                    metrics = fetch_all_data(ticker)
                    if metrics:
                        st.session_state.report_data = metrics
                        st.session_state.current_ticker = ticker
                        status_text.empty()
                        st.rerun()
                    else:
                        status_text.error("No data could be retrieved for this ticker.")
                except Exception as e:
                    status_text.error(f"Analysis failed: {e}")
    else:
        col_title, col_reset = st.columns([8, 2])
        col_title.title(f"📊 {st.session_state.current_ticker} Financial Report")
        if col_reset.button("New Analysis"):
            st.session_state.report_data = None
            st.rerun()

        st.subheader("Consolidated Market & Financial Metrics")
        df = pd.DataFrame(st.session_state.report_data)

        if not df.empty:
            df['Value'] = df['Value'].astype(str)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No metric data found.")


if __name__ == "__main__":
    main()
