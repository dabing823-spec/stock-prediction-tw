import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import io
import chardet
from datetime import date, datetime, timedelta
import urllib3
import yfinance as yf
import time

# -------------------------------------------
# 1. 基礎設定 & CSS 視覺優化 (期天資訊風格)
# -------------------------------------------
st.set_page_config(page_title="台股戰情室 (旗艦版)", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 自定義 CSS：深色背景、紅漲綠跌卡片、緊湊排版
st.markdown("""
<style>
    /* 全局背景微調 */
    .stApp {
        background-color: #0e1117;
    }
    /* 指標卡片樣式 */
    .metric-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #FF4B4B;
        text-align: center;
    }
    .metric-label { font-size: 14px; color: #aaa; }
    .metric-value { font-size: 24px; font-weight: bold; color: #fff; }
    .metric-delta { font-size: 14px; }
    
    /* 股票 Heatmap 卡片 */
    .stock-card {
        padding: 10px;
        border-radius: 5px;
        color: white;
        text-align: center;
        margin-bottom: 10px;
        font-family: "Microsoft JhengHei", sans-serif;
        transition: transform 0.2s;
    }
    .stock-card:hover { transform: scale(1.05); }
    .stock-up { background-color: #d63031; border: 1px solid #ff7675; } /* 台股紅漲 */
    .stock-down { background-color: #00b894; border: 1px solid #55efc4; } /* 台股綠跌 */
    .stock-flat { background-color: #636e72; border: 1px solid #b2bec3; }
    
    .stock-rank { font-size: 12px; opacity: 0.8; }
    .stock-name { font-size: 18px; font-weight: bold; margin: 5px 0; }
    .stock-price { font-size: 16px; }
    .stock-detail { font-size: 12px; opacity: 0.9; margin-top: 5px;}
    
    /* 策略看板 */
    .strategy-box {
        background-color: #2d3436;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #4b4b4b;
        margin-bottom: 20px;
    }
    .strategy-title { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 10px; }
    .strategy-list { color: #dfe6e9; font-size: 14px; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -------------------------------------------
# 2. 大盤環境指標 (New!)
# -------------------------------------------
@st.cache_data(ttl=300)
def get_market_indicators():
    indicators = {}
    
    # 1. VIX (Yahoo)
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if not hist.empty:
            curr = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            indicators["VIX"] = {"val": round(curr, 2), "delta": round(curr - prev, 2)}
    except: indicators["VIX"] = {"val": "-", "delta": 0}

    # 2. CNN Fear & Greed (API 模擬 / 簡易抓取)
    # 因 CNN API 經常變動，這裡使用 VIX 與美股走勢做簡單推估，或顯示連結
    # 這裡為了穩定性，我們先顯示連結，並用 SPY 波動做簡單情緒標記
    try:
        spy = yf.Ticker("SPY").history(period="5d")
        spy_chg = (spy["Close"].iloc[-1] - spy["Close"].iloc[-5]) / spy["Close"].iloc[-5]
        fng_status = "貪婪" if spy_chg > 0.02 else "恐懼" if spy_chg < -0.02 else "中立"
        indicators["CNN"] = {"val": fng_status, "desc": "美股情緒"}
    except: indicators["CNN"] = {"val": "-", "desc": "美股情緒"}

    # 3. 加權指數與均線 (Yahoo)
    try:
        twii = yf.Ticker("^TWII")
        hist = twii.history(period="3mo") # 抓一季算均線
        if not hist.empty:
            curr = hist["Close"].iloc[-1]
            ma20 = hist["Close"].tail(20).mean() # 月線
            ma60 = hist["Close"].tail(60).mean() # 季線
            
            status = []
            if curr > ma20: status.append("站上月線")
            else: status.append("跌破月線")
            
            if curr > ma60: status.append("站上季線")
            else: status.append("跌破季線")
            
            indicators["TWII"] = {
                "val": int(curr),
                "ma20": int(ma20),
                "ma60": int(ma60),
                "status": " | ".join(status)
            }
    except: indicators["TWII"] = {"val": "-", "status": "無法取得"}

    return indicators

# -------------------------------------------
# 3. 數據抓取核心 (維持高效)
# -------------------------------------------
@st.cache_data(ttl=3600)
def fetch_taifex_rankings(limit=200):
    url = "https://www.taifex.com.tw/cht/9/futuresQADetail"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        encoding = chardet.detect(resp.content)["encoding"] or "utf-8"
        html_text = resp.content.decode(encoding, errors="ignore")
        dfs = pd.read_html(io.StringIO(html_text), flavor=["lxml", "html5lib"])
        for df in dfs:
            cols = "".join([str(c) for c in df.columns])
            if "排名" in cols and ("名稱" in cols or "代號" in cols):
                df.columns = [str(c).replace(" ", "") for c in df.columns]
                col_map = {c: ("排名" if "排名" in c else "股票代碼" if "代" in c else "股票名稱") for c in df.columns if any(x in c for x in ["排名","代","名"])}
                df = df.rename(columns=col_map)
                df = df[pd.to_numeric(df["排名"], errors='coerce').notnull()]
                df["排名"] = df["排名"].astype(int)
                df["股票代碼"] = df["股票代碼"].astype(str).str.extract(r'(\d{4})')[0]
                return df.sort_values("排名").head(limit)
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_msci_list():
    url = "https://stock.capital.com.tw/z/zm/zmd/zmdc.djhtm?MSCI=0"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        guess = chardet.detect(resp.content)
        encoding = guess['encoding'] if guess['encoding'] else 'cp950'
        html_text = resp.content.decode(encoding, errors="ignore")
        codes = set(re.findall(r"Link2Stk\('(\d{4})'\)", html_text))
        if not codes: codes = set(re.findall(r"\b(\d{4})\b", BeautifulSoup(html_text, "lxml").get_text()))
        return sorted(list(codes))
    except: return []

@st.cache_data(ttl=3600)
def fetch_etf_holdings(etf_code="0050"):
    url = f"https://www.moneydj.com/ETF/X/Basic/Basic0007a.xdjhtm?etfid={etf_code}.TW"
    try:
        time.sleep(0.5)
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        resp.encoding = resp.apparent_encoding or "utf-8"
        dfs = pd.read_html(io.StringIO(resp.text), flavor="lxml")
        names = []
        for df in dfs:
            cols = [str(c[-1] if isinstance(df.columns, pd.MultiIndex) else c).strip() for c in df.columns]
            df.columns = cols
            target = next((c for c in cols if "名稱" in c), None)
            if target: names.extend(df[target].astype(str).str.strip().tolist())
        return list(set([n for n in names if n not in ['nan','']]))
    except: return []

@st.cache_data(ttl=300)
def get_advanced_stock_info(codes):
    if not codes: return {}
    try:
        tickers = " ".join([f"{c}.TW" for c in codes])
        data = yf.Tickers(tickers)
        res = {}
        for c in codes:
            try:
                t = data.tickers[f"{c}.TW"]
                h = t.history(period="5d")
                if not h.empty:
                    curr_price = h["Close"].iloc[-1]
                    prev_price = h["Close"].iloc[-2] if len(h) > 1 else curr_price
                    vol = h["Volume"].iloc[-1]
                    avg_vol = h["Volume"].mean()
                    turnover = curr_price * vol
                    change_pct = ((curr_price - prev_price) / prev_price) * 100
                    
                    if turnover > 100000000: turnover_str = f"{turnover/100000000:.1f}億"
                    else: turnover_str = f"{turnover/10000:.0f}萬"

                    if vol > (avg_vol * 2) and vol > 1000: vol_status = "🔥爆量"
                    elif vol < (avg_vol * 0.6): vol_status = "💧縮量"
                    else: vol_status = "➖"
                    
                    res[c] = {
                        "現價": curr_price,
                        "漲跌幅": change_pct,
                        "量能狀態": vol_status,
                        "成交值": turnover_str,
                        "成交量": int(vol/1000),
                        "raw_vol": vol
                    }
                else: res[c] = None
            except: res[c] = None
        return res
    except: return {}

# -------------------------------------------
# 4. 視覺化組件 (Heatmap Card)
# -------------------------------------------
def render_heatmap_grid(df, codes_list):
    """將 DataFrame 渲染成紅綠色塊的網格"""
    if df.empty:
        st.info("無符合條件標的")
        return

    info = get_advanced_stock_info(codes_list)
    
    # 建立 4 欄網格
    cols = st.columns(4)
    
    for index, row in df.iterrows():
        code = row['股票代碼']
        name = row['股票名稱']
        rank = row['排名']
        
        stock_data = info.get(code)
        
        if stock_data:
            price = stock_data['現價']
            chg = stock_data['漲跌幅']
            vol_note = stock_data['量能狀態']
            val_note = stock_data['成交值']
            
            # 決定顏色 (台股紅漲綠跌)
            if chg > 0: card_class = "stock-up"
            elif chg < 0: card_class = "stock-down"
            else: card_class = "stock-flat"
            
            chg_str = f"{chg:+.2f}%"
        else:
            price = "-"
            chg_str = "-"
            vol_note = ""
            val_note = ""
            card_class = "stock-flat"

        # Yahoo 連結
        link = f"https://tw.stock.yahoo.com/quote/{code}"

        # HTML 卡片
        html = f"""
        <a href="{link}" target="_blank" style="text-decoration:none;">
            <div class="stock-card {card_class}">
                <div class="stock-rank">Rank {rank}</div>
                <div class="stock-name">{name} ({code})</div>
                <div class="stock-price">{price} ({chg_str})</div>
                <div class="stock-detail">{vol_note} | {val_note}</div>
            </div>
        </a>
        """
        
        # 依序放入欄位
        with cols[index % 4]:
            st.markdown(html, unsafe_allow_html=True)

# -------------------------------------------
# 5. 主程式
# -------------------------------------------

# --- A. 大盤儀表板 (Dashboard) ---
st.title("🚀 台股戰情室 (旗艦操盤版)")
st.caption("全方位監控：VIX | CNN | 大盤均線 | 融資維持率 | ETF 資金流向")

m_inds = get_market_indicators()

# 顯示四大指標
col1, col2, col3, col4 = st.columns(4)

with col1:
    vix = m_inds["VIX"]
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #e74c3c;">
        <div class="metric-label">🇺🇸 美國 VIX 恐慌指數</div>
        <div class="metric-value">{vix['val']}</div>
        <div class="metric-delta" style="color: {'red' if vix['delta']>0 else 'green'};">{vix['delta']:+.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    cnn = m_inds["CNN"]
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #f1c40f;">
        <div class="metric-label">🇺🇸 CNN 恐懼貪婪 (Proxy)</div>
        <div class="metric-value">{cnn['val']}</div>
        <div class="metric-delta"><a href="https://edition.cnn.com/markets/fear-and-greed" target="_blank" style="color: #3498db;">點擊查看原圖</a></div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    tw = m_inds["TWII"]
    color = "#2ecc71" if "站上" in tw['status'] else "#e74c3c"
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {color};">
        <div class="metric-label">🇹🇼 加權指數 (月/季線)</div>
        <div class="metric-value">{tw['val']}</div>
        <div class="metric-delta" style="font-size:12px;">{tw['status']}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    # 融資維持率按鈕 (因無法精確抓取，提供直連)
    st.markdown("""
    <div class="metric-card" style="border-left-color: #9b59b6;">
        <div class="metric-label">📊 融資維持率 (>155%安全)</div>
        <div class="metric-value" style="font-size:18px; margin-top:5px;">
            <a href="https://goodinfo.tw/tw/StockMarketSummary.asp" target="_blank" style="color: #fff; text-decoration: underline;">
            點擊查詢 Goodinfo
            </a>
        </div>
        <div class="metric-delta">觀察大盤是否 > 季線</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- B. 資料載入 ---
with st.spinner("正在掃描市場籌碼..."):
    df_mcap = fetch_taifex_rankings(limit=200)
    msci_codes = fetch_msci_list()
    holdings = {}
    for etf in ["0050", "0056", "00878", "00919"]:
        holdings[etf] = set(fetch_etf_holdings(etf))

if df_mcap.empty:
    st.error("無法取得即時資料"); st.stop()

# --- C. 戰情室分頁 ---
tab1, tab2, tab3 = st.tabs(["🇹🇼 0050 吃豆腐", "🌍 MSCI 波動戰", "💰 高股息/中型 100"])

# ==================================================
# Tab 1: 0050 (含策略看板)
# ==================================================
with tab1:
    # 策略看板
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📜 0050 吃豆腐操作 SOP</div>
        <div class="strategy-list">
            1. <b>觀念：</b> 0050 為被動 ETF，生效日必須買齊成分股。我們的獲利來自「提供流動性」。<br>
            2. <b>進場 (潛在納入)：</b> 觀察下方綠色卡片，若成交量縮 (💧縮量) 且股價穩，可於生效日當天 <b>13:24</b> 佈局。<br>
            3. <b>出場 (必勝點)：</b> <b>13:30 最後一盤</b>，掛 <b>「跌停價」</b> 賣出。<br>
               (註：掛跌停是為了確保優先成交，系統會撮合在當下的市價/高價，不會真的賣在跌停)。<br>
            4. <b>警告：</b> 若公布前股價已大漲 >20%，利多出盡機率高，勿追。
        </div>
    </div>
    """, unsafe_allow_html=True)

    if holdings["0050"]:
        df_anl = df_mcap.head(100).copy()
        df_anl["in_0050"] = df_anl["股票名稱"].isin(holdings["0050"])
        
        must_in = df_anl[(df_anl["排名"] <= 40) & (~df_anl["in_0050"])]
        must_out = df_anl[(df_anl["排名"] > 60) & (df_anl["in_0050"])]
        
        st.subheader("🟢 潛在納入 (買點觀察)")
        render_heatmap_grid(must_in, list(must_in["股票代碼"]))
        
        st.subheader("🔴 潛在剔除 (避開/放空)")
        render_heatmap_grid(must_out, list(must_out["股票代碼"]))
    else:
        st.warning("0050 資料讀取失敗")

# ==================================================
# Tab 2: MSCI (含策略看板)
# ==================================================
with tab2:
    # 策略看板
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📜 MSCI 季度調整 SOP</div>
        <div class="strategy-list">
            1. <b>特性：</b> 外資被動買盤極大，主要影響「最後一盤」成交量 (爆大量)。<br>
            2. <b>意外黑馬：</b> 若下方出現「高機率納入」但市場未預期，公布日開盤可搶短 (當沖)。<br>
            3. <b>持股處理：</b> 若手中持有納入股，建議於 <b>生效日 13:30</b> 掛 <b>「跌停價」</b> 賣出，享受外資抬轎。<br>
            4. <b>風險：</b> 右側「潛在剔除」區的股票，外資倒貨時間長，切勿隨意接刀。
        </div>
    </div>
    """, unsafe_allow_html=True)

    if msci_codes:
        prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))]
        prob_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))]
        
        st.subheader("🟢 潛在納入 (高機率)")
        render_heatmap_grid(prob_in, list(prob_in["股票代碼"]))
        
        st.subheader("🔴 潛在剔除 (高風險)")
        render_heatmap_grid(prob_out, list(prob_out["股票代碼"]))

