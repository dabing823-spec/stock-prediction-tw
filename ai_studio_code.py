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
st.set_page_config(page_title="台股 ETF 戰情室 (全方位版)", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -------------------------------------------
# 2. 數據抓取核心 (擴充版)
# -------------------------------------------

@st.cache_data(ttl=3600)
def fetch_taifex_rankings(limit=200):
    """抓取期交所市值排名 (擴大到 200 名以涵蓋中型股)"""
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
        
        if not rows: # Fallback
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
    """通用 ETF 成分股抓取 (0050, 0056, 00878, 00919)"""
    url = f"https://www.moneydj.com/ETF/X/Basic/Basic0007a.xdjhtm?etfid={etf_code}.TW"
    try:
        # 加上隨機延遲避免被擋
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
    """取得量價資訊 (含漲跌、均量判斷)"""
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
                        "raw_vol": vol,
                        "raw_change": change_pct
                    }
                else:
                    res[c] = {"現價": "-", "漲跌": "-", "量能": "-", "raw_vol": 0, "raw_change": 0}
            except:
                res[c] = {"現價": "-", "漲跌": "-", "量能": "-", "raw_vol": 0, "raw_change": 0}
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
    df["量能狀態"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    return df

def get_high_yield_schedule():
    """高股息行事曆"""
    m = date.today().month
    schedules = [
        {"name": "00878 (國泰)", "adj": [5, 11], "desc": "看重 ESG 與過去配息"},
        {"name": "0056 (元大)",  "adj": [6, 12], "desc": "預測未來一年殖利率"},
        {"name": "00919 (群益)", "adj": [5, 12], "desc": "精準高息 (看已宣告)"}
    ]
    active = [s for s in schedules if m in s["adj"]]
    return active, schedules

# -------------------------------------------
# 4. 主程式
# -------------------------------------------
st.title("📈 台股 ETF 戰情室 (全方位版)")
st.caption("涵蓋：0050 (權值) | MSCI (外資) | 00878/0056/00919 (高股息中型)")

# --- 資料準備 ---
with st.spinner("正在掃描全市場與各大 ETF 持股..."):
    df_mcap = fetch_taifex_rankings(limit=200)
    msci_codes = fetch_msci_list()
    
    # 抓取各大 ETF 成分股 (用來標記)
    holdings = {}
    for etf in ["0050", "0056", "00878", "00919"]:
        holdings[etf] = set(fetch_etf_holdings(etf))

    if df_mcap.empty:
        st.error("無法取得市值排名"); st.stop()

# --- 側邊欄 ---
with st.sidebar:
    st.header("🗓️ 調整行事曆")
    active_hy, all_hy = get_high_yield_schedule()
    
    if active_hy:
        st.error(f"🔥 本月 ({date.today().month}月) 重點戰場")
        for h in active_hy:
            st.write(f"● **{h['name']}**")
    else:
        st.info(f"本月 ({date.today().month}月) 無大型高股息調整")
        st.markdown("**下波預告：**")
        st.text("12月: 0056, 00919")
        
    st.divider()
    st.write("**資料最後更新:**", datetime.now().strftime("%H:%M"))
    if st.button("🔄 更新行情"):
        st.cache_data.clear()
        st.rerun()

# --- 分頁 ---
tab1, tab2, tab3 = st.tabs(["🇹🇼 0050 權值對決", "🌍 MSCI 外資對決", "💰 高股息/中型 100"])

# ==================================================
# Tab 1: 0050 (明確納入 vs 剔除)
# ==================================================
with tab1:
    st.markdown("### 0050 調整預測 (市值前 50 大)")
    if holdings["0050"]:
        df_anl = df_mcap.head(100).copy()
        df_anl["in_0050"] = df_anl["股票名稱"].isin(holdings["0050"])
        
        # 1. 納入候選 (Rank <= 40 or 41-50)
        must_in = df_anl[(df_anl["排名"] <= 40) & (~df_anl["in_0050"])]
        candidate_in = df_anl[(df_anl["排名"] > 40) & (df_anl["排名"] <= 50) & (~df_anl["in_0050"])]
        
        # 2. 剔除候選 (Rank > 60 or 41-60)
        # 需從完整清單找在 0050 內的人
        in_list = df_mcap[df_mcap["股票名稱"].isin(holdings["0050"])]
        must_out = in_list[in_list["排名"] > 60]
        danger_out = in_list[(in_list["排名"] > 40) & (in_list["排名"] <= 60)].sort_values("排名", ascending=False)
        
        # 準備抓行情
        codes = list(must_in["股票代碼"]) + list(candidate_in["股票代碼"]) + list(must_out["股票代碼"]) + list(danger_out["股票代碼"])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.success("🟢 **潛在納入區 (買進訊號)**")
            if not must_in.empty:
                st.markdown("**🔥 必然納入 (排名 ≤ 40)**")
                st.dataframe(enrich_df(must_in, codes)[["排名","股票名稱","現價","漲跌幅","量能狀態"]], hide_index=True)
            
            if not candidate_in.empty:
                st.markdown("**⚔️ 關鍵挑戰者 (排名 41-50)**")
                st.dataframe(enrich_df(candidate_in, codes)[["排名","股票名稱","現價","漲跌幅","量能狀態"]], hide_index=True)
            
            if must_in.empty and candidate_in.empty:
                st.info("前 50 名皆已在名單內，無潛在納入者。")

        with col2:
            st.error("🔴 **潛在剔除區 (賣出訊號)**")
            if not must_out.empty:
                st.markdown("**👋 必然剔除 (排名 > 60)**")
                st.dataframe(enrich_df(must_out, codes)[["排名","股票名稱","現價","漲跌幅","量能狀態"]], hide_index=True)
                
            if not danger_out.empty:
                st.markdown("**⚠️ 危險邊緣 (排名 41-60)**")
                st.dataframe(enrich_df(danger_out, codes)[["排名","股票名稱","現價","漲跌幅","量能狀態"]], hide_index=True)

    else:
        st.warning("無法取得 0050 成分股")

# ==================================================
# Tab 2: MSCI (明確納入 vs 剔除)
# ==================================================
with tab2:
    st.markdown("### MSCI 調整預測 (市值前 100 大)")
    if msci_codes:
        # 1. 納入 (Rank <= 85)
        prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))]
        watch_in = df_mcap[(df_mcap["排名"] > 85) & (df_mcap["排名"] <= 100) & (~df_mcap["股票代碼"].isin(msci_codes))]
        
        # 2. 剔除 (Rank > 100)
        prob_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))]
        
        codes = list(prob_in["股票代碼"]) + list(watch_in["股票代碼"]) + list(prob_out["股票代碼"])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.success("🟢 **潛在納入區 (外資買盤)**")
            if not prob_in.empty:
                st.markdown("**🔥 高機率納入 (排名 ≤ 85)**")
                st.dataframe(enrich_df(prob_in, codes)[["排名","股票名稱","現價","漲跌幅","量能狀態"]], hide_index=True)
            else:
                st.write("前 85 名皆已納入。")
                
            if not watch_in.empty:
                st.markdown("**🧐 邊緣觀察 (排名 86-100)**")
                st.dataframe(enrich_df(watch_in, codes)[["排名","股票名稱","現價","漲跌幅","量能狀態"]], hide_index=True)

        with col2:
            st.error("🔴 **潛在剔除區 (外資賣盤)**")
            if not prob_out.empty:
                st.markdown("**👋 潛在剔除 (排名 > 100)**")
                st.dataframe(enrich_df(prob_out, codes)[["排名","股票名稱","現價","漲跌幅","量能狀態"]], hide_index=True)
            else:
                st.write("目前成分股排名皆在 100 名內。")
    else:
        st.warning("無法取得 MSCI 名單")

