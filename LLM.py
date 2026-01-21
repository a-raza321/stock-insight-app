import requests
import json
import time
import os
import streamlit as st


def get_company_name(ticker):
    """
    Fetches the official company name from Polygon.io using the ticker.
    """
    # Replace with your actual Polygon.io API key
    # polygon_api_key = ""
    polygon_api_key = st.secrets["polygon"]
    url = f"https://api.polygon.io/v3/reference/tickers/{ticker}?apiKey={polygon_api_key}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Extract the company name from the results
            name = data.get("results", {}).get("name")
            if name:
                return name
            return ticker
        else:
            # Fallback to ticker if API call fails
            return ticker
    except Exception:
        return ticker


def analyze_ticker(ticker):
    """
    Python script to perform fundamental equity analysis using the Perplexity API.
    """

    # 1. Configuration
    # Hardcoded API key as requested
    # api_key = ""
    api_key = st.secrets["perplexity"]

    # 2. Get the name of company using ticker through api of polygon.io
    company_name = get_company_name(ticker)

    # 3. Construct the Prompts
    system_prompt = "You are a fundamental equity analyst."

    # Passing the company_name fetched from Polygon.io directly into the prompt
    user_prompt = f"""Analyze the following company: {company_name} (Ticker: {ticker})

Tasks:
1. Write a short company description (3–4 sentences).
2. Clearly state the company’s main value propositions to customers.
3. Identify and explain the company’s economic moat, if any (e.g., switching costs, network effects, scale, regulation, brand, cost advantage).
4. Identify the current CEO and report the most recent available CEO ownership percentage of the company’s outstanding shares.
   - Use the latest publicly available data (SEC filings, proxy statements, or reliable financial sources).
   - If exact ownership is unavailable, state “Not disclosed” and explain briefly.

Then classify the company into ONE of the following categories based on its business model and moat strength.
Return ONLY one category and its corresponding points.

Categories (choose exactly one):
- Mission-critical / infrastructure → 15 points  
- High switching cost SaaS / platform → 10 points  
- Competitive commodity → 5 points  
- Cyclical / low differentiation → 0 points  

Output format (strict):
Company Description:
<text>

Value Proposition:
- <bullet point>
- <bullet point>

Moat Analysis:
<text>

CEO Ownership:
CEO Name: <name>
Ownership Percentage: <numeric % or "Not disclosed">
Source: <brief source reference>

Final Classification:
Category: <one category only>
Points: <numeric value>
Confidence Level: <High / Medium / Low>

Rules:
- Do not mention more than one category.
- If the company fits multiple categories, choose the highest applicable score.
- Use factual, neutral language.
- Avoid speculation.
- Base conclusions on business fundamentals, customer dependency, and competitive dynamics.
"""

    # 4. API Request Setup
    url = "https://api.perplexity.ai/chat/completions"

    payload = {
        "model": "sonar",  # Uses Perplexity's online search-enabled model
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,  # Low temperature for factual analysis
        "top_p": 0.9,
        "return_citations": True,
        "search_domain_filter": ["sec.gov", "finance.yahoo.com", "bloomberg.com", "reuters.com"],
        "return_images": False,
        "return_related_questions": False,
        "search_recency_filter": "month"
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 5. Execute with Exponential Backoff
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return content

            elif response.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            else:
                return f"Error: {response.status_code} - {response.text}"

        except Exception as e:
            return f"An unexpected error occurred: {e}"

    return "Failed to retrieve analysis after multiple attempts."


if __name__ == "__main__":
    # Example usage if run directly
    result = analyze_ticker("AAPL")
    print(result)
