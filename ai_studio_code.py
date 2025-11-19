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
import calendar

# -------------------------------------------
# 1. 基礎設定與工具
# -------------------------------------------
st.set_page_config(page_title="台股指數調整戰情室", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -------------------------------------------
# 2. 爬蟲函式
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
    """注意：這裡抓取的是目前生效的名單 (通常尚未更新為最新公布的結果)"""
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
# 3. 智能日程判斷 (加入「已公布」邏輯)
# -------------------------------------------
def get_smart_schedule():
    today = date.today()
    m = today.month
    d = today.day
    
    # 計算當月最後一個交易日 (粗略計算為當月最後一天)
    last_day = calendar.monthrange(today.year, m)[1]
    effective_date = date(today.year, m, last_day)
    
    # --- MSCI 邏輯 (2, 5, 8, 11月) ---
    msci_months = [2, 5, 8, 11]
    
    # 判斷本月是否為 MSCI 月
    if m in msci_months:
        # 如果還沒到月中 (假設 7號公布)
        if d < 7:
            msci_status = "prediction" # 預測期
            msci_text = f"本月 ({m}月) 為調整月份，預計近日公布！"
        # 如果已經過了公布日，但還沒到月底生效
        elif 7 <= d <= last_day:
            msci_status = "announced" # 已公布，等待生效
            msci_text = f"本月名單 **已公布**！將於 {m}/{last_day} 收盤生效。"
        else:
            msci_status = "done" # 本月已結束
            msci_text = "本月調整已結束。"
        target_msci_month = m
    else:
        # 找下一個月份
        candidates = [x for x in msci_months if x > m]
        target_msci_month = candidates[0] if candidates else 2
        msci_status = "future"
        msci_text = f"下回調整：{target_msci_month}月"

    msci_info = {
        "month": target_msci_month,
        "status": msci_status,
        "desc": msci_text,
        "effective_date": f"{today.year}/{target_msci_month}/{calendar.monthrange(today.year, target_msci_month)[1]}"
    }

    # --- 0050 邏輯 (3, 6, 9, 12月) ---
    ftse_months = [3, 6, 9, 12]
    if m in ftse_months:
        # 0050 公布日通常是第一個或第二個週五 (約 1~12號)
        if d < 5:
            ftse_status = "prediction"
            ftse_text = f"本月 ({m}月) 為調整月份，即將公布！"
        elif 5 <= d <= 20: # 假設20號生效
            ftse_status = "announced"
            ftse_text = f"本月名單可能 **已公布**，等待第三個週五生效。"
        else:
            ftse_status = "done"
            ftse_text = "本月調整已結束。"
        target_ftse_month = m
    else:
        candidates = [x for x in ftse_months if x > m]
        target_ftse_month = candidates[0] if candidates else 3
        ftse_status = "future"
        ftse_text = f"下回調整：{target_ftse_month}月"
        
    ftse_info = {
        "month": target_ftse_month,
        "status": ftse_status,
        "desc": ftse_text
    }
    
    return msci_info, ftse_info

# -------------------------------------------
# 4. 主介面
# -------------------------------------------

st.title("📊 台股指數調整戰情室")
st.caption("資料來源：期交所 (排名) | MoneyDJ | Yahoo Finance")

msci_s, ftse_s = get_smart_schedule()

# 側邊欄資訊
with st.sidebar:
    st.header("📅 本期戰況")
    
    # MSCI 狀態卡
    if msci_s['status'] == 'announced':
        st.success(f"**MSCI (11月)**\n\n狀態：🔴 **已公布**\n操作：等待生效日尾盤\n生效：{msci_s['effective_date']}")
    else:
        st.info(f"**MSCI**\n\n{msci_s['desc']}")

    # 0050 狀態卡
    if ftse_s['status'] == 'announced':
        st.success(f"**0050 ({ftse_s['month']}月)**\n\n狀態：🔴 **已公布**\n說明：{ftse_s['desc']}")
    else:
        st.info(f"**0050**\n\n{ftse_s['desc']}")
        
    if st.button("🔄 更新最新行情"):
        st.cache_data.clear()
        st.rerun()

with st.spinner("正在分析數據..."):
    df_mcap = fetch_taifex_rankings()
    msci_codes = fetch_msci_list()
    df_0050 = fetch_0050_holdings()

if df_mcap.empty:
    st.error("期交所連線失敗")
    st.stop()

tab1, tab2 = st.tabs(["🌍 MSCI 季度調整 (本月焦點)", "🇹🇼 0050 關鍵戰役"])

# ==========================================
# Tab 1: MSCI (本月重點)
# ==========================================
with tab1:
    # 根據狀態顯示不同的提示
    if msci_s['status'] == 'announced':
        st.markdown(f"""
        <div style="padding: 15px; background-color: #ffebee; border-left: 5px solid #f44336; border-radius: 5px; margin-bottom: 20px;">
            <h4>🚨 MSCI 11月名單已公布！</h4>
            <ul>
                <li><b>目前狀態：</b> 等待 <b>{msci_s['effective_date']}</b> (月底) 收盤生效。</li>
                <li><b>重要提醒：</b> 下方列表是比對「最新市值」與「舊成分股(尚未生效更新)」。</li>
                <li><b>如何解讀：</b> 若下方出現「高機率納入」名單，且新聞確認已納入，則該股在生效日尾盤會有<b>被動買盤</b>。</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="padding: 15px; background-color: #e3f2fd; border-left: 5px solid #2196f3; border-radius: 5px; margin-bottom: 20px;">
            <h4>ℹ️ MSCI 觀察看板</h4>
            <ul><li>名單尚未公布，下方為根據市值排名的預測結果。</li></ul>
        </div>
        """, unsafe_allow_html=True)

    if msci_codes:
        # 這裡的邏輯是：網站上的 msci_codes 還沒更新 (因為還沒生效)，所以可以拿來比對
        # 潛在納入 = 排名很前面，但不在舊名單內 -> 代表這次"應該"被納入了
        high_prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))].copy()
        watch_in = df_mcap[(df_mcap["排名"] > 85) & (df_mcap["排名"] <= 100) & (~df_mcap["股票代碼"].isin(msci_codes))].copy()
        pot_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))].copy()

        target_codes = list(high_prob_in["股票代碼"]) + list(pot_out["股票代碼"])
        prices = get_stock_info(target_codes)

        st.subheader("🔥 疑似納入/高機率名單 (排名 ≤ 85)")
        if not high_prob_in.empty:
            high_prob_in["現價"] = high_prob_in["股票代碼"].map(lambda x: prices.get(x, "-"))
            st.success("這些股票市值排名極高但不在舊名單中，請核對新聞是否已宣布納入！")
            st.dataframe(high_prob_in[["排名", "股票代碼", "股票名稱", "現價"]], hide_index=True)
        else:
            st.info("前 85 名皆已在舊名單內 (或網站已提前更新名單)。")
            
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🚀 邊緣觀察區 (86~100)")
            st.dataframe(watch_in[["排名", "股票代碼", "股票名稱"]], hide_index=True)
        with c2:
            st.subheader("⚠️ 疑似剔除/高風險 (>100)")
            if not pot_out.empty:
                pot_out["現價"] = pot_out["股票代碼"].map(lambda x: prices.get(x, "-"))
                st.error("這些股票仍在舊名單中但市值滑落，請核對新聞是否已剔除。")
                st.dataframe(pot_out[["排名", "股票代碼", "股票名稱", "現價"]], hide_index=True)
            else:
                st.write("無")
    else:
        st.warning("無法取得 MSCI 舊名單")