# ==================================================
# Tab 3: 高股息/中型 100 (新增功能)
# ==================================================
with tab3:
    st.markdown("""
    ### 💰 高股息/中型股戰場 (00878, 0056, 00919)
    **邏輯：** 這些 ETF 主要從 **市值前 150 大** 的股票中，挑選殖利率高的。
    **策略：** 關注排名 **50~150 名** 的股票。若該月有 ETF 調整，且某檔股票**成交量放大、股價上漲**，極可能是被納入的目標。
    """)
    
    # 1. 篩選中型股 (Rank 50-150)
    mid_cap = df_mcap[(df_mcap["排名"] >= 50) & (df_mcap["排名"] <= 150)].copy()
    
    # 2. 標記目前是否已在這些 ETF 中 (避免重複推薦)
    def check_status(name):
        tags = []
        if name in holdings["0056"]: tags.append("0056")
        if name in holdings["00878"]: tags.append("00878")
        if name in holdings["00919"]: tags.append("00919")
        return ", ".join(tags) if tags else "-"
    
    mid_cap["已入選 ETF"] = mid_cap["股票名稱"].apply(check_status)
    
    # 3. 取得行情
    codes = list(mid_cap["股票代碼"])
    info = get_advanced_stock_info(codes)
    
    # 4. 整合資料
    mid_cap["現價"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("現價", "-"))
    mid_cap["漲跌幅"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("漲跌", "-"))
    mid_cap["量能狀態"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    mid_cap["raw_vol"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("raw_vol", 0))
    mid_cap["raw_change"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("raw_change", 0))

    # 5. 篩選器 (互動功能)
    c1, c2 = st.columns([1, 2])
    with c1:
        filter_type = st.radio("篩選重點：", ["🔥 量能爆發 (有人在買)", "🚀 股價強勢 (漲幅高)", "💎 尚未入選 (潛在黑馬)"])
    
    with c2:
        st.info("💡 提示：找「量能爆發」且「尚未入選」的股票，配合該股殖利率(需另查)，命中率最高。")

    # 根據篩選顯示
    if filter_type == "🔥 量能爆發 (有人在買)":
        # 找成交量大於 0 且依量排序
        display_df = mid_cap.sort_values("raw_vol", ascending=False).head(20)
    elif filter_type == "🚀 股價強勢 (漲幅高)":
        display_df = mid_cap.sort_values("raw_change", ascending=False).head(20)
    else:
        # 找還沒被這三檔 ETF 選中，且排名靠前的
        display_df = mid_cap[mid_cap["已入選 ETF"] == "-"].sort_values("排名").head(20)

    st.dataframe(
        display_df[["排名", "股票名稱", "已入選 ETF", "現價", "漲跌幅", "量能狀態"]],
        use_container_width=True,
        hide_index=True
    )
