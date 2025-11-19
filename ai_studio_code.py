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
# 2. 爬蟲函式 (加上 verify=False 修正)
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
        
        # (簡化版解析邏輯，與先前相同)
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
            
        if not rows: # 備用 Pandas 解析
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
                # 嘗試取得最新一筆交易資訊
                h = data.tickers[f"{c}.TW"].history(period="1d")
                if not h.empty:
                    res[c] = round(h["Close"].iloc[-1], 2)
                else:
                    res[c] = "-"
            except: res[c] = "-"
        return res
    except: return {}

# -------------------------------------------
# 3. 日程判斷邏輯
# -------------------------------------------
def get_schedule_info():
    """計算並回傳 MSCI 與 0050 的日程資訊"""
    m = date.today().month
    
    # MSCI (2, 5, 8, 11月)
    msci_months = [2, 5, 8, 11]
    next_msci = min([x for x in msci_months if x >= m] + [2]) # 簡單找下一個
    msci_info = {
        "next_month": next_msci,
        "announce": "該月中旬 (約10-15日)",
        "effective": "該月月底收盤"
    }
    
    # 0050 (3, 6, 9, 12月)
    ftse_months = [3, 6, 9, 12]
    next_ftse = min([x for x in ftse_months if x >= m] + [3])
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

# 側邊欄：功能與狀態
with st.sidebar:
    st.header("⚙️ 設定與資訊")
    if st.button("🔄 強制更新資料"):
        st.cache_data.clear()
        st.rerun()
    
    st.info(f"最後更新：{datetime.now().strftime('%H:%M')}")
    
    st.markdown("---")
    st.markdown("### 📅 投資行事曆")
    msci_s, ftse_s = get_schedule_info()
    
    st.markdown(f"**MSCI 季度調整**")
    st.text(f"下回月份：{msci_s['next_month']}月")
    st.text(f"公布時間：{msci_s['announce']}")
    st.text(f"生效時間：{msci_s['effective']}")
    
    st.markdown(f"**0050 (富時) 調整**")
    st.text(f"下回月份：{ftse_s['next_month']}月")
    st.text(f"公布時間：{ftse_s['announce']}")
    st.text(f"生效時間：{ftse_s['effective']}")

# 抓取資料
with st.spinner("正在分析大盤數據..."):
    df_mcap = fetch_taifex_rankings()
    msci_codes = fetch_msci_list()
    df_0050 = fetch_0050_holdings()

if df_mcap.empty:
    st.error("無法連線至期交所取得排名資料，請稍後再試。")
    st.stop()

# 分頁
tab1, tab2 = st.tabs(["🇹🇼 0050 關鍵戰役", "🌍 MSCI 季度調整"])

