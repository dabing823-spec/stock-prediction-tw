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
st.set_page_config(page_title="台股 ETF 戰情室 (操盤版)", layout="wide")
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
# 4. 主程式
# -------------------------------------------
st.title("📈 台股 ETF 戰情室 (實戰操盤版)")
st.caption("整合量化訊號、資金流向與操盤手交易劇本")

with st.spinner("正在載入全市場即時數據..."):
    df_mcap = fetch_taifex_rankings(limit=200)
    msci_codes = fetch_msci_list()
    holdings = {}
    for etf in ["0050", "0056", "00878", "00919"]:
        holdings[etf] = set(fetch_etf_holdings(etf))

    if df_mcap.empty:
        st.error("資料源連線逾時，請重新整理"); st.stop()

# 側邊欄
with st.sidebar:
    st.header("📡 市場雷達")
    active_hy = get_high_yield_schedule()
    
    if active_hy:
        st.error(f"🔥 **本月重頭戲**")
        for h in active_hy:
            st.write(f"● {h['name']}")
        st.caption("策略：請關注 Tab 3 的中型股爆量訊號")
    else:
        st.info("本月無大型高股息調整")
        st.text("下波預告：12月 (0056, 00919)")
    
    st.divider()
    if st.button("🔄 更新行情"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Update: {datetime.now().strftime('%H:%M')}")

tab1, tab2, tab3 = st.tabs(["🇹🇼 0050 權值對決", "🌍 MSCI 外資對決", "💰 高股息/中型 100"])

# ==================================================
# Tab 1: 0050 (吃豆腐劇本)
# ==================================================
with tab1:
    # --- 實戰劇本 A (已修正出場邏輯) ---
    with st.expander("📜 交易劇本：【0050 吃豆腐戰法】 (點擊展開)", expanded=True):
        st.markdown("""
        ### 🎯 核心邏輯：流動性衝擊 (Liquidity Shock)
        0050 是被動 ETF，必須在「生效日」尾盤買齊成分股。我們的獲利來源是**提供流動性給 ETF**。

        #### ✅ 買進劇本 (針對左欄「潛在納入」)
        1.  **觀察期：** 公布名單後，觀察股價走勢。若股價沒有噴出(甚至下跌)，是最佳機會。
        2.  **出手時機：** **生效日當天 (通常是週五) 13:24:00**。
        3.  **操作：** 掛單買進「納入股」。
        4.  **出場：** **13:30:00 (最後一盤)** **掛「跌停價」賣出**。
            *   **為什麼掛跌停？** 為了確保 **100% 成交** (優先權最高)。
            *   **會賣在跌停嗎？** 不會。ETF 會市價買進，撮合價格會是當時的市場價(通常是高價)。
        5.  **獲利點：** 賺取 13:25~13:30 ETF 大量市價買單推升的價差。

        #### ❌ 避雷針
        *   如果公布前股價已經漲幅 > 20%，代表已經有人偷跑，**不要追**，容易利多出盡。
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
            st.success("🟢 **潛在納入 (買方觀察)**")
            if not must_in.empty:
                st.markdown("**🔥 必然納入 (Rank ≤ 40)**")
                st.dataframe(enrich_df(must_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            else:
                st.info("前 40 名皆已在名單內。")

            if not candidate_in.empty:
                st.markdown("**⚔️ 關鍵挑戰者 (Rank 41-50)**")
                st.dataframe(enrich_df(candidate_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

        with c2:
            st.error("🔴 **潛在剔除 (跳車觀察)**")
            if not must_out.empty:
                st.markdown("**👋 必然剔除 (Rank > 60)**")
                st.dataframe(enrich_df(must_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            if not danger_out.empty:
                st.markdown("**⚠️ 危險邊緣 (Rank 41-60)**")
                st.dataframe(enrich_df(danger_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
    else:
        st.warning("0050 資料讀取失敗")

# ==================================================
# Tab 2: MSCI (外資劇本)
# ==================================================
with tab2:
    # --- 實戰劇本 B ---
    with st.expander("📜 交易劇本：【MSCI 波動戰法】 (點擊展開)", expanded=True):
        st.markdown("""
        ### 🎯 核心邏輯：全球資金重配置
        MSCI 調整牽動的是數千億的外資被動買盤。

        #### ⚡ 操作時機點
        1.  **公布日 (早晨)：** 
            *   如果出現 **「意外納入」** 的黑馬 (下方列表顯示高機率，但市場沒預料到)，開盤**市價敲進**，當沖勝率高。
        2.  **生效日 (月底)：**
            *   **尾盤爆量戰術：** MSCI 調整日，尾盤 5 分鐘成交量常佔全日的 20%。
            *   **操作：** 若你持有納入股，不要在盤中賣。
            *   **出場：** 13:30 最後一盤，**掛「跌停價」賣出** (確保成交在當日最後一筆大量換手價)。
        """)

    if msci_codes:
        prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))]
        watch_in = df_mcap[(df_mcap["排名"] > 85) & (df_mcap["排名"] <= 100) & (~df_mcap["股票代碼"].isin(msci_codes))]
        prob_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))]
        
        all_codes = list(prob_in["股票代碼"]) + list(watch_in["股票代碼"]) + list(prob_out["股票代碼"])
        
        c1, c2 = st.columns(2)
        with c1:
            st.success("🟢 **潛在納入 (外資買盤)**")
            if not prob_in.empty:
                st.markdown("**🔥 高機率納入 (Rank ≤ 85)**")
                st.dataframe(enrich_df(prob_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            if not watch_in.empty:
                st.markdown("**🧐 邊緣觀察 (Rank 86-100)**")
                st.dataframe(enrich_df(watch_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

        with c2:
            st.error("🔴 **潛在剔除 (外資賣盤)**")
            if not prob_out.empty:
                st.markdown("**👋 潛在剔除 (Rank > 100)**")
                st.dataframe(enrich_df(prob_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
    else:
        st.warning("MSCI 資料讀取失敗")

# ==================================================
# Tab 3: 高股息/中型 100 (偷跑劇本)
# ==================================================
with tab3:
    # --- 實戰劇本 C ---
    with st.expander("📜 交易劇本：【主力潛伏跟單術】 (點擊展開)", expanded=True):
        st.markdown("""
        ### 🎯 核心邏輯：抓出「正在偷跑」的資金
        高股息 ETF (0056, 00878) 調整是明牌，投信主動基金會提前卡位。我們要抓的就是這些痕跡。

        #### 🕵️‍♂️ 獵物特徵 (請在下方篩選器尋找)
        1.  **身份：** 排名在 **50~150 名** 之間，且 **「已入選 ETF」欄位是空** 的。
        2.  **訊號 A (量能)：** 成交量出現 **「🔥爆量」** (大於5日均量2倍)。
        3.  **訊號 B (資金)：** 成交值排名衝進 **前 30 名** (代表有大人在顧)。
        4.  **訊號 C (價格)：** 漲跌幅為 **紅字**，且股價站在 5 日線之上。

        #### ⚡ 操作 SOP
        *   **掃描：** 每天收盤後，打開此分頁，選「💰 資金熱度」排序。
        *   **進場：** 在公告前 1 個月佈局。
        *   **出場：** 公告名單當天大漲時，**掛「跌停」或「市價」** 停利 (確保賣掉)。
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
        sort_method = st.radio("🔍 戰術掃描器：", ["💰 資金熱度 (抓大人)", "🔥 量能爆發 (抓偷跑)", "💎 尚未入選 (抓遺珠)"])
    with c2:
        st.info("💡 這是最容易抓到飆股的區域。請重點關注「資金熱度」高且「尚未入選」的股票。")

    if sort_method == "💰 資金熱度 (抓大人)":
        df_show = mid_cap.sort_values("raw_turnover", ascending=False).head(30)
    elif sort_method == "🔥 量能爆發 (抓偷跑)":
        df_show = mid_cap.sort_values("raw_vol", ascending=False).head(30)
    else:
        df_show = mid_cap[mid_cap["已入選 ETF"] == "-"].sort_values("排名").head(30)

    st.dataframe(
        df_show[["排名", "連結代碼", "股票名稱", "已入選 ETF", "現價", "成交值", "漲跌幅", "成交量"]],
        use_container_width=True,
        hide_index=True,
        column_config=column_cfg
    )
