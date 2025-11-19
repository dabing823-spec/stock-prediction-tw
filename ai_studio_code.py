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

# -------------------------------------------
# 1. 基礎設定與工具
# -------------------------------------------
st.set_page_config(page_title="台股指數調整預測 Pro", layout="wide")

# 忽略 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -------------------------------------------
# 2. 爬蟲函式
# -------------------------------------------
@st.cache_data(ttl=3600)
def fetch_taifex_rankings(limit=200):
    """抓取期交所市值排名"""
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
    """抓取 MSCI 成分股"""
    url = "https://stock.capital.com.tw/z/zm/zmd/zmdc.djhtm?MSCI=0"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        guess = chardet.detect(resp.content)
        encoding = guess['encoding'] if guess['encoding'] else 'cp950'
        html_text = resp.content.decode(encoding, errors="ignore")
        codes = set(re.findall(r"Link2Stk\('(\d{4})'\)", html_text))
        if not codes: codes = set(re.findall(r"\b(\d{4})\b", BeautifulSoup(html_text, "lxml").get_text()))
        return sorted(list(codes))
    except Exception as e:
        st.error(f"抓取 MSCI 名單失敗: {e}"); return []

@st.cache_data(ttl=3600)
def fetch_0050_holdings():
    """抓取 0050 成分股"""
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
    except Exception as e:
        st.error(f"抓取 0050 名單失敗: {e}"); return pd.DataFrame()

@st.cache_data(ttl=300)
def get_stock_info(codes):
    """取得即時股價"""
    if not codes: return {}
    try:
        tickers = " ".join([f"{c}.TW" for c in codes])
        data = yf.Tickers(tickers)
        res = {}
        for c in codes:
            try:
                h = data.tickers[f"{c}.TW"].history(period="1d")
                if not h.empty:
                    res[c] = round(h["Close"].iloc[-1], 2)
                else:
                    res[c] = "-"
            except: res[c] = "-"
        return res
    except: return {}

# -------------------------------------------
# 3. 日程判斷邏輯 (修正 Bug)
# -------------------------------------------
def get_schedule_info():
    """計算並回傳 MSCI 與 0050 的日程資訊"""
    today = date.today()
    m = today.month
    
    # 輔助函式：找下一個發生的月份
    def find_next_month(current, months):
        # 先找今年還有沒有剩下的月份
        candidates = [x for x in months if x >= current]
        if candidates:
            return candidates[0] # 如果有，取最近的一個
        else:
            return months[0] # 如果沒有，取明年的第一個

    # MSCI (2, 5, 8, 11月)
    next_msci = find_next_month(m, [2, 5, 8, 11])
    msci_info = {
        "next_month": next_msci,
        "announce": "該月中旬 (約10-15日)",
        "effective": "該月月底收盤"
    }
    
    # 0050 (3, 6, 9, 12月)
    # 修正：若現在是 11月, find_next_month 會回傳 12
    next_ftse = find_next_month(m, [3, 6, 9, 12])
    
    ftse_info = {
        "next_month": next_ftse,
        "announce": f"{next_ftse}月 第一個或第二個星期五",
        "effective": f"{next_ftse}月 第三個星期五收盤"
    }
    return msci_info, ftse_info

# -------------------------------------------
# 4. 主介面 UI
# -------------------------------------------

st.title("📊 台股指數調整預測戰情室")
st.caption("資料來源：期交所 (排名) | MoneyDJ (0050) | Yahoo Finance (股價)")

# 側邊欄
with st.sidebar:
    st.header("⚙️ 設定與資訊")
    if st.button("🔄 強制更新資料"):
        st.cache_data.clear()
        st.rerun()
    
    st.info(f"最後更新：{datetime.now().strftime('%H:%M')}")
    
    st.markdown("---")
    st.markdown("### 📅 投資行事曆")
    msci_s, ftse_s = get_schedule_info()
    
    st.success(f"**0050 (富時) 調整**\n\n下回：**{ftse_s['next_month']}月**\n公布：{ftse_s['announce']}\n生效：{ftse_s['effective']}")
    st.info(f"**MSCI 季度調整**\n\n下回：**{msci_s['next_month']}月**\n公布：{msci_s['announce']}\n生效：{msci_s['effective']}")

# 抓取資料
with st.spinner("正在分析大盤數據..."):
    df_mcap = fetch_taifex_rankings()
    msci_codes = fetch_msci_list()
    df_0050 = fetch_0050_holdings()

if df_mcap.empty:
    st.error("無法連線至期交所取得排名資料，請稍後再試。")
    st.stop()

tab1, tab2 = st.tabs(["🇹🇼 0050 關鍵戰役", "🌍 MSCI 季度調整"])

# 共用函式：加股價
def add_price(df, codes_list):
    if df.empty: return df
    prices = get_stock_info(codes_list)
    df["現價"] = df["股票代碼"].map(lambda x: prices.get(x, "-"))
    return df

