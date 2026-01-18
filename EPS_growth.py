import requests
import sys
import streamlit as st

def get_forward_eps_growth(symbol, api_key):
    """
    Fetches the Forward EPS Growth for a given ticker
    using the Alpha Vantage Fundamental Data (OVERVIEW) endpoint.
    Returns only the numerical growth percentage value or None if an error occurs.
    """
    # Alpha Vantage API URL for Fundamental Data
    url = f'https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={api_key}'

    try:
        response = requests.get(url)
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()
        data = response.json()

        # Handle API Limit/Note messages from Alpha Vantage
        if "Note" in data:
            return None

        # Check if the returned data is empty or invalid
        if not data or "Symbol" not in data:
            return None

        # Alpha Vantage provides 'QuarterlyEarningsGrowthYOY' as the core growth metric in the Overview
        growth_raw = data.get("QuarterlyEarningsGrowthYOY", "0")

        # Convert growth string to a numerical percentage
        try:
            growth_pct = float(growth_raw) * 100
            return growth_pct
        except (ValueError, TypeError):
            return None

    except requests.exceptions.RequestException:
        return None


if __name__ == "__main__":
    # This block allows for testing but keeps the logic importable
    MY_API_KEY = st.secrets["ALPHA_VANTAGE_KEY"]
    ticker = input("Enter Stock Ticker (e.g., NVDA, AAPL): ").strip().upper()

    if ticker:
        result = get_forward_eps_growth(ticker, MY_API_KEY)
        # For testing purposes in this file, we print the captured return
        print(result)