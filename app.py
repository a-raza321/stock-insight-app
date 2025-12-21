import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io

st.set_page_config(
    page_title="Stock Insight",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items=None
)

st.markdown("""
    <style>
    
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .stApp { background-color: #ffffff; }

    .block-container {
        padding-top: 1rem !important;
        max-width: 1000px;
    }

    .main-header {
        text-align: center;
        margin-bottom: 2rem;
        color: #1e1e1e;
    }

    
    .stTextInput > div > div > input {
        color: #1e1e1e !important;
        background-color: #ffffff !important;
        caret-color: #1e1e1e !important;
    }

    
    .stButton > button {
        color: #ffffff !important;
        background-color: #007bff !important;
    }

    
    [data-testid="stMetricValue"] { color: #1e1e1e !important; }
    [data-testid="stMetricLabel"] { color: #555555 !important; }

    
    .stMarkdown, p, span, h1, h2, h3 {
        color: #1e1e1e !important;
    }

    hr { border: 0.5px solid #eeeeee !important; }
    </style>
""", unsafe_allow_html=True)


if 'report_data' not in st.session_state:
    st.session_state.report_data = None
if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = ""




def format_ticker(ticker):
    return ticker.strip().upper()


def get_insider_sentiment(val_str):
    if val_str in ["N/A", "-", ""]: return "N/A"
    try:
        val = float(val_str.replace("%", "").replace(",", ""))
        if val > 0: return "Net Buying"
        if val < 0: return "Net Selling"
        return "Neutral"
    except:
        return "N/A"


def scrape_finviz(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
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


def fetch_metrics(ticker_symbol):
    ticker_symbol = format_ticker(ticker_symbol)
    stock = yf.Ticker(ticker_symbol)

    # Categories of results
    yf_rows = []
    finviz_rows = []
    derived_rows = []

    # 1. Yahoo Finance Basic Info & Expirations
    try:
        info = stock.info
        metrics = [
            ("Company Name", info.get('longName', ticker_symbol)),
            ("Current Stock Price", info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))),
            ("Market Cap", info.get('marketCap', 'N/A')),
            ("Shares Outstanding", info.get('sharesOutstanding', 'N/A')),
            ("52 Week High", info.get('fiftyTwoWeekHigh', 'N/A')),
            ("52 Week Low", info.get('fiftyTwoWeekLow', 'N/A'))
        ]
        for name, val in metrics:
            yf_rows.append({"Metric Name": name, "Source": "Yahoo Finance", "Value": val})

        # Options Expiration
        options = stock.options
        latest_exp = options[-1] if options else "N/A"
        yf_rows.append({"Metric Name": "Latest Options Expiration", "Source": "Yahoo Finance", "Value": latest_exp})

        insider = info.get('heldPercentInsiders')
        yf_rows.append({
            "Metric Name": "Total Insider Ownership %",
            "Source": "Yahoo Finance",
            "Value": f"{insider * 100:.2f}%" if insider else "N/A"
        })
    except:
        pass


    try:
        q_bs = stock.quarterly_balance_sheet
        q_is = stock.quarterly_financials
        if not q_bs.empty:
            bs = q_bs.iloc[:, 0]
            date = q_bs.columns[0].strftime('%Y-%m-%d')

            # Map common balance sheet keys
            assets = bs.get('Total Assets', 'N/A')
            liabs = bs.get('Total Liabilities Net Minority Interest', bs.get('Total Liabilities', 'N/A'))
            cash = bs.get('Cash And Cash Equivalents', bs.get('Cash Cash Equivalents And Short Term Investments', 0))

            yf_rows.append({"Metric Name": "Quarter End Date", "Source": "Yahoo Finance", "Value": str(date)})
            yf_rows.append({"Metric Name": "Total Assets", "Source": "Yahoo Finance", "Value": assets})
            yf_rows.append({"Metric Name": "Total Liabilities", "Source": "Yahoo Finance", "Value": liabs})
            yf_rows.append({"Metric Name": "Cash and Equivalents", "Source": "Yahoo Finance", "Value": float(cash)})

            if not q_is.empty:
                expenses = q_is.iloc[:, 0].get('Operating Expense', q_is.iloc[:, 0].get('Total Operating Expenses', 0))
                yf_rows.append(
                    {"Metric Name": "Quarterly Op Expenses", "Source": "Yahoo Finance", "Value": float(expenses)})

                # Derived Ratios
                try:
                    ratio = round(float(assets) / float(liabs), 2) if (liabs != 'N/A' and float(liabs) != 0) else 0
                    derived_rows.append({"Metric Name": "Asset/Liab Ratio", "Source": "Derived", "Value": ratio})
                except:
                    pass

                try:
                    runway = round(float(cash) / float(expenses), 2) if expenses else 0
                    derived_rows.append({"Metric Name": "Cash Runway (Quarters)", "Source": "Derived", "Value": runway})
                except:
                    pass
    except:
        pass


    fv = scrape_finviz(ticker_symbol)
    for k, v in fv.items():
        finviz_rows.append({"Metric Name": k, "Source": "Finviz", "Value": v})


    all_data = yf_rows + derived_rows + finviz_rows
    return all_data




def main():

    if st.session_state.report_data is None:

        st.markdown(
            '<div class="main-header"><h1>Stock Insight</h1><p>Enter a ticker to see the stock summary</p></div>',
            unsafe_allow_html=True)

        _, center_col, _ = st.columns([1, 1.5, 1])
        with center_col:
            ticker_input = st.text_input("Ticker", placeholder="e.g. TSLA, NVDA", key="ticker_box",
                                         label_visibility="collapsed")
            generate_btn = st.button("Generate Report")

            if generate_btn and ticker_input:
                ticker = format_ticker(ticker_input)
                with st.spinner(f"Analyzing {ticker}..."):
                    data = fetch_metrics(ticker)
                    if len(data) > 0:
                        st.session_state.report_data = data
                        st.session_state.current_ticker = ticker
                        st.rerun()
                    else:
                        st.error("Ticker not found or data unavailable.")
    else:

        col_reset, _ = st.columns([1, 8])
        with col_reset:
            if st.button("Reset"):
                st.session_state.report_data = None
                st.session_state.current_ticker = ""
                st.rerun()

        st.markdown('<div class="main-header"><h1>Stock Insight</h1></div>', unsafe_allow_html=True)

        data = st.session_state.report_data
        ticker = st.session_state.current_ticker
        df = pd.DataFrame(data)
        df['Value'] = df['Value'].astype(str)

        st.markdown("---")
        st.header(f"📊 {ticker} Report")

        def find_val(name):
            return next((item['Value'] for item in data if item['Metric Name'] == name), "N/A")

        col1, _, _ = st.columns([2, 1, 1])
        with col1:
            st.metric(" Company", find_val('Company Name'))

        st.markdown("---")
        st.subheader("Consolidated Data Table")
        st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()