# ==========================================
# Tab 1: 0050
# ==========================================
with tab1:
    # 策略看板
    st.markdown(f"""
    <div style="padding: 15px; background-color: #e6fffa; border-left: 5px solid #00b894; border-radius: 5px; margin-bottom: 20px;">
        <h4>💡 0050 下回調整：{ftse_s['next_month']}月</h4>
        <ul>
            <li><b>買入時機：</b> {ftse_s['effective']} (生效日) 13:25-13:30 試搓盤。</li>
            <li><b>規則：</b> 市值前 40 名「必然納入」；60 名後「必然剔除」。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    if not df_0050.empty:
        current_0050 = set(df_0050["股票名稱"].astype(str).str.strip())
        df_anl = df_mcap.head(100).copy()
        df_anl["in_0050"] = df_anl["股票名稱"].isin(current_0050)
        
        # 1. 必然列入 (<=40 & Not In)
        must_in = df_anl[(df_anl["排名"] <= 40) & (~df_anl["in_0050"])].copy()
        # 2. 必然剔除 (>60 & In)
        in_list_stocks = df_mcap[df_mcap["股票名稱"].isin(current_0050)]
        must_out = in_list_stocks[in_list_stocks["排名"] > 60].copy()
        # 3. 挑戰者 (41~50)
        candidates = df_anl[(df_anl["排名"] > 40) & (df_anl["排名"] <= 50) & (~df_anl["in_0050"])].sort_values("排名").head(3)

        # 準備抓股價的清單
        all_codes = list(must_in["股票代碼"]) + list(candidates["股票代碼"]) + list(must_out["股票代碼"])
        prices = get_stock_info(all_codes)
        
        # 顯示
        st.subheader("🚀 必然納入 (排名 ≤ 40)")
        if not must_in.empty:
            must_in["現價"] = must_in["股票代碼"].map(lambda x: prices.get(x, "-"))
            st.success("🔥 強烈買進訊號！符合必然納入標準。")
            st.dataframe(must_in[["排名", "股票代碼", "股票名稱", "現價"]], hide_index=True)
        else:
            st.info("目前無個股符合必然納入標準 (前 40 名皆已在名單內)。")
            
        st.divider()

        st.subheader("⚔️ 關鍵挑戰者 (排名 41~50)")
        cols = st.columns(3)
        for i, (_, row) in enumerate(candidates.iterrows()):
            p = prices.get(row["股票代碼"], "-")
            with cols[i]:
                st.metric(f"No.{row['排名']} {row['股票名稱']}", f"${p}", f"差 {row['排名']-40} 名", delta_color="inverse")
        
        st.divider()
        
        col_out, col_danger = st.columns(2)
        with col_out:
            st.subheader("👋 必然剔除 (排名 > 60)")
            if not must_out.empty:
                must_out["現價"] = must_out["股票代碼"].map(lambda x: prices.get(x, "-"))
                st.error("⚠️ 預期會有被動賣壓")
                st.dataframe(must_out[["排名", "股票代碼", "股票名稱", "現價"]], hide_index=True)
            else:
                st.write("無")
                
        with col_danger:
            st.subheader("⚠️ 危險邊緣 (41~60)")
            danger = in_list_stocks[(in_list_stocks["排名"] > 40) & (in_list_stocks["排名"] <= 60)].sort_values("排名", ascending=False)
            if not danger.empty:
                st.dataframe(danger[["排名", "股票代碼", "股票名稱"]], hide_index=True)
            else:
                st.write("無")
    else:
        st.warning("無法取得 0050 資料")

# ==========================================
# Tab 2: MSCI
# ==========================================
with tab2:
    # 策略看板
    st.markdown(f"""
    <div style="padding: 15px; background-color: #fff8e6; border-left: 5px solid #fdcb6e; border-radius: 5px; margin-bottom: 20px;">
        <h4>💡 MSCI 下回調整：{msci_s['next_month']}月</h4>
        <ul>
            <li><b>關鍵差異：</b> MSCI 看重「自由流通市值」，非單純總市值。</li>
            <li><b>高機率納入：</b> 市值衝進前 <b>85</b> 名但尚未納入者，機率極高。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if msci_codes:
        # 邏輯優化：
        # 1. 高機率納入 (High Probability): Rank <= 85 & Not in MSCI
        #    (台灣 MSCI 成分股通常在 88~90 檔左右，取 85 是安全邊際)
        high_prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))].copy()
        
        # 2. 潛在觀察 (Watch list): 86~100 名
        watch_in = df_mcap[(df_mcap["排名"] > 85) & (df_mcap["排名"] <= 100) & (~df_mcap["股票代碼"].isin(msci_codes))].copy()
        
        # 3. 潛在剔除
        pot_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))].copy()

        # 抓股價
        target_codes = list(high_prob_in["股票代碼"]) + list(pot_out["股票代碼"])
        prices = get_stock_info(target_codes)

        # 顯示
        st.subheader("🔥 高機率納入名單 (排名 ≤ 85)")
        if not high_prob_in.empty:
            high_prob_in["現價"] = high_prob_in["股票代碼"].map(lambda x: prices.get(x, "-"))
            st.success("注意！市值已達 MSCI 安全水位，納入機率高！")
            st.dataframe(high_prob_in[["排名", "股票代碼", "股票名稱", "現價"]], hide_index=True)
        else:
            st.info("目前前 85 名皆已在 MSCI 名單內，無明顯漏網之魚。")
            
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🚀 邊緣觀察區 (86~100)")
            st.dataframe(watch_in[["排名", "股票代碼", "股票名稱"]], hide_index=True)
            
        with c2:
            st.subheader("⚠️ 潛在剔除風險 (>100)")
            if not pot_out.empty:
                pot_out["現價"] = pot_out["股票代碼"].map(lambda x: prices.get(x, "-"))
                st.dataframe(pot_out[["排名", "股票代碼", "股票名稱", "現價"]], hide_index=True)
            else:
                st.write("目前無明顯剔除風險個股")
                
    else:
        st.warning("無法取得 MSCI 名單")