# ==========================================
# Tab 1: 0050 預測 (重點優化)
# ==========================================
with tab1:
    # --- 策略看板 ---
    st.markdown(f"""
    <div style="padding: 15px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px;">
        <h4>💡 0050 操作策略 ({ftse_s['next_month']}月調整)</h4>
        <ul>
            <li><b>觀察期：</b> {ftse_s['next_month']}月的前一個月月底，市值排名定生死。</li>
            <li><b>公布日：</b> {ftse_s['announce']} 盤後公布。</li>
            <li><b>買入點：</b> <b>{ftse_s['effective']}</b> (調整生效日) 的 <b>最後一盤 (13:25-13:30)</b>。</li>
            <li><b>被動買盤：</b> 0050 ETF 會在生效日尾盤一次性買入納入股、賣出剔除股。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    if not df_0050.empty:
        current_0050 = set(df_0050["股票名稱"].astype(str).str.strip())
        
        # 資料整合
        df_anl = df_mcap.head(100).copy()
        df_anl["in_0050"] = df_anl["股票名稱"].isin(current_0050)
        
        # 邏輯定義
        # 1. 必然列入: Rank <= 40 且不在名單內
        must_in = df_anl[(df_anl["排名"] <= 40) & (~df_anl["in_0050"])].copy()
        
        # 2. 必然剔除: Rank > 60 且在名單內 (需從完整名單找)
        in_list_stocks = df_mcap[df_mcap["股票名稱"].isin(current_0050)]
        must_out = in_list_stocks[in_list_stocks["排名"] > 60].copy()
        
        # 3. 關鍵觀察: Rank 41~45 (潛在挑戰者)
        candidates = df_anl[(df_anl["排名"] > 40) & (df_anl["排名"] <= 50) & (~df_anl["in_0050"])].sort_values("排名").head(3)

        # 取得相關股價
        target_codes = list(must_in["股票代碼"]) + list(candidates["股票代碼"]) + list(must_out["股票代碼"])
        prices = get_stock_info(target_codes)
        
        def add_price(df):
            if df.empty: return df
            df["現價"] = df["股票代碼"].map(lambda x: prices.get(x, "-"))
            return df

        # --- 顯示區域 ---
        
        # 1. 必然列入 (最重要)
        st.subheader("🚀 必然列入名單 (符合排名 ≤ 40)")
        if not must_in.empty:
            must_in = add_price(must_in)
            st.success("🔥 注意！以下個股已達納入標準，被動買盤預期進場！")
            st.dataframe(
                must_in[["排名", "股票代碼", "股票名稱", "現價"]], 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("目前尚無個股衝進前 40 名 (安全名單空缺中)。")
            
        st.divider()

        # 2. 戰況儀表板 (最有機會的前三名)
        st.subheader("⚔️ 關鍵挑戰者 (排名 41~50)")
        st.markdown("若前 40 名無變動，這區間的股票將透過技術規則爭取納入。")
        
        cols = st.columns(3)
        for i, (_, row) in enumerate(candidates.iterrows()):
            p = prices.get(row["股票代碼"], "-")
            with cols[i]:
                st.metric(
                    label=f"No.{row['排名']} {row['股票名稱']}",
                    value=f"${p}",
                    delta=f"距門檻(40) 差 {row['排名']-40} 名",
                    delta_color="inverse"
                )
        
        st.divider()

        # 3. 剔除與危險區
        col_out, col_danger = st.columns(2)
        
        with col_out:
            st.subheader("👋 必然剔除 (排名 > 60)")
            if not must_out.empty:
                must_out = add_price(must_out)
                st.error("⚠️ 以下個股排名大幅滑落，預期被動賣壓！")
                st.dataframe(must_out[["排名", "股票代碼", "股票名稱", "現價"]], hide_index=True)
            else:
                st.write("目前無必然剔除名單。")

        with col_danger:
            st.subheader("⚠️ 邊緣危險區 (41~60)")
            danger = in_list_stocks[(in_list_stocks["排名"] > 40) & (in_list_stocks["排名"] <= 60)].sort_values("排名", ascending=False)
            if not danger.empty:
                st.warning("目前在成分股內，但排名後段，有被替換風險。")
                st.dataframe(danger[["排名", "股票代碼", "股票名稱"]], hide_index=True)
            else:
                st.write("現有成分股排名皆穩定。")

    else:
        st.warning("無法取得 0050 目前成分股，僅顯示市值排名。")
        st.dataframe(df_mcap.head(50))

# ==========================================
# Tab 2: MSCI 預測
# ==========================================
with tab2:
    # --- 策略看板 ---
    st.markdown(f"""
    <div style="padding: 15px; background-color: #e8f4f8; border-radius: 10px; margin-bottom: 20px;">
        <h4>💡 MSCI 操作策略 ({msci_s['next_month']}月調整)</h4>
        <ul>
            <li><b>公布日：</b> {msci_s['announce']} (台灣時間通常為早晨)。</li>
            <li><b>生效日：</b> <b>{msci_s['effective']}</b> (最後一個交易日)。</li>
            <li><b>尾盤爆量：</b> MSCI 調整當天最後一盤 (13:25-13:30) 通常會有數百億的被動成交量，波動劇烈。</li>
            <li><b>策略：</b> 若確認納入，通常公布後會漲一波，但生效日尾盤可能會因被動買盤滿足而回檔 (或反之)，需靈活操作。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if msci_codes:
        # 邏輯：MSCI 納入通常看的是「自由流通市值」，這裡用「總市值」做近似預估
        # 潛在納入：市值前 80~100 名但不在名單內 (範圍抓寬一點)
        pot_in = df_mcap[(df_mcap["排名"] <= 100) & (~df_mcap["股票代碼"].isin(msci_codes))].reset_index(drop=True)
        
        # 潛在剔除：市值掉到 100 名以外且在名單內
        pot_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))].reset_index(drop=True)

        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🚀 潛在納入觀察 (前100未入選)")
            st.dataframe(pot_in, use_container_width=True, hide_index=True)
            
        with c2:
            st.subheader("⚠️ 潛在剔除觀察 (排名>100仍在列)")
            st.dataframe(pot_out, use_container_width=True, hide_index=True)
    else:
        st.warning("無法取得 MSCI 名單")
