import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import io
import chardet
from datetime import date, datetime
import urllib3
import yfinance as yf
import time

# -------------------------------------------
# 1. 基礎設定 & CSS
# -------------------------------------------
st.set_page_config(page_title="台股 ETF 戰情室 (操盤旗艦版)", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 自定義 CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #262730;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #FF4B4B;
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-label { font-size: 13px; color: #aaa; }
    .metric-value { font-size: 20px; font-weight: bold; color: #fff; }
    
    .strategy-box {
        background-color: #1e2329;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #333;
        margin-bottom: 20px;
    }
    .strategy-title { color: #f1c40f; font-size: 16px; font-weight: bold; margin-bottom: 8px; }
    .strategy-list { color: #ddd; font-size: 14px; line-height: 1.5; }
    .strategy-highlight { color: #ff7675; font-weight: bold; }
    .buy-signal { color: #55efc4; font-weight: bold; }
    .sell-signal { color: #ff7675; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -------------------------------------------
# 2. 大盤環境指標
# -------------------------------------------
@st.cache_data(ttl=300)
def get_market_indicators():
    indicators = {}
    try:
        # VIX
        vix = yf.Ticker("^VIX").history(period="5d")
        if not vix.empty:
            curr = vix["Close"].iloc[-1]
            prev = vix["Close"].iloc[-2]
            indicators["VIX"] = {"val": round(curr, 2), "delta": round(curr - prev, 2)}
        else: indicators["VIX"] = {"val": "-", "delta": 0}

        # 加權指數 (月季線)
        twii = yf.Ticker("^TWII").history(period="3mo")
        if not twii.empty:
            curr = twii["Close"].iloc[-1]
            ma20 = twii["Close"].tail(20).mean()
            ma60 = twii["Close"].tail(60).mean()
            status_list = []
            status_list.append("站上月線" if curr > ma20 else "跌破月線")
            status_list.append("站上季線" if curr > ma60 else "跌破季線")
            indicators["TWII"] = {"val": int(curr), "status": " | ".join(status_list)}
        else: indicators["TWII"] = {"val": "-", "status": "無法取得"}
        
    except: 
        indicators = {"VIX": {"val":"-", "delta":0}, "TWII": {"val":"-", "status":"-"}}
    return indicators

# -------------------------------------------
# 3. 數據抓取核心
# -------------------------------------------

@st.cache_data(ttl=3600)
def fetch_taifex_rankings(limit=200):
    url = "https://www.taifex.com.tw/cht/9/futuresQADetail"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        encoding = chardet.detect(resp.content)["encoding"] or resp.apparent_encoding
        html_text = resp.content.decode(encoding, errors="ignore")
        soup = BeautifulSoup(html_text, "lxml")
        rows = []
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if not tds: continue
            rank, code, name = None, None, None
            txts = [td.get_text(strip=True) for td in tds
