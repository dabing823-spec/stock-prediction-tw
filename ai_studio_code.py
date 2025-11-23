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
import numpy as np

# -------------------------------------------
# 1. 基礎設定 & CSS
# -------------------------------------------
st.set_page_config(page_title="台股 ETF 戰情室 (Alpha 修正版)", layout="wide")
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
    .strategy-list { color: #ddd; font-size: 14px; line-height: 1.6; }
    .strategy-highlight { color: #ff7675; font-weight: bold; }
    .buy-signal { color: #55efc4; font-weight: bold; }
    .sell-signal { color: #ff7675; font-weight: bold; }
    
    /* Alpha 策略專用 */
    .alpha-long { border-left: 4px solid #55efc4; background-color: #2d3436; padding: 10px; border-radius: 5px;}
    .alpha-short { border-left: 4px solid #ff7675; background-color: #2d3436; padding: 10px; border-radius: 5px;}
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
        vix = yf.Ticker("^VIX").history(period="5d")
        if not vix.empty:
            curr = vix["Close"].iloc[-1]
            prev = vix["Close"].iloc[-2]
            indicators["VIX"] = {"val": round(curr, 2), "delta": round(curr - prev, 2)}
        else: indicators["VIX"] = {"val": "-", "delta": 0}

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
            txts = [td.get_text(strip=True) for td in tds]
            for s in txts:
                if rank is None and re.fullmatch(r"\d+", s): rank = int(s)
                elif rank and not code and re.fullmatch(r"\d{4}", s): code = s
                elif rank and code and not name and not re.fullmatch(r"\d+", s):
                    name = s; break
            if rank and code and name: rows.append({"排名": rank, "股票代碼": code, "股票名稱": name})
        
        if not rows:
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
        return pd.DataFrame(rows).sort_values("排名").head(limit)
    except Exception as e:
        st.error(f"抓取市值排名失敗: {e}"); return pd.DataFrame()

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

@st.cache_data(ttl=86400)
def get_dividend_yield_batch(codes):
    if not codes: return {}
    data = {}
    tickers_str = " ".join([f"{c}.TW" for c in codes])
    try:
        tickers = yf.Tickers(tickers_str)
        for c in codes:
            try:
                info = tickers.tickers[f"{c}.TW"].info
                dy = info.get('trailingAnnualDividendYield')
                if dy is None:
                    dy = info.get('dividendYield')
                    if dy and dy > 0.2: dy = 0 
                if dy is not None: data[c] = dy * 100
                else: data[c] = 0
            except: data[c] = 0
        return data
    except: return {}

# 批次取得產業資訊 (關鍵功能：篩選電子股)
@st.cache_data(ttl=86400)
def get_sector_batch(codes):
    if not codes: return {}
    sector_map = {}
    tickers_str = " ".join([f"{c}.TW" for c in codes])
    try:
        tickers = yf.Tickers(tickers_str)
        for c in codes:
            try:
                s = tickers.tickers[f"{c}.TW"].info.get('sector', 'Unknown')
                sector_map[c] = s
            except:
                sector_map[c] = 'Unknown'
        return sector_map
    except: return {}

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
                    
                    if turnover > 100000000: turnover_str = f"{turnover/100000000:.1f}億"
                    else: turnover_str = f"{turnover/10000:.0f}萬"
                    
                    change_pct = ((curr_price - prev_price) / prev_price) * 100
                    
                    vol_status = "🔥爆量" if (vol > avg_vol * 2 and vol > 1000) else "💧縮量" if vol < avg_vol * 0.6 else "➖正常"
                    
                    res[c] = {
                        "現價": f"{curr_price:.2f}",
                        "漲跌": f"{change_pct:+.2f}%",
                        "量能": f"{int(vol/1000)}張 ({vol_status})",
                        "成交值": turnover_str,
                        "raw_vol": vol,
                        "raw_change": change_pct,
                        "raw_turnover": turnover,
                        "raw_price": curr_price
                    }
                else:
                    res[c] = {"現價": "-", "漲跌": "-", "量能": "-", "成交值": "-", "raw_vol": 0, "raw_change": 0, "raw_turnover": 0, "raw_price": 0}
            except:
                res[c] = {"現價": "-", "漲跌": "-", "量能": "-", "成交值": "-", "raw_vol": 0, "raw_change": 0, "raw_turnover": 0, "raw_price": 0}
        return res
    except: return {}

@st.cache_data(ttl=3600)
def calculate_market_weights(codes):
    if not codes: return {}
    try:
        mcap_data = {}
        tickers = " ".join([f"{c}.TW" for c in codes])
        data = yf.Tickers(tickers)
        for c in codes:
            try:
                mcap = data.tickers[f"{c}.TW"].fast_info.market_cap
                if mcap: mcap_data[c] = mcap
            except: mcap_data[c] = 0
        total = sum(mcap_data.values())
        res = {}
        for c, mcap in mcap_data.items():
            w = (mcap/total)*100 if total > 0 else 0
            res[c] = {"市值": f"{mcap/100000000:.0f}億", "權重": f"{w:.2f}%", "raw_mcap": mcap}
        return res
    except: return {}

def enrich_df(df, codes_list, add_weight=False):
    if df.empty: return df
    info = get_advanced_stock_info(codes_list)
    
    df["現價"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("現價", "-"))
    df["漲跌幅"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("漲跌", "-"))
    df["成交量"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    df["成交值"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("成交值", "-"))
    df["raw_turnover"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("raw_turnover", 0))
    df["raw_vol"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("raw_vol", 0))
    df["連結代碼"] = df["股票代碼"].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
    
    if add_weight:
        weight_info = calculate_market_weights(codes_list)
        df["總市值"] = df["股票代碼"].map(lambda x: weight_info.get(x, {}).get("市值", "-"))
        df["權重(Top150)"] = df["股票代碼"].map(lambda x: weight_info.get(x, {}).get("權重", "-"))
    return df

def get_high_yield_schedule():
    m = date.today().month
    schedules = [
        {"name": "00878 (國泰)", "adj": [5, 11]},
        {"name": "0056 (元大)",  "adj": [6, 12]},
        {"name": "00919 (群益)", "adj": [5, 12]}
    ]
    active = [s for s in schedules if m in s["adj"]]
    return active

column_cfg = {
    "連結代碼": st.column_config.LinkColumn("代號", display_text=r"https://tw\.stock\.yahoo\.com/quote/(\d+)", width="small"),
    "raw_turnover": None, "raw_vol": None, "raw_yield": None
}

# --- 電子權值 Alpha 策略 (自動篩選版) ---
def calculate_tech_alpha_portfolio(total_capital, hedge_ratio, df_mcap):
    # 1. 取市值前 50 大
    top50_df = df_mcap.head(50).copy()
    top50_codes = top50_df["股票代碼"].tolist()
    
    # 2. 抓取產業類別
    sector_map = get_sector_batch(top50_codes)
    top50_df["Sector"] = top50_df["股票代碼"].map(sector_map)
    
    # 3. 篩選電子/半導體股 (Technology & Semiconductors)
    # 這裡將 "Technology" 與 "Semiconductors" 視為目標 Alpha 來源
    tech_df = top50_df[top50_df["Sector"].isin(["Technology", "Semiconductors", "Electronic Technology"])].copy()
    
    # 若過濾完沒東西 (預防性)，回傳空
    if tech_df.empty: return None, None, pd.DataFrame()
    
    # 4. 計算權重 (針對這群電子股重新分配)
    target_codes = tech_df["股票代碼"].tolist()
    weight_info = calculate_market_weights(target_codes)
    tech_df["raw_mcap"] = tech_df["股票代碼"].map(lambda x: weight_info.get(x, {}).get("raw_mcap", 0))
    
    total_mcap = tech_df["raw_mcap"].sum()
    tech_df["配置權重(%)"] = (tech_df["raw_mcap"] / total_mcap)
    
    # 5. 計算多方部位
    price_info = get_advanced_stock_info(target_codes)
    tech_df["現價"] = tech_df["股票代碼"].map(lambda x: price_info.get(x, {}).get("raw_price", 0))
    
    tech_df["分配金額"] = total_capital * tech_df["配置權重(%)"]
    tech_df["建議買進(股)"] = (tech_df["分配金額"] / tech_df["現價"]).fillna(0).astype(int)
    
    # 補欄位
    tech_df["股票名稱"] = tech_df["股票名稱"]
    tech_df["連結代碼"] = tech_df["股票代碼"].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
    
    # 調整顯示
    tech_df["配置權重(%)"] = (tech_df["配置權重(%)"] * 100).map(lambda x: f"{x:.2f}%")
    tech_df["分配金額"] = tech_df["分配金額"].map(lambda x: f"${int(x):,}")
    
    # 6. 計算空方部位 (避險)
    try:
        twii_price = yf.Ticker("^TWII").history(period="1d")["Close"].iloc[-1]
    except:
        twii_price = 23000
        
    short_value_needed = total_capital / hedge_ratio
    micro_contract_val = twii_price * 10
    num_micro = short_value_needed / micro_contract_val
    
    short_info = {
        "index_price": int(twii_price),
        "micro_val": int(micro_contract_val),
        "short_value": int(short_value_needed),
        "contracts": round(num_micro, 1)
    }
    
    return tech_df, short_info, top50_df[["股票名稱", "Sector"]]

# -------------------------------------------
# 5. 主程式 UI
# -------------------------------------------
st.title("🚀 台股 ETF 戰情室 (全攻略版)")
st.caption("0050 | MSCI | 高股息 | 電子 Alpha 對沖")

m_inds = get_market_indicators()
col1, col2, col3, col4 = st.columns(4)
with col1:
    v = m_inds.get("VIX", {})
    c = "red" if v.get('delta',0) > 0 else "green"
    st.markdown(f"""<div class="metric-card" style="border-left-color: #e74c3c;"><div class="metric-label">🇺🇸 VIX 恐慌指數</div><div class="metric-value">{v.get('val','-')} <span style="font-size:14px; color:{c};">({v.get('delta','-'):+.2f})</span></div></div>""", unsafe_allow_html=True)
with col2:
    st.markdown(f"""<div class="metric-card" style="border-left-color: #f1c40f;"><div class="metric-label">🇺🇸 CNN 恐懼貪婪</div><div class="metric-value" style="font-size:16px; padding-top:4px;"><a href="https://edition.cnn.com/markets/fear-and-greed" target="_blank" style="color:#fff;">點擊查看</a></div></div>""", unsafe_allow_html=True)
with col3:
    t = m_inds.get("TWII", {})
    c = "#2ecc71" if "站上" in t.get('status','') else "#e74c3c"
    st.markdown(f"""<div class="metric-card" style="border-left-color: {c};"><div class="metric-label">🇹🇼 加權指數</div><div class="metric-value">{t.get('val','-')}</div><div class="metric-label" style="color:{c};">{t.get('status','-')}</div></div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""<div class="metric-card" style="border-left-color: #9b59b6;"><div class="metric-label">📊 融資維持率</div><div class="metric-value" style="font-size:16px; padding-top:4px;"><a href="https://www.macromicro.me/charts/53117/taiwan-taiex-maintenance-margin" target="_blank" style="color:#fff;">MacroMicro 查詢</a></div></div>""", unsafe_allow_html=True)

st.divider()

with st.spinner("正在進行全市場掃描 (含殖利率數據)..."):
    df_mcap = fetch_taifex_rankings(limit=200)
    msci_codes = fetch_msci_list()
    holdings = {}
    for etf in ["0050", "0056", "00878", "00919"]:
        holdings[etf] = set(fetch_etf_holdings(etf))

    if df_mcap.empty: st.error("無法取得資料"); st.stop()

with st.sidebar:
    st.header("📡 市場雷達")
    active_hy = get_high_yield_schedule()
    if active_hy: st.error(f"🔥 **本月焦點:** {', '.join([h['name'] for h in active_hy])}")
    else: st.info("本月無大型調整")
    st.divider()
    if st.button("🔄 更新行情"): st.cache_data.clear(); st.rerun()
    st.caption(f"Update: {datetime.now().strftime('%H:%M')}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🇹🇼 0050 權值", "🌍 MSCI 外資", "💰 0056 高股息", "📊 全市場權重", "⚡ 電子 Alpha 對沖"])

# Tab 1: 0050
with tab1:
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📜 0050 吃豆腐戰法 (SOP)</div>
        <div class="strategy-list">
            1. <b>核心邏輯：</b> 市值前 40 名必定納入。利用「市值排名」提前預測。<br>
            2. <b>進場時機：</b> <span class="buy-signal">公告前 1 個月</span>。掃描下方 Rank ≤ 40 但未入選者。<br>
            3. <b>出場時機：</b> <span class="sell-signal">生效日當天 13:30</span>。掛「跌停價」倒貨給 ETF。<br>
            4. <b>避險：</b> 若公告前漲幅 > 20%，勿追。
        </div>
    </div>
    """, unsafe_allow_html=True)
    if holdings["0050"]:
        df_anl = df_mcap.head(100).copy()
        df_anl["in_0050"] = df_anl["股票名稱"].isin(holdings["0050"])
        must_in = df_anl[(df_anl["排名"] <= 40) & (~df_anl["in_0050"])]
        must_out = df_anl[(df_anl["排名"] > 60) & (df_anl["in_0050"])]
        all_codes = list(must_in["股票代碼"]) + list(must_out["股票代碼"])
        
        c1, c2 = st.columns(2)
        with c1:
            st.success("🟢 **潛在納入 (Rank ≤ 40)**")
            if not must_in.empty: st.dataframe(enrich_df(must_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
        with c2:
            st.error("🔴 **潛在剔除 (Rank > 60)**")
            if not must_out.empty: st.dataframe(enrich_df(must_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

# Tab 2: MSCI
with tab2:
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📜 MSCI 波動戰法 (SOP)</div>
        <div class="strategy-list">
            1. <b>核心邏輯：</b> 追蹤全球資金流，重點在「生效日尾盤爆量」。<br>
            2. <b>進場時機：</b> <span class="buy-signal">公布日早晨</span>。搶進意外黑馬。<br>
            3. <b>出場時機：</b> <span class="sell-signal">生效日 13:30</span>。掛「跌停價」賣出。<br>
            4. <b>避險：</b> 右側「剔除區」勿輕易接刀。
        </div>
    </div>
    """, unsafe_allow_html=True)
    if msci_codes:
        prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))]
        prob_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))]
        all_codes = list(prob_in["股票代碼"]) + list(prob_out["股票代碼"])
        
        c1, c2 = st.columns(2)
        with c1:
            st.success("🟢 **潛在納入 (外資買盤)**")
            if not prob_in.empty: st.dataframe(enrich_df(prob_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
        with c2:
            st.error("🔴 **潛在剔除 (外資賣盤)**")
            if not prob_out.empty: st.dataframe(enrich_df(prob_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

# Tab 3: 0056
with tab3:
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📜 0056 高股息戰法 (元大官方邏輯)</div>
        <div class="strategy-list">
            1. <b>選股池：</b> 市值前 150 大。<br>
            2. <b>門檻：</b> 殖利率排名 <span class="buy-signal">前 35 納入</span>；<span class="sell-signal">跌出 66 剔除</span>。<br>
            3. <b>操作：</b> 觀察下方列表，找<b>殖利率高</b>且<b>未入選</b>者。<br>
            4. <b>出場：</b> 0056 有 5 天換股期，可分批調節。
        </div>
    </div>
    """, unsafe_allow_html=True)
    mid_cap = df_mcap[(df_mcap["排名"] >= 50) & (df_mcap["排名"] <= 150)].copy()
    mid_cap["已入選 ETF"] = mid_cap["股票名稱"].apply(lambda x: ", ".join([e for e in holdings if x in holdings[e]]))
    codes = list(mid_cap["股票代碼"])
    
    with st.spinner("計算殖利率排行中..."):
        yield_data = get_dividend_yield_batch(codes)
    
    mid_cap["raw_yield"] = mid_cap["股票代碼"].map(lambda x: yield_data.get(x, 0))
    mid_cap["殖利率(%)"] = mid_cap["raw_yield"].apply(lambda x: f"{x:.2f}%")
    
    sort_method = st.radio("🔍 掃描模式：", ["💰 殖利率排行 (抓高息)", "🔥 量能爆發 (抓偷跑)", "💎 尚未入選 (抓遺珠)"])
    df_show = enrich_df(mid_cap, codes)
    
    if "殖利率" in sort_method: df_show = df_show.sort_values("raw_yield", ascending=False).head(30)
    elif "量能" in sort_method: df_show = df_show.sort_values("raw_vol", ascending=False).head(30)
    else: df_show = df_show[df_show["已入選 ETF"] == ""].sort_values("排名").head(30)
    
    st.dataframe(df_show[["排名","連結代碼","股票名稱","殖利率(%)","已入選 ETF","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

# Tab 4: 全市場權重
with tab4:
    st.markdown("""<div class="strategy-box"><div class="strategy-title">📊 全市場市值權重排行 (Top 150)</div><div class="strategy-list">台股多空地圖。前 150 檔佔大盤 90% 市值。</div></div>""", unsafe_allow_html=True)
    top150 = df_mcap.head(150).copy()
    codes = list(top150["股票代碼"])
    with st.spinner("計算權重中..."):
        df_150 = enrich_df(top150, codes, add_weight=True)
    st.dataframe(df_150[["排名","連結代碼","股票名稱","權重(Top150)","總市值","現價","成交值","漲跌幅"]], hide_index=True, column_config=column_cfg)

# Tab 5: 電子權值 Alpha (Auto-Search)
with tab5:
    st.markdown("""<div class="strategy-box"><div class="strategy-title">🤖 電子權值 Alpha 對沖策略 (自動篩選)</div><div class="strategy-list"><b>邏輯：</b> 自動從 Top 50 市值中，篩選出電子/半導體股做多，同時放空台指期，賺取電子股優於大盤的 Alpha。</div></div>""", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        capital = st.number_input("總投資金額 (TWD)", min_value=100000, value=1000000, step=50000)
        hedge_ratio = st.slider("多空比率 (Long/Short Ratio)", 0.8, 1.5, 1.0, 0.1)
        st.info(f"💡 每買 {int(capital):,} 元股票，需放空約 {int(capital/hedge_ratio):,} 元期貨。")
    with c2:
        with st.spinner("正在篩選 Top 50 電子/半導體股..."):
            ai_df, short_info, debug_df = calculate_tech_alpha_portfolio(capital, hedge_ratio, df_mcap)
    
    if ai_df is not None and short_info is not None:
        col_long, col_short = st.columns(2)
        with col_long:
            st.markdown(f"### 🟢 多方部位 (現貨: ${int(capital):,})")
            st.dataframe(ai_df[["股票名稱", "Sector", "連結代碼", "現價", "配置權重(%)", "分配金額", "建議買進(股)"]], hide_index=True, column_config=column_cfg)
            with st.expander("查看原始產業分類 (Debug)"):
                st.dataframe(debug_df, hide_index=True)
        with col_short:
            st.markdown(f"### 🔴 空方部位 (期貨: ${short_info['short_value']:,})")
            st.markdown(f"""<div class="alpha-short"><h4>避險標的：微台 (TMF)</h4><ul><li>當前指數：<b>{short_info['index_price']}</b></li><li>合約價值：<b>${short_info['micro_val']:,}</b></li><li>建議放空：<b style='color:#ff7675; font-size:24px;'>{short_info['contracts']} 口</b></li></ul></div>""", unsafe_allow_html=True)
