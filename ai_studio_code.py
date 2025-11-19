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
import calendar

# -------------------------------------------
# 1. 基礎設定
# -------------------------------------------
st.set_page_config(page_title="台股指數戰情室 Pro", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -------------------------------------------
# 2. 爬蟲與數據獲取 (增強版)
# -------------------------------------------
@st.cache_data(ttl=3600)
def fetch_taifex_rankings(limit=200):
    # (維持原樣，省略重複代碼以節省篇幅，請保留原本的 fetch_taifex_rankings 邏輯)
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
    # (維持原樣)
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
def fetch_0050_holdings():
    # (維持原樣)
    url = "https://www.moneydj.com/ETF/X/Basic/Basic0007a.xdjhtm?etfid=0050.TW"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        resp.encoding = resp.apparent_encoding or "utf-8"
        dfs = pd.read_html(io.StringIO(resp.text), flavor="lxml")
        names = []
        for df in dfs:
            cols = [str(c[-1] if isinstance(df.columns, pd.MultiIndex) else c).strip() for c in df.columns]
            df.columns = cols
            target = next((c for c in cols if "名稱" in c), None)
            if target: names.extend(df[target].astype(str).str.strip().tolist())
        return pd.DataFrame({"股票名稱": list(set([n for n in names if n not in ['nan','']]))})
    except: return pd.DataFrame()

# --- 🔥 新增：進階行情抓取 (量價分析) ---
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
                # 抓 5 天資料以計算漲跌與平均量
                h = t.history(period="5d")
                if not h.empty:
                    curr_price = h["Close"].iloc[-1]
                    prev_price = h["Close"].iloc[-2] if len(h) > 1 else curr_price
                    vol = h["Volume"].iloc[-1]
                    avg_vol = h["Volume"].mean()
                    
                    # 計算漲跌幅
                    change_pct = ((curr_price - prev_price) / prev_price) * 100
                    
                    # 衝擊指標：如果今日量 > 5日均量 2倍 -> 爆量
                    vol_status = "🔥爆量" if vol > (avg_vol * 2) else "💧縮量" if vol < (avg_vol * 0.5) else "➖正常"
                    
                    # 格式化成交量 (張數)
                    vol_str = f"{int(vol/1000)}張"
                    
                    res[c] = {
                        "現價": f"{curr_price:.2f}",
                        "漲跌": f"{change_pct:+.2f}%",
                        "量能": f"{vol_str} ({vol_status})",
                        "raw_vol": vol
                    }
                else:
                    res[c] = {"現價": "-", "漲跌": "-", "量能": "-", "raw_vol": 0}
            except:
                res[c] = {"現價": "-", "漲跌": "-", "量能": "-", "raw_vol": 0}
        return res
    except: return {}

# -------------------------------------------
# 3. 智能日程與策略
# -------------------------------------------
def get_strategy_calendar():
    today = date.today()
    m = today.month
    
    # 0056 / 00878 行事曆
    etf_high_yield = {
        "00878": {"months": [5, 11], "name": "國泰永續高股息"},
        "0056":  {"months": [6, 12], "name": "元大高股息"},
        "00919": {"months": [5, 12], "name": "群益台灣精選高息"}
    }
    
    active_etfs = []
    for code, info in etf_high_yield.items():
        if m in info["months"]:
            active_etfs.append(f"🔸 {code} {info['name']}")
            
    return active_etfs

# -------------------------------------------
# 4. 主介面
# -------------------------------------------
st.title("📈 台股指數戰情室 Pro")
st.caption("資料來源：期交所 | MoneyDJ | Yahoo Finance (量價分析)")

# 側邊欄
with st.sidebar:
    st.header("📅 豆腐行事曆")
    
    # 顯示高股息 ETF 是否正在調整
    high_yield_now = get_strategy_calendar()
    if high_yield_now:
        st.markdown("### 🔥 本月高股息 ETF 戰場")
        for item in high_yield_now:
            st.write(item)
        st.info("策略：高股息 ETF 調整通常會剔除殖利率變低的股票，納入新的高配息股。請留意投信買賣超。")
    else:
        st.markdown("### 💤 本月無大型高股息 ETF 調整")
        st.text("下波熱點：12月 (0056, 00919)")

    st.divider()
    if st.button("🔄 更新即時行情"):
        st.cache_data.clear()
        st.rerun()

# 抓取資料
with st.spinner("正在進行全市場量價掃描..."):
    df_mcap = fetch_taifex_rankings()
    msci_codes = fetch_msci_list()
    df_0050 = fetch_0050_holdings()

if df_mcap.empty:
    st.error("無法連線資料源"); st.stop()

# 數據處理 helper
def enrich_data(df, target_codes):
    if df.empty: return df
    info = get_advanced_stock_info(target_codes)
    
    df["現價"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("現價", "-"))
    df["漲跌幅"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("漲跌", "-"))
    df["成交量/狀態"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    
    # 簡單的樣式處理 (利用 Pandas Styler 在 Streamlit 顯示會比較複雜，這裡直接用欄位顯示)
    return df

tab1, tab2, tab3 = st.tabs(["🇹🇼 0050 關鍵戰役", "🌍 MSCI 季度調整", "🧠 操盤手筆記"])

# ==========================================
# Tab 1: 0050
# ==========================================
with tab1:
    st.markdown("#### 🎯 0050 潛在調整名單 (含量價分析)")
    if not df_0050.empty:
        curr_0050 = set(df_0050["股票名稱"].str.strip())
        df_anl = df_mcap.head(100).copy()
        df_anl["in_0050"] = df_anl["股票名稱"].isin(curr_0050)
        
        # 篩選
        must_in = df_anl[(df_anl["排名"] <= 40) & (~df_anl["in_0050"])]
        candidates = df_anl[(df_anl["排名"] > 40) & (df_anl["排名"] <= 50) & (~df_anl["in_0050"])].head(3)
        
        target_codes = list(must_in["股票代碼"]) + list(candidates["股票代碼"])
        
        # 顯示 必然納入
        if not must_in.empty:
            st.success("🔥 **強力買進訊號 (必然納入)**")
            st.markdown("關注重點：若**成交量偏低** (流動性差)，被動買盤進場時會有更大的漲幅。")
            final_df = enrich_data(must_in.copy(), target_codes)
            st.dataframe(final_df[["排名", "股票代碼", "股票名稱", "現價", "漲跌幅", "成交量/狀態"]], hide_index=True)
        else:
            st.info("目前前 40 名皆已在 0050 內。")
            
        st.divider()
        
        # 顯示 挑戰者
        st.markdown("#### ⚔️ 關鍵挑戰者 (第 41-50 名)")
        st.markdown("策略：若第 40 名之後的市值差距極小，可賭**「排名逆轉」**。觀察下方漲跌幅，看誰動能強。")
        if not candidates.empty:
            cand_df = enrich_data(candidates.copy(), target_codes)
            st.dataframe(cand_df[["排名", "股票代碼", "股票名稱", "現價", "漲跌幅", "成交量/狀態"]], hide_index=True)
            
    else:
        st.warning("無法取得 0050 資料")

# ==========================================
# Tab 2: MSCI
# ==========================================
with tab2:
    st.markdown("#### 🌍 MSCI 觀察看板")
    if msci_codes:
        # 邏輯：找出高機率納入 (排名前 85 且不在名單內)
        prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))]
        
        if not prob_in.empty:
            st.success("🔥 **MSCI 潛在黑馬 (市值高機率納入)**")
            st.markdown("策略：若名單已公布且確認納入，請關注**生效日尾盤**。")
            
            final_df = enrich_data(prob_in.copy(), list(prob_in["股票代碼"]))
            st.dataframe(final_df[["排名", "股票代碼", "股票名稱", "現價", "漲跌幅", "成交量/狀態"]], hide_index=True)
        else:
            st.info("前 85 名皆已在 MSCI 名單內。")
            
        # 顯示邊緣觀察
        st.markdown("#### 🧐 邊緣觀察區 (86-100名)")
        watch = df_mcap[(df_mcap["排名"] > 85) & (df_mcap["排名"] <= 100) & (~df_mcap["股票代碼"].isin(msci_codes))]
        if not watch.empty:
            watch_df = enrich_data(watch.copy(), list(watch["股票代碼"]))
            st.dataframe(watch_df[["排名", "股票代碼", "股票名稱", "現價", "漲跌幅", "成交量/狀態"]], hide_index=True)
    else:
        st.warning("無法取得 MSCI 名單")