# ==========================================
# Tab 2: 0050
# ==========================================
with tab2:
    st.markdown(f"""
    <div style="padding: 15px; background-color: #e6fffa; border-left: 5px solid #00b894; border-radius: 5px; margin-bottom: 20px;">
        <h4>💡 0050 下回調整：{ftse_s['month']}月</h4>
        <ul>
            <li>目前為 <b>{ftse_s['status']}</b> 階段。</li>
            <li>市值前 40 名為必然納入安全區。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    if not df_0050.empty:
        current_0050 = set(df_0050["股票名稱"].astype(str).str.strip())
        df_anl = df_mcap.head(100).copy()
        df_anl["in_0050"] = df_anl["股票名稱"].isin(current_0050)
        
        must_in = df_anl[(df_anl["排名"] <= 40) & (~df_anl["in_0050"])].copy()
        in_list_stocks = df_mcap[df_mcap["股票名稱"].isin(current_0050)]
        must_out = in_list_stocks[in_list_stocks["排名"] > 60].copy()
        candidates = df_anl[(df_anl["排名"] > 40) & (df_anl["排名"] <= 50) & (~df_anl["in_0050"])].sort_values("排名").head(3)

        all_codes = list(must_in["股票代碼"]) + list(candidates["股票代碼"]) + list(must_out["股票代碼"])
        prices = get_stock_info(all_codes)
        
        st.subheader("🚀 必然納入 (排名 ≤ 40)")
        if not must_in.empty:
            must_in["現價"] = must_in["股票代碼"].map(lambda x: prices.get(x, "-"))
            st.success("🔥 強力買進訊號！")
            st.dataframe(must_in[["排名", "股票代碼", "股票名稱", "現價"]], hide_index=True)
        else:
            st.info("目前無個股符合必然納入標準。")
            
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
