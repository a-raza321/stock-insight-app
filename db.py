import streamlit as st
import pandas as pd
import sys
from google.cloud import bigquery
from google.oauth2 import service_account
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="Analysis History", layout="wide")

# --- PREMIUM UI STYLING ---
st.markdown("""
<style>
    .main-header { text-align: center; color: #1e1e1e; margin-bottom: 20px; }
    .reward-text { color: #28a745 !important; font-weight: bold; }
    .risk-text { color: #dc3545 !important; font-weight: bold; }
    .stButton > button { border-radius: 5px; }
    /* Speed up table rendering */
    .stTable { width: 100%; }
</style>
""", unsafe_allow_html=True)


# --- AUTHENTICATION BLOCK (AS REQUESTED) ---
@st.cache_resource
def get_bigquery_client():
    try:
        if "SERVICE_ACCOUNT_JSON" not in st.secrets:
            sys.stderr.write("ERROR: 'SERVICE_ACCOUNT_JSON' not found in st.secrets\n")
            return None
        service_info = dict(st.secrets["SERVICE_ACCOUNT_JSON"])

        # 2. Fix the private key (Handle Streamlit's newline escaping)
        if "private_key" in service_info:
            service_info["private_key"] = service_info["private_key"].replace("\\n", "\n")
        else:
            sys.stderr.write("ERROR: 'private_key' missing from service account info\n")
            return None

        # 3. Initialize BigQuery Client
        try:
            credentials = service_account.Credentials.from_service_account_info(service_info)
            client = bigquery.Client(credentials=credentials, project=service_info.get("project_id"))
            return client
        except Exception as e:
            sys.stderr.write(f"ERROR: BigQuery Authentication failed: {e}\n")
            return None
    except Exception as e:
        st.error(f"Auth Error: {e}")
        return None


# --- DATABASE HELPERS ---
DATASET_ID = st.secrets["DATASET_ID"]


@st.cache_data(ttl=600)  # Cache ticker list for 10 minutes
def list_ticker_tables():
    if not DATASET_ID:
        st.error("DATASET_ID is missing from st.secrets")
        return []

    client = get_bigquery_client()
    if not client: return []

    try:
        tables = client.list_tables(DATASET_ID)
        return [t.table_id for t in tables if t.table_id.lower() != "moat_score"]
    except Exception as e:
        st.error(f"Error listing tables in dataset '{DATASET_ID}': {e}")
        return []


def delete_ticker_table(ticker):
    client = get_bigquery_client()
    if client:
        try:
            # Construct Fully Qualified Table ID
            if "." in DATASET_ID:
                table_id = f"{DATASET_ID}.{ticker}"
            else:
                table_id = f"{client.project}.{DATASET_ID}.{ticker}"

            client.delete_table(table_id, not_found_ok=True)
            # Clear cache so the ticker disappears from list
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"Error deleting table {ticker}: {e}")
            return False
    return False


@st.cache_data(ttl=300)  # Cache specific table data for 5 minutes
def get_table_data(ticker):
    client = get_bigquery_client()
    if not client: return pd.DataFrame()
    try:
        if "." in DATASET_ID:
            full_table_path = f"{DATASET_ID}.{ticker}"
        else:
            full_table_path = f"{client.project}.{DATASET_ID}.{ticker}"

        query = f"SELECT * FROM `{full_table_path}`"
        job = client.query(query)
        return job.to_dataframe()
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()


def safe_float(val):
    if val is None or str(val).lower() in ['n/a', 'none', 'rejected', '', 'nan']:
        return 0.0
    try:
        cleaned = re.sub(r'[^\d.-]', '', str(val))
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0


# --- APP STATE MANAGEMENT ---
if 'view' not in st.session_state:
    st.session_state.view = 'history'
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = None

# --- UI LOGIC ---

# 1. ANALYSIS HISTORY (LIST VIEW)
if st.session_state.view == 'history':
    st.markdown("<h1 class='main-header'>Analysis History</h1>", unsafe_allow_html=True)

    # Search Box
    search_query = st.text_input("Search Ticker", placeholder="Enter ticker name...").upper()

    # Use cached ticker list
    tickers = list_ticker_tables()

    if search_query:
        tickers = [t for t in tickers if search_query in t.upper()]

    if not tickers:
        st.info(f"No analysis history found in dataset '{DATASET_ID}'.")
        if st.button("Refresh List"):
            st.cache_data.clear()
            st.rerun()
    else:
        # Table Header
        cols = st.columns([1, 4, 1, 1])
        cols[0].write("**Index**")
        cols[1].write("**Ticker Name**")
        cols[2].write("**View**")
        cols[3].write("**Delete**")
        st.divider()

        # Iterate through tickers
        for idx, ticker in enumerate(tickers):
            row_cols = st.columns([1, 4, 1, 1])
            row_cols[0].write(idx + 1)
            row_cols[1].write(f"**{ticker}**")

            # Eye Button (View)
            if row_cols[2].button("👁️", key=f"view_{ticker}"):
                st.session_state.selected_ticker = ticker
                st.session_state.view = 'detail'
                st.rerun()

            # Bin Button (Instant Delete)
            if row_cols[3].button("🗑️", key=f"del_{ticker}"):
                if delete_ticker_table(ticker):
                    st.toast(f"Deleted {ticker}")
                    st.rerun()

