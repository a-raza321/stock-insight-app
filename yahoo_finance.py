import yfinance as yf
import pandas as pd
from datetime import datetime


def format_large_number(num):
    """
    Converts numbers to strings in Millions, Billions, or Trillions.
    """
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
    """
    Searches for the first matching key in the dataframe and returns
    the value from the most recent period.
    """
    if df is None or df.empty:
        return None, None
    for key in possible_keys:
        if key in df.index:
            val = df.loc[key].iloc[0]
            if pd.notnull(val):
                return val, key
    return None, None


def run_comprehensive_analysis(ticker_symbol):
    results = {"ticker": ticker_symbol, "status": "success", "data": {}, "error": None}
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        # Fetching Dataframes
        q_balance_sheet = ticker.quarterly_balance_sheet
        a_balance_sheet = ticker.balance_sheet
        q_cash_flow = ticker.quarterly_cashflow
        a_financials = ticker.financials
        q_financials = ticker.quarterly_financials

        if not info or (q_balance_sheet.empty and a_financials.empty):
            results["status"] = "error"
            results["error"] = f"Could not retrieve sufficient data for {ticker_symbol}."
            return results

        # 1. Current stock price
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')

        # 2. Market cap
        market_cap = info.get('marketCap')

        # 3. 52 week low / high
        low_52 = info.get('fiftyTwoWeekLow')
        high_52 = info.get('fiftyTwoWeekHigh')

        # 4. Latest expiration date
        options = ticker.options
        latest_expiry = options[-1] if options else "N/A"

        # 5. Total insider ownership %
        insider_own_pct = info.get('heldPercentInsiders')
        insider_val = f"{insider_own_pct * 100:.2f}%" if insider_own_pct is not None else "N/A"

        # 6. Total Assets & Liabilities
        total_assets, _ = get_latest_metric(q_balance_sheet, ['Total Assets'])
        total_liabilities, _ = get_latest_metric(q_balance_sheet, [
            'Total Liabilities Net Minor Interest', 'Total Liab', 'Total Liabilities'
        ])

        # Fallback for Liabilities
        if total_liabilities is None:
            curr_l, _ = get_latest_metric(q_balance_sheet, ['Current Liabilities', 'Total Current Liabilities'])
            non_curr_l, _ = get_latest_metric(q_balance_sheet, ['Total Non Current Liabilities Net Minority Interest',
                                                                'Non Current Liabilities'])
            if curr_l is not None or non_curr_l is not None:
                total_liabilities = (curr_l or 0) + (non_curr_l or 0)

        # 7. Assets / Liabilities Ratio
        al_ratio = None
        if total_assets and total_liabilities and total_liabilities != 0:
            al_ratio = round(total_assets / total_liabilities, 2)

        # 8. Runway (Quarterly Cash / Monthly Burn)
        current_cash, _ = get_latest_metric(q_balance_sheet, ['Cash And Cash Equivalents',
                                                              'Cash Cash Equivalents And Short Term Investments'])
        quarterly_ocf, _ = get_latest_metric(q_cash_flow, ['Operating Cash Flow'])
        runway_val = "N/A"
        if current_cash is not None and quarterly_ocf is not None:
            if quarterly_ocf < 0:
                monthly_burn = abs(quarterly_ocf) / 3
                runway_val = f"{current_cash / monthly_burn:.2f} Months"
            else:
                runway_val = "Positive OCF (No Burn)"

        # 9. Net Debt / EBITDA
        ebitda, _ = get_latest_metric(a_financials, ['EBITDA', 'Normalized EBITDA'])
        net_debt_raw, _ = get_latest_metric(a_balance_sheet, ['Net Debt'])
        if net_debt_raw is None:
            total_debt, _ = get_latest_metric(a_balance_sheet, ['Total Debt'])
            cash_comp, _ = get_latest_metric(a_balance_sheet, ['Cash And Cash Equivalents'])
            if total_debt is not None and cash_comp is not None:
                net_debt_raw = total_debt - cash_comp

        nd_ebitda_val = "N/A"
        # if ebitda and net_debt_raw is not None and ebitda > 0:
        if ebitda is not None and ebitda != 0 and net_debt_raw is not None:
            nd_ebitda_val = round(net_debt_raw / ebitda, 2)

        # 10. Cash Burn Severity
        fcf_ttm = q_cash_flow.loc['Free Cash Flow'].iloc[:4].sum() if 'Free Cash Flow' in q_cash_flow.index else None
        severity_val = "N/A"
        if market_cap and fcf_ttm is not None and fcf_ttm < 0:
            severity_val = f"{(abs(fcf_ttm) / market_cap) * 100:.2f}%"
        elif fcf_ttm is not None and fcf_ttm >= 0:
            severity_val = "0.00% (Positive FCF)"


            share_growth_val = "N/A"
            shares_data = ticker.get_shares_full(start=datetime.now() - pd.DateOffset(years=5))

            if shares_data is not None and not shares_data.empty:
                # Clean data: sort and remove duplicates
                shares_data = shares_data.sort_index().iloc[~shares_data.index.duplicated(keep='last')]

                # Ensure we have at least two data points to compare
                if len(shares_data) > 1:
                    latest_idx = -1
                    target_date = shares_data.index[latest_idx] - pd.DateOffset(years=3)

                    # Find the index of the date closest to 3 years ago
                    idx_3y = shares_data.index.get_indexer([target_date], method='nearest')[0]

                    # Ensure the found index is valid and not the same as the latest index
                    if idx_3y != -1 and idx_3y < (len(shares_data) + latest_idx):
                        latest_s = shares_data.iloc[latest_idx]
                        hist_s = shares_data.iloc[idx_3y]

                        # Calculate time difference in years
                        years_diff = (shares_data.index[latest_idx] - shares_data.index[idx_3y]).days / 365.25

                        # Validation: Check for positive non-zero values and valid time difference
                        if (pd.notnull(latest_s) and pd.notnull(hist_s) and
                                hist_s > 0 and latest_s > 0 and years_diff > 0):
                            cagr = ((latest_s / hist_s) ** (1 / years_diff)) - 1
                            share_growth_val = f"{cagr * 100:.2f}%"

        # 12. Degree of Operating Leverage (DOL)
        dol_val = "N/A"
        if a_financials.shape[1] >= 2 and 'Total Revenue' in a_financials.index:
            sales = a_financials.loc['Total Revenue']
            ebit_v, ebit_k = get_latest_metric(a_financials, ['EBIT', 'Operating Income'])
            if ebit_v is not None:
                ebit_row = a_financials.loc[ebit_k]
                pct_sales = (sales.iloc[0] - sales.iloc[1]) / abs(sales.iloc[1]) if sales.iloc[1] != 0 else 0
                pct_ebit = (ebit_row.iloc[0] - ebit_row.iloc[1]) / abs(ebit_row.iloc[1]) if ebit_row.iloc[1] != 0 else 0
                if pct_sales != 0:
                    dol_val = round(pct_ebit / pct_sales, 2)

        # 13. Capital Structure Pressure (CSP)
        debt_to_equity = info.get('debtToEquity', 0)
        convert_labels = [idx for idx in a_balance_sheet.index if 'convertible' in str(idx).lower()]
        has_converts = len(convert_labels) > 0
        convert_val = a_balance_sheet.loc[convert_labels[0]].iloc[0] if has_converts else 0

        csp_status = "No converts / ATM"
        if (debt_to_equity and debt_to_equity > 300):
            csp_status = "Heavy converts / ATM"  # Extreme case
        elif has_converts:
            dilution_overhang = (convert_val / market_cap) if market_cap and market_cap > 0 else 0
            if dilution_overhang > 0.05 or (debt_to_equity and debt_to_equity > 150):
                csp_status = "Heavy converts / ATM"
            else:
                csp_status = "Minor converts"
        elif debt_to_equity and debt_to_equity > 100:
            csp_status = "Heavy converts / ATM"

        # Construct Final Filtered Output
        final_metrics = {
            "Current stock price": f"{current_price:.2f}" if current_price else "N/A",
            "Market cap": format_large_number(market_cap),
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
        results["status"] = "error"
        results["error"] = str(e)
        return results
