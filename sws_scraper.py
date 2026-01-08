import os
import time
import warnings
import sys
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager

warnings.filterwarnings("ignore")

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    return driver

def search_company(driver, company_name):
    try:
        driver.get("https://simplywall.st/")
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='search-search-field']"))
        )
        search_box.send_keys(company_name)
        time.sleep(3)
        
        suggestion = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/stocks/') and not(contains(@href, 'market-cap'))][1]"))
        )
        suggestion.click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        return driver.current_url
    except:
        return None

def scrape_risk_rewards_sws(company_name):
    driver = None
    data = {"company": "", "rewards": [], "risks": []}
    
    try:
        driver = get_driver()
        url = search_company(driver, company_name)
        if not url: return data

        time.sleep(2)
        driver.execute_script("window.scrollBy(0, 800)")
        
        try:
            data["company"] = driver.find_element(By.TAG_NAME, "h1").text.strip()
        except: pass

        all_links = driver.find_elements(By.XPATH, "//blockquote//a | //div[contains(@class, 'highlight')]//a")
        
        risk_keywords = ["debt", "leverage", "liabilities", "unprofitable", "loss", "volatile", "dilut", "insider selling", "decline", "lawsuit", "risk"]
        reward_keywords = ["growth", "earnings", "profit", "forecast", "undervalued", "outperform", "dividend", "market leader"]

        for link in all_links:
            text = link.text.strip()
            if len(text) < 10: continue
            text_l = text.lower()
            
            if any(k in text_l for k in risk_keywords):
                if text not in data["risks"]: data["risks"].append(text)
            elif any(k in text_l for k in reward_keywords):
                if text not in data["rewards"]: data["rewards"].append(text)
                
        return data
    finally:
        if driver: driver.quit()

def get_gemini_analysis(data):
    api_key = "" # Add your key in st.secrets
    model = "gemini-2.5-flash-preview-09-2025"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    prompt = f"Analyse financial rewards and risks for {data['company']}. Rewards: {data['rewards']}. Risks: {data['risks']}. Summarize in bullet points < 15 words."
    
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        return resp.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Analysis unavailable."
