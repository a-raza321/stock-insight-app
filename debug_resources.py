import streamlit as st
import psutil
import os

def get_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return mem_info.rss / (1024 * 1024)  # Convert to MB

st.title("System Health Check")
mem = get_memory_usage()

st.metric("Current Memory Usage", f"{mem:.2f} MB")

if mem > 800:
    st.warning("⚠️ You are close to the 1GB Streamlit Cloud limit. Your browsers are likely causing this.")

st.write("### Active Background Processes")
# This will show you if Selenium/Playwright/Chrome are still running in the background
for proc in psutil.process_iter(['pid', 'name']):
    st.write(proc.info)
