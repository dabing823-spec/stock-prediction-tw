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
# 2. 數據抓取核心 (保持高效快取)
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
                    
                    if vol > (avg_vol * 2) and vol > 1000: vol_status = "🔥爆量"
                    elif vol < (avg_vol * 0.6): vol_status = "💧縮量"
                    else: vol_status = "➖正常"
                    
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
# 3. 介面輔助
# -------------------------------------------
def enrich_df(df, codes_list):
    if df.empty: return df
    info = get_advanced_stock_info(codes_list)
    df["現價"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("現價", "-"))
    df["漲跌幅"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("漲跌", "-"))
    df["成交量"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    df["成交值"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("成交值", "-"))
    df["raw_turnover"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("raw_turnover", 0))
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

column_cfg = {
    "連結代碼": st.column_config.LinkColumn("代號", display_text=r"https://tw\.stock\.yahoo\.com/quote/(\d+)", width="small"),
    "raw_turnover": None, "raw_vol": None, "raw_change": None
}

# -------------------------------------------
# 4. 主程式 (UI)
# -------------------------------------------
st.title("📈 台股 ETF 戰情室 (Pro)")
st.caption("全方位監控：0050 權值 | MSCI 外資 | 高股息吃豆腐策略")

with st.spinner("正在掃描全市場數據與計算資金流向..."):
    df_mcap = fetch_taifex_rankings(limit=200)
    msci_codes = fetch_msci_list()
    holdings = {}
    for etf in ["0050", "0056", "00878", "00919"]:
        holdings[etf] = set(fetch_etf_holdings(etf))

    if df_mcap.empty:
        st.error("無法取得市值排名，請稍後重試"); st.stop()

# --- 側邊欄 (更新名稱與內容) ---
with st.sidebar:
    st.header("📡 換股時程與情報") # 修改名稱
    
    active_hy = get_high_yield_schedule()
    
    st.markdown("### 🔥 本月焦點")
    if active_hy:
        for h in active_hy:
            st.markdown(f"👉 **{h['name']}** 調整中")
    else:
        st.markdown("本月無大型高股息調整")
    
    st.divider()
    st.markdown("### 🗓️ 未來預告")
    st.text("12月: 0050, 0056, 00919")
    st.text("02月: MSCI 季度調整")
    
    st.divider()
    if st.button("🔄 更新即時行情"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"更新時間: {datetime.now().strftime('%H:%M')}")

tab1, tab2, tab3 = st.tabs(["🇹🇼 0050 權值對決", "🌍 MSCI 外資對決", "💰 高股息/中型 100"])

# ==================================================
# Tab 1: 0050
# ==================================================
with tab1:
    # --- 加入策略說明 (Expander) ---
    with st.expander("📖 [必讀] 0050 戰法與操作規則", expanded=False):
        st.markdown("""
        **1. 調整規則：**
        *   **納入：** 總市值排名前 **40** 名（必入）。
        *   **剔除：** 總市值排名掉到 **60** 名以後（必出）。
        *   **觀察區：** 41~60 名之間，視技術規則與保留名單而定。
        
        **2. 操作策略 (吃豆腐)：**
        *   **公布前 (預測期)：** 買進「必然納入」名單。若成交量縮（沒人注意），效果更好。
        *   **生效日 (12月第三個週五)：** 
            *   被動買盤會在 **13:25-13:30** 最後一盤掛市價買進。
            *   若你已獲利，可在尾盤掛漲停或市價賣給投信。
        *   **風險：** 若公布前股價已大漲（已反應），公布後容易利多出盡。
        """)

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
            st.success("🟢 **潛在納入區 (買進訊號)**")
            if not must_in.empty:
                st.markdown("**🔥 必然納入 (Rank ≤ 40)**")
                st.dataframe(enrich_df(must_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            if not candidate_in.empty:
                st.markdown("**⚔️ 關鍵挑戰者 (Rank 41-50)**")
                st.dataframe(enrich_df(candidate_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            if must_in.empty and candidate_in.empty:
                st.info("目前前 50 名皆已在成分股內。")

        with c2:
            st.error("🔴 **潛在剔除區 (賣出訊號)**")
            if not must_out.empty:
                st.markdown("**👋 必然剔除 (Rank > 60)**")
                st.dataframe(enrich_df(must_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            if not danger_out.empty:
                st.markdown("**⚠️ 危險邊緣 (Rank 41-60)**")
                st.dataframe(enrich_df(danger_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
    else:
        st.warning("0050 資料讀取失敗")

# ==================================================
# Tab 2: MSCI
# ==================================================
with tab2:
    # --- 加入策略說明 (Expander) ---
    with st.expander("📖 [必讀] MSCI 戰法與操作規則", expanded=False):
        st.markdown("""
        **1. 調整規則：**
        *   主要看 **總市值** + **自由流通市值 (Free Float)**。
        *   外資對於「流動性」要求極高。通常台灣市值排名前 **85** 名是安全納入區。
        
        **2. 操作策略 (跟著外資做)：**
        *   **公布日 (凌晨)：** 確定納入名單。如果是「意外納入」的黑馬，開盤容易跳空大漲。
        *   **生效日 (月底收盤)：** 
            *   **爆量時刻：** MSCI 調整是全球連動，被動基金會在當天 **最後一盤 (13:25-13:30)** 強制換股。
            *   **波動：** 當天尾盤股價常會劇烈跳動 (例如瞬間拉高或殺低 1~2%)，這是正常的被動買盤效應。
        """)

    if msci_codes:
        prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))]
        watch_in = df_mcap[(df_mcap["排名"] > 85) & (df_mcap["排名"] <= 100) & (~df_mcap["股票代碼"].isin(msci_codes))]
        prob_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))]
        
        all_codes = list(prob_in["股票代碼"]) + list(watch_in["股票代碼"]) + list(prob_out["股票代碼"])
        
        c1, c2 = st.columns(2)
        with c1:
            st.success("🟢 **潛在納入區 (外資買盤)**")
            if not prob_in.empty:
                st.markdown("**🔥 高機率納入 (Rank ≤ 85)**")
                st.dataframe(enrich_df(prob_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            if not watch_in.empty:
                st.markdown("**🧐 邊緣觀察 (Rank 86-100)**")
                st.dataframe(enrich_df(watch_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

        with c2:
            st.error("🔴 **潛在剔除區 (外資賣盤)**")
            if not prob_out.empty:
                st.markdown("**👋 潛在剔除 (Rank > 100)**")
                st.dataframe(enrich_df(prob_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
    else:
        st.warning("MSCI 資料讀取失敗")

# ==================================================
# Tab 3: 高股息/中型 100
# ==================================================
with tab3:
    # --- 加入策略說明 (Expander) ---
    with st.expander("📖 [必讀] 高股息/中型 100 吃豆腐戰法", expanded=True): # 預設展開
        st.markdown("""
        **1. 戰場說明：**
        *   00878, 0056, 00919 等千億級 ETF，成分股多落在 **市值 50~150 名** 的中型股。
        *   這些 ETF 換股時，對中型股的股價衝擊力道，往往比 0050 對台積電的影響還大。
        
        **2. 篩選心法：**
        *   **找遺珠：** 找「排名在前 (50-100)」但 **「已入選 ETF」欄位是空** 的股票。
        *   **看量能：** 如果這支遺珠最近 **「成交量爆發 (🔥爆量)」** 或 **「成交值大增」**，代表投信可能正在默默佈局。
        *   **查殖利率：** (需自行確認) 若該股殖利率 > 5% 且獲利成長，被納入高股息 ETF 的機率極高。
        """)

    mid_cap = df_mcap[(df_mcap["排名"] >= 50) & (df_mcap["排名"] <= 150)].copy()
    
    def check_status(name):
        tags = []
        if name in holdings["0056"]: tags.append("0056")
        if name in holdings["00878"]: tags.append("00878")
        if name in holdings["00919"]: tags.append("00919")
        return ", ".join(tags) if tags else "-"
    
    mid_cap["已入選 ETF"] = mid_cap["股票名稱"].apply(check_status)
    
    codes = list(mid_cap["股票代碼"])
    info = get_advanced_stock_info(codes)
    
    mid_cap["現價"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("現價", "-"))
    mid_cap["漲跌幅"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("漲跌", "-"))
    mid_cap["成交量"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    mid_cap["成交值"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("成交值", "-"))
    mid_cap["raw_turnover"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("raw_turnover", 0))
    mid_cap["raw_vol"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("raw_vol", 0))
    mid_cap["raw_change"] = mid_cap["股票代碼"].map(lambda x: info.get(x, {}).get("raw_change", 0))
    mid_cap["連結代碼"] = mid_cap["股票代碼"].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")

    c1, c2 = st.columns([1, 2])
    with c1:
        sort_method = st.radio("篩選與排序：", ["💰 資金熱度 (成交值)", "🔥 量能爆發 (成交量)", "💎 尚未入選 (潛在黑馬)"])
    with c2:
        st.info("💡 資金熱度與爆量，通常是法人進場的前兆。")

    if sort_method == "💰 資金熱度 (成交值)":
        df_show = mid_cap.sort_values("raw_turnover", ascending=False).head(30)
    elif sort_method == "🔥 量能爆發 (成交量)":
        df_show = mid_cap.sort_values("raw_vol", ascending=False).head(30)
    else:
        df_show = mid_cap[mid_cap["已入選 ETF"] == "-"].sort_values("排名").head(30)

    st.dataframe(
        df_show[["排名", "連結代碼", "股票名稱", "已入選 ETF", "現價", "成交值", "漲跌幅", "成交量"]],
        use_container_width=True,
        hide_index=True,
        column_config=column_cfg
    )