# 2. TICKER ANALYSIS (DETAIL VIEW)
elif st.session_state.view == 'detail':
    ticker = st.session_state.selected_ticker

    # Fetch data
    df = get_table_data(ticker)

    # Header Section
    col_back, col_title = st.columns([1, 9])
    if col_back.button("Back"):
        st.session_state.view = 'history'
        st.rerun()

    if df.empty:
        st.error(f"No data found for ticker: {ticker}.")
        if st.button("Clear Cache & Retry"):
            st.cache_data.clear()
            st.rerun()
    else:
        st.markdown(f"<h1 style='text-align: center;'>Analysis: {ticker}</h1>", unsafe_allow_html=True)

        # --- FETCH DATE ---
        m_col = 'Matric name' if 'Matric name' in df.columns else 'Metric Name'
        date_row = df[df[m_col].str.upper() == 'DATE'] if m_col in df.columns else pd.DataFrame()
        date_val = date_row['LLM'].iloc[0] if not date_row.empty else "N/A"
        st.markdown(f"<h3 style='text-align: center;'>Analysis Date: {date_val}</h3>", unsafe_allow_html=True)

        # --- MAIN METRICS TABLE ---
        qual_metrics = ["Risks", "Rewards", "Company Description", "Value Proposition", "Moat Analysis", "DATE"]
        metrics_df = df[~df[m_col].isin(qual_metrics)].copy()

        s_col = 'Obtained Score' if 'Obtained Score' in df.columns else 'Obtained points'
        t_col = 'Total score' if 'Total score' in df.columns else 'Total points'

        display_cols = [m_col, "Source", "Value", s_col, t_col]
        available_display_cols = [c for c in display_cols if c in df.columns]

        # Calculate Total Row
        sum_obtained = metrics_df[s_col].apply(safe_float).sum() if s_col in metrics_df.columns else 0

        total_row = pd.DataFrame([{
            m_col: "Total Score",
            "Source": "",
            "Value": "",
            s_col: int(round(sum_obtained)),
            t_col: 100
        }])

        table_to_show = pd.concat([metrics_df[available_display_cols], total_row], ignore_index=True)

        st.subheader("Financial Metrics")
        st.table(table_to_show)

        # --- SUMMARY TABLE CALCULATION ---
        st.markdown("### Summary")


        def get_score(metric_list):
            val = df[df[m_col].isin(metric_list)][s_col].apply(safe_float).sum() if s_col in df.columns else 0
            return int(round(val))


        s1_metrics = ["Runway", "Net Debt / EBITDA", "Assets / Liabilities Ratio", "Cash Burn Severity",
                      "Share Count Growth", "Capital Structure Pressure"]
        s2_metrics = ["Market cap", "Forward EPS Growth (%)", "Degree of Operating Leverage", "IV Rank",
                      "Short Float (%)", "Institutional Ownership (%)"]
        s3_metrics = ["Total insider ownership %", "CEO Ownership %", "Net Insider Buying vs Selling (%)"]
        s4_metrics = ["GuruFocus Moat Score", "Business Model & Value Proposition"]

        s1 = get_score(s1_metrics)
        s2 = get_score(s2_metrics)
        s3 = get_score(s3_metrics)
        s4 = get_score(s4_metrics)
        final_score = s1 + s2 + s3 + s4

        # Verdict Logic
        score_series = df[s_col].astype(str).str.lower() if s_col in df.columns else pd.Series([])
        is_rejected = "rejected" in score_series.values

        if is_rejected:
            verdict = "❌ Rejected"
        else:
            if final_score >= 80:
                verdict = "🔥 Elite LEAPS Candidate"
            elif final_score >= 70:
                verdict = "✅ Qualified"
            elif final_score >= 60:
                verdict = "⚠️ Watchlist"
            else:
                verdict = "❌ Reject"

        summary_data = [{
            "Ticker": ticker,
            "Financial Survival & Balance Sheet": s1,
            "Growth & Asymmetric Upside": s2,
            "Insider Alignment & Behavior": s3,
            "Moat & Qualitative Conviction": s4,
            "Final Score": final_score,
            "Verdict": verdict
        }]
        st.table(pd.DataFrame(summary_data))


        # --- QUALITATIVE SECTIONS ---
        def get_llm_text(metric_name):
            res = df[df[m_col] == metric_name]['LLM'] if m_col in df.columns and 'LLM' in df.columns else pd.Series([])
            return res.iloc[0] if not res.empty and pd.notnull(res.iloc[0]) else "N/A"


        # 💰 Rewards
        st.markdown("#### 💰 Rewards")
        st.markdown(f'<p class="reward-text">{get_llm_text("Rewards")}</p>', unsafe_allow_html=True)

        # 🚨 Risks
        st.markdown("#### 🚨 Risks")
        st.markdown(f'<p class="risk-text">{get_llm_text("Risks")}</p>', unsafe_allow_html=True)

        # 🏭 Company Description
        st.markdown("#### 🏭 Company Description")
        st.write(get_llm_text("Company Description"))

        # 🤝 Value Proposition
        st.markdown("#### 🤝 Value Proposition")
        st.write(get_llm_text("Value Proposition"))

        # 🛡️ Moat Analysis
        st.markdown("#### 🛡️ Moat Analysis")

        st.write(get_llm_text("Moat Analysis"))