# ==========================================
# Tab 3: 操盤手筆記 (新增)
# ==========================================
with tab3:
    st.markdown("""
    ### 🧠 老司機的 ETF 吃豆腐心法
    
    #### 1. 什麼是「流動性衝擊」？ (Liquidity Shock)
    當 0050 這種巨型 ETF 必須買入一檔股票，但這檔股票平常沒什麼人在交易 (成交量低)，ETF 的買盤會把股價瞬間買上去。
    *   **觀察重點：** 在「必然納入」名單中，找 **"成交量/狀態" 為 "💧縮量"** 的股票。這就是最肥的肉。
    
    #### 2. 時間點的藝術
    *   **公布前 (猜題期)：** 買進高機率名單 (如本網頁預測的 Rank <= 40)。賺的是「市場預期」的錢。
    *   **公布後~生效前 (抬轎期)：** 散戶看到新聞進場，股價會漲。此時是賣點，不是買點。
    *   **生效日 (決戰日)：** 
        *   **尾盤爆量**：ETF 會在 13:25~13:30 掛市價買進。
        *   **策略**：如果你手上有貨，掛漲停板賣給 ETF；如果你想當沖，尾盤前先拉高出貨。
    
    #### 3. 小心「預判你的預判」
    現在 ETF 調整太透明，很多人會提早卡位。如果公布名單前股價已經漲了 30%，公布當天可能會**利多出盡**反而下跌。
    *   **避雷針：** 看 "漲跌幅"，如果進榜前已經大漲一段，千萬別追。
    
    #### 4. 其他 ETF 戰場
    別只盯著 0050/MSCI。
    *   **00878 (5/11月)**、**0056 (6/12月)**、**00919 (5/12月)**
    *   這些高股息 ETF 規模巨大，調整時對中型股 (市值 50-150 名) 的衝擊力比 0050 還強！
    """)
