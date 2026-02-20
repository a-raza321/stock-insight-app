import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import logging
import streamlit as st
import requests
import json
import sys
import os

# --- API Key from Secrets ---
ALPHA_VANTAGE_KEY = st.secrets["ALPHA_VANTAGE_API_KEY_3"]

# --- Configured logging to track errors and retries ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def format_large_number(num):
    """Converts numbers to strings in Millions, Billions, or Trillions."""
    if num is None or not isinstance(num, (int, float)):
        return "N/A"
    abs_num = abs(num)
    if abs_num >= 1_000_000_000_000:
        return f"{num / 1_000_000_000_000:.2f} Trillion"
    elif abs_num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f} Billion"
    elif abs_num >= 1_000_000:
        return f"{num / 1_000_000:.2f} Million"
    else:
        return f"{num:.2f}"

def get_latest_metric(df, possible_keys):
    """Searches for the first matching key in the dataframe and returns the latest value."""
    if df is None or df.empty:
        return None, None
    for key in possible_keys:
        if key in df.index:
            try:
                val = df.loc[key].iloc[0]
                if pd.notnull(val):
                    return val, key
            except (IndexError, AttributeError):
                continue
    return None, None

def run_comprehensive_analysis(ticker_symbol):
    # Proxy Configuration
    PROXY_USER = st.secrets["PROXY_USER"]
    PROXY_PASS = st.secrets["PROXY_PASS"]
    PROXY_HOST = "gw.dataimpulse.com"
    PROXY_PORT = "823"
    proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    proxies = {"http": proxy_url, "https": proxy_url}

    max_retries = 2
    retry_count = 0
    results = {"ticker": ticker_symbol, "status": "success", "data": {}, "error": None}

    # Initialize variables
    current_price = None
    market_cap = None
    low_52 = None
    high_52 = None
    latest_expiry = "N/A"
    insider_val = "N/A"
    total_assets = None
    total_liabilities = None
    al_ratio = None
    runway_val = "N/A"
    ebitda = None
    net_debt_raw = None
    nd_ebitda_val = "N/A"
    severity_val = "N/A"
    share_growth_val = "N/A"
    dol_val = "N/A"
    csp_status = "No converts / ATM"
    shares_outstanding = None

    def av_clean(val):
        try:
            return float(val) if val and str(val).lower() != "none" else 0.0
        except (ValueError, TypeError):
            return 0.0

    while retry_count < max_retries:
        try:
            logging.info(f"Attempt {retry_count + 1} for {ticker_symbol} using proxy {proxy_url}")
            ticker = yf.Ticker(ticker_symbol)

            # --- 1. YAHOO FINANCE DATA EXTRACTION (WITH PROXY) ---
            try:
                # To apply proxy correctly in yfinance, we pass it to the 'proxy' parameter in methods
                # Note: yf.Ticker object property 'proxy' is used by internal fetchers
                ticker.proxy = proxy_url 
                
                info = ticker.get_info(proxy=proxy_url)
                q_balance_sheet = ticker.get_drawdown_balancesheet(proxy=proxy_url) if hasattr(ticker, 'get_drawdown_balancesheet') else ticker.quarterly_balance_sheet
                a_balance_sheet = ticker.balance_sheet
                q_cash_flow = ticker.quarterly_cashflow
                a_financials = ticker.financials

                current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                market_cap = info.get('marketCap')
                shares_outstanding = info.get('sharesOutstanding')
                low_52 = info.get('fiftyTwoWeekLow')
                high_52 = info.get('fiftyTwoWeekHigh')
                insider_own_pct = info.get('heldPercentInsiders')
                
                # Expiry and Shares Growth
                try:
                    options = ticker.options
                    latest_expiry = options[-1] if options else "N/A"
                except: latest_expiry = "N/A"
                
                try:
                    shares_data = ticker.get_shares_full(start=datetime.now() - pd.DateOffset(years=5))
                    if shares_data is not None and not shares_data.empty:
                        shares_data = shares_data.sort_index().iloc[~shares_data.index.duplicated(keep='last')]
                        if len(shares_data) > 1:
                            latest_idx = -1
                            target_date = shares_data.index[latest_idx] - pd.DateOffset(years=3)
                            idx_3y = shares_data.index.get_indexer([target_date], method='nearest')[0]
                            if idx_3y != -1:
                                latest_s, hist_s = shares_data.iloc[latest_idx], shares_data.iloc[idx_3y]
                                years_diff = (shares_data.index[latest_idx] - shares_data.index[idx_3y]).days / 365.25
                                if hist_s > 0 and years_diff > 0:
                                    cagr = ((latest_s / hist_s) ** (1 / years_diff)) - 1
                                    share_growth_val = f"{cagr * 100:.2f}%"
                except: share_growth_val = "N/A"

            except Exception as yf_err:
                logging.warning(f"Yahoo Finance Rate Limit/Error for {ticker_symbol}: {yf_err}. Shifting to Alpha Vantage immediately.")
                # We don't return here; we let the AV backups below handle it
                info, q_balance_sheet, a_balance_sheet, q_cash_flow, a_financials = {}, None, None, None, None
                insider_own_pct = None

            # --- 2. ALPHA VANTAGE BACKUPS (TRIGGERED IF YF DATA IS MISSING) ---
            
            # Backup: Price, Cap, Shares, Range
            if not current_price or not market_cap:
                try:
                    ov_url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker_symbol}&apikey={ALPHA_VANTAGE_KEY}"
                    ov_data = requests.get(ov_url, proxies=proxies, timeout=15).json()
                    
                    if not current_price:
                        gq_url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker_symbol}&apikey={ALPHA_VANTAGE_KEY}"
                        gq_data = requests.get(gq_url, proxies=proxies, timeout=15).json().get("Global Quote", {})
                        current_price = av_clean(gq_data.get("05. price"))
                    
                    market_cap = market_cap or av_clean(ov_data.get("MarketCapitalization"))
                    shares_outstanding = shares_outstanding or av_clean(ov_data.get("SharesOutstanding"))
                    low_52 = low_52 or av_clean(ov_data.get("52WeekLow"))
                    high_52 = high_52 or av_clean(ov_data.get("52WeekHigh"))
                    if insider_own_pct is None:
                        insider_own_pct = av_clean(ov_data.get("PercentInsiders")) / 100.0 if ov_data.get("PercentInsiders") else None
                except Exception as e: logging.error(f"AV Primary Backup Error: {e}")

            insider_val = f"{insider_own_pct * 100:.2f}%" if insider_own_pct is not None else "N/A"

            # Backup: Assets & Liabilities
            total_assets, _ = get_latest_metric(q_balance_sheet, ['Total Assets'])
            total_liabilities, _ = get_latest_metric(q_balance_sheet, ['Total Liabilities Net Minor Interest', 'Total Liab', 'Total Liabilities'])
            
            if total_assets is None or total_liabilities is None:
                try:
                    av_bs_url = f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={ticker_symbol}&apikey={ALPHA_VANTAGE_KEY}"
                    reports = requests.get(av_bs_url, proxies=proxies, timeout=15).json().get("quarterlyReports", [])
                    if reports:
                        total_assets = total_assets or av_clean(reports[0].get("totalAssets"))
                        total_liabilities = total_liabilities or av_clean(reports[0].get("totalLiabilities"))
                except: pass

            if total_assets and total_liabilities and total_liabilities != 0:
                al_ratio = round(total_assets / total_liabilities, 2)

            # Backup: Runway (Cash & Burn)
            current_cash, _ = get_latest_metric(q_balance_sheet, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'])
            quarterly_ocf, _ = get_latest_metric(q_cash_flow, ['Operating Cash Flow'])

            if current_cash is None or quarterly_ocf is None:
                try:
                    av_bs_url = f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={ticker_symbol}&apikey={ALPHA_VANTAGE_KEY}"
                    av_cf_url = f"https://www.alphavantage.co/query?function=CASH_FLOW&symbol={ticker_symbol}&apikey={ALPHA_VANTAGE_KEY}"
                    if current_cash is None:
                        current_cash = av_clean(requests.get(av_bs_url, proxies=proxies, timeout=15).json().get("quarterlyReports", [{}])[0].get("cashAndCashEquivalentsAtCarryingValue"))
                    if quarterly_ocf is None:
                        quarterly_ocf = av_clean(requests.get(av_cf_url, proxies=proxies, timeout=15).json().get("quarterlyReports", [{}])[0].get("operatingCashflow"))
                except: pass

            if current_cash is not None and quarterly_ocf is not None:
                if quarterly_ocf < 0:
                    monthly_burn = abs(quarterly_ocf) / 3
                    runway_val = f"{current_cash / monthly_burn:.2f} Months"
                else: runway_val = "Positive OCF (No Burn)"

            # Backup: Net Debt / EBITDA
            ebitda, _ = get_latest_metric(a_financials, ['EBITDA', 'Normalized EBITDA'])
            net_debt_raw, _ = get_latest_metric(a_balance_sheet, ['Net Debt'])

            if ebitda is None or net_debt_raw is None:
                try:
                    av_inc_url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={ticker_symbol}&apikey={ALPHA_VANTAGE_KEY}"
                    av_bs_url = f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={ticker_symbol}&apikey={ALPHA_VANTAGE_KEY}"
                    if ebitda is None:
                        ebitda = av_clean(requests.get(av_inc_url, proxies=proxies, timeout=15).json().get("annualReports", [{}])[0].get("ebitda"))
                    if net_debt_raw is None:
                        report = requests.get(av_bs_url, proxies=proxies, timeout=15).json().get("annualReports", [{}])[0]
                        net_debt_raw = (av_clean(report.get("shortTermDebt")) + av_clean(report.get("longTermDebt"))) - av_clean(report.get("cashAndCashEquivalentsAtCarryingValue"))
                except: pass

            if ebitda and ebitda != 0 and net_debt_raw is not None:
                nd_ebitda_val = round(net_debt_raw / ebitda, 2)

            # Backup: DOL
            if a_financials is not None and a_financials.shape[1] >= 2 and 'Total Revenue' in a_financials.index:
                sales = a_financials.loc['Total Revenue']
                ebit_v, ebit_k = get_latest_metric(a_financials, ['EBIT', 'Operating Income'])
                if ebit_v is not None:
                    ebit_row = a_financials.loc[ebit_k]
                    pct_sales = (sales.iloc[0] - sales.iloc[1]) / abs(sales.iloc[1]) if sales.iloc[1] != 0 else 0
                    pct_ebit = (ebit_row.iloc[0] - ebit_row.iloc[1]) / abs(ebit_row.iloc[1]) if ebit_row.iloc[1] != 0 else 0
                    if pct_sales != 0: dol_val = round(pct_ebit / pct_sales, 2)

            if dol_val == "N/A":
                try:
                    av_inc_url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={ticker_symbol}&apikey={ALPHA_VANTAGE_KEY}"
                    reports = requests.get(av_inc_url, proxies=proxies, timeout=15).json().get("annualReports", [])
                    if len(reports) >= 2:
                        s1, s2 = av_clean(reports[0].get("totalRevenue")), av_clean(reports[1].get("totalRevenue"))
                        e1, e2 = av_clean(reports[0].get("operatingIncome")), av_clean(reports[1].get("operatingIncome"))
                        p_sales = (s1 - s2) / abs(s2) if s2 != 0 else 0
                        p_ebit = (e1 - e2) / abs(e2) if e2 != 0 else 0
                        if p_sales != 0: dol_val = round(p_ebit / p_sales, 2)
                except: pass

            # CSP Calculation
            debt_to_equity = info.get('debtToEquity', 0)
            if not debt_to_equity:
                try:
                    ov_url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker_symbol}&apikey={ALPHA_VANTAGE_KEY}"
                    debt_to_equity = av_clean(requests.get(ov_url, proxies=proxies, timeout=15).json().get("DebtToEquityRatio")) * 100
                except: pass

            has_converts = False
            if a_balance_sheet is not None:
                convert_labels = [idx for idx in a_balance_sheet.index if 'convertible' in str(idx).lower()]
                if convert_labels:
                    has_converts = True
                    convert_val = a_balance_sheet.loc[convert_labels[0]].iloc[0]
                    dilution_overhang = (convert_val / market_cap) if market_cap and market_cap > 0 else 0
                    if dilution_overhang > 0.05 or debt_to_equity > 150: csp_status = "Heavy converts / ATM"
                    else: csp_status = "Minor converts"
            
            if csp_status == "No converts / ATM" and debt_to_equity > 100:
                csp_status = "Heavy converts / ATM"

            # Final Metrics Assembly
            final_metrics = {
                "Current stock price": f"{current_price:.2f}" if current_price else "N/A",
                "Market cap": format_large_number(market_cap),
                "Shares Outstanding": format_large_number(shares_outstanding),
                "52 week low": f"{low_52:.2f}" if low_52 else "N/A",
                "52 weeks high": f"{high_52:.2f}" if high_52 else "N/A",
                "latest expiration date": latest_expiry,
                "Total insider ownership %": insider_val,
                "Total Assets": format_large_number(total_assets),
                "Total Liabilities": format_large_number(total_liabilities),
                "Assets / Liabilities Ratio": al_ratio if al_ratio is not None else "N/A",
                "Runway": runway_val,
                "Net Debt": format_large_number(net_debt_raw),
                "EBITDA": format_large_number(ebitda),
                "Net Debt / EBITDA": nd_ebitda_val,
                "Cash Burn Severity": severity_val,
                "Share Count Growth": share_growth_val,
                "Degree of Operating Leverage": dol_val,
                "Capital Structure Pressure": csp_status
            }

            results["data"] = {"Summary": final_metrics}
            return results

        except Exception as e:
            retry_count += 1
            logging.error(f"Error on attempt {retry_count} for {ticker_symbol}: {str(e)}")
            if retry_count < max_retries:
                time.sleep(2)
            else:
                results["status"] = "error"
                results["error"] = f"Final failure for {ticker_symbol}: {str(e)}"
                return results