# ==================================================
# Tab 3: 高股息中型股 (含策略看板)
# ==================================================
with tab3:
    # 策略看板
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📜 中型股 (0056/00878) 偷跑 SOP</div>
        <div class="strategy-list">
            1. <b>目標：</b> 鎖定排名 50~150 名，且尚未入選高股息 ETF 的股票。<br>
            2. <b>訊號：</b> 下方卡片出現 <b>「🔥爆量」</b> 且 <b>「成交值(億)」</b> 很大，代表投信正在偷跑。<br>
            3. <b>操作：</b> 在公告前 1 個月進場，公告利多見報時出場。<br>
            4. <b>篩選：</b> 請善用下方的「資金熱度」排序，找出大人在顧的股票。
        </div>
    </div>
    """, unsafe_allow_html=True)

    mid_cap = df_mcap[(df_mcap["排名"] >= 50) & (df_mcap["排名"] <= 150)].copy()
    
    def check_status(name):
        tags = []
        if name in holdings["0056"]: tags.append("0056")
        if name in holdings["00878"]: tags.append("00878")
        if name in holdings["00919"]: tags.append("00919")
        return ", ".join(tags) if tags else "-"
    mid_cap["已入選 ETF"] = mid_cap["股票名稱"].apply(check_status)
    
    # 篩選器
    sort_type = st.radio("🔍 掃描模式", ["💰 資金熱度 (抓大人)", "🔥 量能爆發 (抓偷跑)", "💎 尚未入選 (抓遺珠)"], horizontal=True)
    
    # 為了排序需要先抓取部分資料 (這裡抓前 50 檔中型股做示範，避免 API 爆掉)
    # 實際量化操作會掃描全部，這裡為求速度掃描 Rank 50-120
    scan_range = mid_cap.head(70) 
    info = get_advanced_stock_info(list(scan_range["股票代碼"]))
    
    scan_range["raw_turnover"] = scan_range["股票代碼"].map(lambda x: info.get(x, {}).get("raw_vol", 0) * info.get(x, {}).get("現價", 0))
    scan_range["raw_vol"] = scan_range["股票代碼"].map(lambda x: info.get(x, {}).get("raw_vol", 0))
    
    if "資金" in sort_type:
        final_df = scan_range.sort_values("raw_turnover", ascending=False).head(20)
    elif "量能" in sort_type:
        final_df = scan_range.sort_values("raw_vol", ascending=False).head(20)
    else:
        final_df = scan_range[scan_range["已入選 ETF"] == "-"].head(20)
        
    render_heatmap_grid(final_df, list(final_df["股票代碼"]))
