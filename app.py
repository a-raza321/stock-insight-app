import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import concurrent.futures
from datetime import datetime

# --- Configuration & Styling ---
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
    .report-card { background-color: #f8f9fa; padding: 20px; border-radius: 12px; border: 1px solid #e9ecef; margin-bottom: 20px; white-space: pre-wrap; }
    </style>
""", unsafe_allow_html=True)

# --- Constants ---
API_KEY = "AIzaSyDltEXJqAbp7dBbI59g-XEd_Uy479R77tU"  # The environment provides the key at runtime
MODEL_NAME = "gemini-2.5-flash-preview-09-2025"


# --- Helper Functions ---

def format_ticker(ticker):
    return ticker.strip().upper()


def format_large_number(val):
    if not isinstance(val, (int, float)): return val
    try:
        abs_val = abs(val)
        if abs_val >= 1_000_000_000_000:
            return f"${val / 1_000_000_000_000:.3f}T"
        elif abs_val >= 1_000_000_000:
            return f"${val / 1_000_000_000:.2f}B"
        elif abs_val >= 1_000_000:
            return f"${val / 1_000_000:.2f}M"
        return f"${val:,.2f}"
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


# --- Gemini API Utils ---

def call_gemini_general(prompt, system_instruction=None, use_search=False):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0}
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    if use_search:
        payload["tools"] = [{"google_search": {}}]

    # Exponential backoff
    for i in [1, 2, 4, 8, 16]:
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text',
                                                                                                      'N/A').strip()
            elif response.status_code == 429:
                time.sleep(i)
        except:
            time.sleep(i)
    return "N/A"


# --- Scrapers ---

def scrape_finviz(ticker):
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
        return {
            "Net Insider Buying vs Selling %": data.get("Insider Trans", "N/A"),
            "Net Insider Activity": get_insider_sentiment(data.get("Insider Trans", "N/A")),
            "Institutional Ownership %": data.get("Inst Own", "N/A"),
            "Short Float %": data.get("Short Float", "N/A")
        }
    except:
        return {}


def fetch_moat_score_fast(ticker):
    """Replaced Selenium with Gemini Search for stability and speed."""
    prompt = f"Find the current GuruFocus Moat Score for the stock ticker: {ticker}."
    return call_gemini_general(prompt,
                               system_instruction="Provide ONLY the numerical score. For example, if the score is 8, just output '8'. Do not include words like 'Moat' or 'Rating'.",
                               use_search=True)


# --- Research Agents ---

def fetch_simply_wall_st_analysis(ticker):
    prompt = f"""
    Search Simply Wall St (simplywall.st) for {ticker}.
    Structure the response into these EXACT sections without emojis:

    Rewards
    - Key bullet points from Valuation, Growth, and Dividends.

    Risks
    - Financial health flags and debt analysis.

    Risk/Reward Synthesis
    - Overall assessment.
    - Verdict: One-line long-term outlook.

    LEAPS Implications
    - Dilution, profitability, and volatility impact.
    """
    return call_gemini_general(prompt, use_search=True)


def fetch_moat_indicators(ticker):
    prompt = f"Identify 2-4 qualitative economic moat indicators for {ticker} (e.g., Brand, Switching Costs, Network Effect). Based on GuruFocus analysis."
    return call_gemini_general(prompt,
                               system_instruction="Output ONLY plain bullet points: - [Heading]: [Description max 10 words]. Do not use markdown bolding.",
                               use_search=True)


# --- Core Data Fetcher ---

def fetch_yfinance_data(ticker):
    all_rows = []
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Standard Metrics
        metrics = [
            ("Company Name", info.get('longName', ticker)),
            ("Current Stock Price", info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))),
            ("Market Cap", info.get('marketCap', 'N/A')),
            ("Shares Outstanding", info.get('sharesOutstanding', 'N/A')),
            ("52 Week High", info.get('fiftyTwoWeekHigh', 'N/A')),
            ("52 Week Low", info.get('fiftyTwoWeekLow', 'N/A'))
        ]
        for name, val in metrics:
            all_rows.append({"Metric Name": name, "Source": "Yahoo Finance", "Value": format_large_number(val)})

        # Ownership
        total_insider = info.get('heldPercentInsiders')
        insider_val = f"{total_insider * 100:.2f}%" if total_insider is not None else "N/A"
        all_rows.append({"Metric Name": "Total Insider Ownership %", "Source": "Yahoo Finance", "Value": insider_val})

        # Latest Options Expiration
        options = stock.options
        all_rows.append({"Metric Name": "Latest Options Expiration", "Source": "Yahoo Finance",
                         "Value": options[-1] if options else "N/A"})

        # Financials
        q_bs = stock.quarterly_balance_sheet
        q_cf = stock.quarterly_cashflow
        q_is = stock.quarterly_financials

        if not q_bs.empty:
            bs = q_bs.iloc[:, 0]

            # Specific requested metrics
            total_assets = bs.get('Total Assets', 0)
            total_liabilities = bs.get('Total Liabilities Net Minority Interest', bs.get('Total Liabilities', 0))
            cash = bs.get('Cash And Cash Equivalents', bs.get('Cash Cash Equivalents And Short Term Investments', 0))

            all_rows.append({"Metric Name": "Total Assets", "Source": "Yahoo Finance",
                             "Value": format_large_number(float(total_assets))})
            all_rows.append({"Metric Name": "Total Liabilities", "Source": "Yahoo Finance",
                             "Value": format_large_number(float(total_liabilities))})

            # Assets / Liabilities Ratio
            if total_liabilities and total_liabilities != 0:
                al_ratio = round(float(total_assets) / float(total_liabilities), 2)
                all_rows.append({"Metric Name": "Assets / Liabilities Ratio", "Source": "Derived", "Value": al_ratio})

            all_rows.append({"Metric Name": "Cash & Cash Equivalents (Latest Quarter)", "Source": "Yahoo Finance",
                             "Value": format_large_number(float(cash))})

            # Operating Expenses (Quarterly)
            if not q_is.empty:
                is_data = q_is.iloc[:, 0]
                op_expenses = is_data.get('Operating Expense', is_data.get('Total Operating Expenses', 0))
                all_rows.append({"Metric Name": "Operating Expenses (Quarterly)", "Source": "Yahoo Finance",
                                 "Value": format_large_number(float(op_expenses))})

            # Calculate Runway
            if not q_cf.empty:
                op_cash_flow = 0
                for key in ['Total Cash From Operating Activities', 'Operating Cash Flow',
                            'Cash Flow From Continuing Operating Activities']:
                    if key in q_cf.index:
                        op_cash_flow = q_cf.loc[key].iloc[0]
                        break
                if op_cash_flow < 0:
                    monthly_burn = abs(float(op_cash_flow)) / 3
                    runway = round(float(cash) / monthly_burn, 1) if monthly_burn > 0 else 0
                    all_rows.append({"Metric Name": "Runway", "Source": "Derived", "Value": f"{runway} months"})
                else:
                    all_rows.append({"Metric Name": "Runway", "Source": "Derived", "Value": "Cash flow positive"})

        # CEO Ownership via Search
        ceo_val = call_gemini_general(f"CEO ownership percentage of {ticker} from Yahoo Finance.",
                                      system_instruction="Provide ONLY the percentage value.", use_search=True)
        all_rows.append({"Metric Name": "CEO Ownership %", "Source": "Yahoo Finance", "Value": ceo_val})

    except Exception as e:
        st.error(f"Error fetching YFinance data: {e}")
    return all_rows


def fetch_all_data_parallel(ticker):
    # Use ThreadPoolExecutor for concurrent execution
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit all tasks
        future_yf = executor.submit(fetch_yfinance_data, ticker)
        future_fv = executor.submit(scrape_finviz, ticker)
        future_moat_score = executor.submit(fetch_moat_score_fast, ticker)
        future_sws = executor.submit(fetch_simply_wall_st_analysis, ticker)
        future_moat_ind = executor.submit(fetch_moat_indicators, ticker)

        # Collect results
        yf_rows = future_yf.result()
        fv_data = future_fv.result()
        moat_score = future_moat_score.result()
        sws_report = future_sws.result()
        moat_indicators = future_moat_ind.result()

    # Merge Finviz and Moat Score into the metrics list
    for k, v in fv_data.items():
        yf_rows.append({"Metric Name": k, "Source": "Finviz", "Value": v})

    yf_rows.append({"Metric Name": "Moat Score", "Source": "Guru Focus", "Value": moat_score})

    return yf_rows, sws_report, moat_indicators


# --- UI Layout ---

def main():
    if 'report_data' not in st.session_state:
        st.session_state.report_data = None

    if st.session_state.report_data is None:
        st.markdown(
            '<div class="main-header"><h1>Stock Insight Pro</h1><p>Institutional-Grade Stock Analysis</p></div>',
            unsafe_allow_html=True)
        _, center_col, _ = st.columns([1, 1.5, 1])
        with center_col:
            ticker_input = st.text_input("Ticker", placeholder="e.g. TSLA, NVDA", key="ticker_box",
                                         label_visibility="collapsed")
            generate_btn = st.button("Generate Comprehensive Report")
            if generate_btn and ticker_input:
                ticker = format_ticker(ticker_input)
                with st.spinner(f"Running Parallel Analysis for {ticker}..."):
                    metrics, sws, moat = fetch_all_data_parallel(ticker)
                    st.session_state.report_data = metrics
                    st.session_state.sws_report = sws
                    st.session_state.moat_report = moat
                    st.session_state.current_ticker = ticker
                    st.rerun()
    else:
        col_title, col_reset = st.columns([8, 2])
        with col_title:
            st.title(f"📊 {st.session_state.current_ticker} Report")
        with col_reset:
            if st.button("New Analysis"):
                st.session_state.report_data = None
                st.rerun()

        tab1, tab2, tab3 = st.tabs(["Metrics & Financials", "Risk & Reward Analysis", "Moat Indicators"])

        with tab1:
            st.subheader("Consolidated Market Data")
            df = pd.DataFrame(st.session_state.report_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

        with tab2:
            st.subheader("Simply Wall St: Deep Analysis")
            st.markdown(f'<div class="report-card">{st.session_state.sws_report}</div>', unsafe_allow_html=True)

        with tab3:
            st.subheader("GuruFocus: Qualitative Moat Indicators")
            st.markdown(f'<div class="report-card">{st.session_state.moat_report}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
