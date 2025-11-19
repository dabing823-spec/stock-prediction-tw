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
# 1. 基礎設定
# -------------------------------------------
st.set_page_config(page_title="台股 ETF 戰情室 (Pro)", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -------------------------------------------
# 2. 數據抓取核心
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
        clean_names = list(set([n for n in names if n not in ['nan','']]))
        return clean_names
    except: return []

@st.cache_data(ttl=300)
def get_advanced_stock_info(codes):
    """取得量價資訊 (含成交值計算)"""
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
                    
                    # 計算成交值 (價格 * 成交量)
                    turnover = curr_price * vol
                    
                    # 格式化成交值
                    if turnover > 100000000:
                        turnover_str = f"{turnover/100000000:.1f}億"
                    else:
                        turnover_str = f"{turnover/10000:.0f}萬"
                    
                    change_pct = ((curr_price - prev_price) / prev_price) * 100
                    
                    # 量能訊號
                    if vol > (avg_vol * 2) and vol > 1000:
                        vol_status = "🔥爆量"
                    elif vol < (avg_vol * 0.6):
                        vol_status = "💧縮量"
                    else:
                        vol_status = "➖正常"
                    
                    res[c] = {
                        "現價": f"{curr_price:.2f}",
                        "漲跌": f"{change_pct:+.2f}%",
                        "量能": f"{int(vol/1000)}張 ({vol_status})",
                        "成交值": turnover_str,
                        "raw_vol": vol,
                        "raw_change": change_pct,
                        "raw_turnover": turnover
                    }
                else:
                    res[c] = {"現價": "-", "漲跌": "-", "量能": "-", "成交值": "-", "raw_vol": 0, "raw_change": 0, "raw_turnover": 0}
            except:
                res[c] = {"現價": "-", "漲跌": "-", "量能": "-", "成交值": "-", "raw_vol": 0, "raw_change": 0, "raw_turnover": 0}
        return res
    except: return {}

# -------------------------------------------
# 3. 介面輔助函式
# -------------------------------------------
def enrich_df(df, codes_list):
    if df.empty: return df
    info = get_advanced_stock_info(codes_list)
    df["現價"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("現價", "-"))
    df["漲跌幅"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("漲跌", "-"))
    df["成交量"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    df["成交值"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("成交值", "-"))
    
    # 隱藏排序用的 raw data，但保留在 DataFrame 中
    df["raw_turnover"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("raw_turnover", 0))
    
    # 建立 Yahoo 連結 (之後用 column_config 渲染)
    df["連結代碼"] = df["股票代碼"].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
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

# 顯示設定 (共用)
column_cfg = {
    "連結代碼": st.column_config.LinkColumn(
        "代號", 
        display_text=r"https://tw\.stock\.yahoo\.com/quote/(\d+)", # Regex 提取代碼顯示
        help="點擊查看 Yahoo 個股資訊"
    ),
    "raw_turnover": None, # 隱藏
    "raw_vol": None,
    "raw_change": None
}

# -------------------------------------------
# 4. 主程式
# -------------------------------------------
st.title("📈 台股 ETF 戰情室 (Pro)")
st.caption("點擊代號可連結至 Yahoo 股市 | 涵蓋 0050, MSCI, 高股息中型股")

with st.spinner("正在掃描全市場量價與資金流向..."):
    df_mcap = fetch_taifex_rankings(limit=200)
    msci_codes = fetch_msci_list()
    
    holdings = {}
    for etf in ["0050", "0056", "00878", "00919"]:
        holdings[etf] = set(fetch_etf_holdings(etf))

    if df_mcap.empty:
        st.error("無法取得市值排名"); st.stop()

# 側邊欄
with st.sidebar:
    st.header("🗓️ 調整行事曆")
    active_hy = get_high_yield_schedule()
    if active_hy:
        st.error(f"🔥 本月重點: {', '.join([h['name'] for h in active_hy])}")
    else:
        st.info("本月無大型高股息調整")
        st.text("下波: 12月 (0056, 00919)")
    
    st.divider()
    if st.button("🔄 更新行情"):
        st.cache_data.clear()
        st.rerun()

tab1, tab2, tab3 = st.tabs(["🇹🇼 0050 權值對決", "🌍 MSCI 外資對決", "💰 高股息/中型 100"])

# ==================================================
# Tab 1: 0050
# ==================================================
with tab1:
    st.markdown("### 0050 調整預測")
    if holdings["0050"]:
        df_anl = df_mcap.head(100).copy()
        df_anl["in_0050"] = df_anl["股票名稱"].isin(holdings["0050"])
        
        must_in = df_anl[(df_anl["排名"] <= 40) & (~df_anl["in_0050"])]
        candidate_in = df_anl[(df_anl["排名"] > 40) & (df_anl["排名"] <= 50) & (~df_anl["in_0050"])]
        
        in_list = df_mcap[df_mcap["股票名稱"].isin(holdings["0050"])]
        must_out = in_list[in_list["排名"] > 60]
        danger_out = in_list[(in_list["排名"] > 40) & (in_list["排名"] <= 60)].sort_values("排名", ascending=False)
        
        all_codes = list(must_in["股票代碼"]) + list(candidate_in["股票代碼"]) + list(must_out["股票代碼"]) + list(danger_out["股票代碼"])
        
        c1, c2 = st.columns(2)
        with c1:
            st.success("🟢 **潛在納入區**")
            if not must_in.empty:
                st.markdown("**🔥 必然納入 (Rank ≤ 40)**")
                df_show = enrich_df(must_in, all_codes)
                st.dataframe(df_show[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            
            if not candidate_in.empty:
                st.markdown("**⚔️ 關鍵挑戰者 (Rank 41-50)**")
                df_show = enrich_df(candidate_in, all_codes)
                st.dataframe(df_show[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

        with c2:
            st.error("🔴 **潛在剔除區**")
            if not must_out.empty:
                st.markdown("**👋 必然剔除 (Rank > 60)**")
                df_show = enrich_df(must_out, all_codes)
                st.dataframe(df_show[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            
            if not danger_out.empty:
                st.markdown("**⚠️ 危險邊緣 (Rank 41-60)**")
                df_show = enrich_df(danger_out, all_codes)
                st.dataframe(df_show[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
    else:
        st.warning("0050 資料讀取失敗")

# ==================================================
# Tab 2: MSCI
# ==================================================
with tab2:
    st.markdown("### MSCI 調整預測")
    if msci_codes:
        prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))]
        watch_in = df_mcap[(df_mcap["排名"] > 85) & (df_mcap["排名"] <= 100) & (~df_mcap["股票代碼"].isin(msci_codes))]
        prob_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))]
        
        all_codes = list(prob_in["股票代碼"]) + list(watch_in["股票代碼"]) + list(prob_out["股票代碼"])
        
        c1, c2 = st.columns(2)
        with c1:
            st.success("🟢 **潛在納入區**")
            if not prob_in.empty:
                st.markdown("**🔥 高機率納入 (Rank ≤ 85)**")
                df_show = enrich_df(prob_in, all_codes)
                st.dataframe(df_show[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            
            if not watch_in.empty:
                st.markdown("**🧐 邊緣觀察 (Rank 86-100)**")
                df_show = enrich_df(watch_in, all_codes)
                st.dataframe(df_show[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

        with c2:
            st.error("🔴 **潛在剔除區**")
            if not prob_out.empty:
                st.markdown("**👋 潛在剔除 (Rank > 100)**")
                df_show = enrich_df(prob_out, all_codes)
                st.dataframe(df_show[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
    else:
        st.warning("MSCI 資料讀取失敗")

# ==================================================
# Tab 3: 高股息/中型 100
# ==================================================
with tab3:
    st.markdown("### 💰 高股息/中型股戰場")
    st.markdown("鎖定 **市值 50~150 名**，結合 **資金熱度 (成交值)** 判斷。")
    
    mid_cap = df_mcap[(df_mcap["排名"] >= 50) & (df_mcap["排名"] <= 150)].copy()
    
    def check_status(name):
        tags = []
        if name in holdings["0056"]: tags.append("0056")
        if name in holdings["00878"]: tags.append("00878")
        if name in holdings["00919"]: tags.append("00919")
        return ", ".join(tags) if tags else "-"
    
    mid_cap["已入選 ETF"] = mid_cap["股票名稱"].apply(check_status)
    
    # 抓取行情
    codes = list(mid_cap["股票代碼"])
    info = get_advanced_stock_info(codes)
    
    mid_cap["現價"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("現價", "-"))
    mid_cap["漲跌幅"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("漲跌", "-"))
    mid_cap["成交量"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    mid_cap["成交值"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("成交值", "-"))
    
    # 用來排序的數值
    mid_cap["raw_turnover"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("raw_turnover", 0))
    mid_cap["raw_vol"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("raw_vol", 0))
    mid_cap["raw_change"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("raw_change", 0))
    
    # 連結
    mid_cap["連結代碼"] = mid_cap["股票代碼"].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")

    # 篩選與排序
    c1, c2 = st.columns([1, 2])
    with c1:
        sort_method = st.radio("排序依據：", ["💰 資金熱度 (成交值)", "🔥 量能爆發 (成交量)", "🚀 股價強勢 (漲跌幅)", "💎 尚未入選 (挖寶)"])
    
    with c2:
        st.info("💡 點擊表格內的「代號」可直接跳轉 Yahoo 股市。")

    if sort_method == "💰 資金熱度 (成交值)":
        df_show = mid_cap.sort_values("raw_turnover", ascending=False).head(30)
    elif sort_method == "🔥 量能爆發 (成交量)":
        df_show = mid_cap.sort_values("raw_vol", ascending=False).head(30)
    elif sort_method == "🚀 股價強勢 (漲跌幅)":
        df_show = mid_cap.sort_values("raw_change", ascending=False).head(30)
    else:
        df_show = mid_cap[mid_cap["已入選 ETF"] == "-"].sort_values("排名").head(30)

    st.dataframe(
        df_show[["排名", "連結代碼", "股票名稱", "已入選 ETF", "現價", "成交值", "漲跌幅", "成交量"]],
        use_container_width=True,
        hide_index=True,
        column_config=column_cfg
    )
