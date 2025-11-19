import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import io
import chardet
from datetime import date, datetime
import urllib3
# 忽略不安全連線的警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# 設定頁面標題與配置
st.set_page_config(page_title="台股指數調整預測 (MSCI & 0050)", layout="wide")

# ==========================================
# 核心工具函式 (爬蟲與解析)
# ==========================================

# 模擬瀏覽器 Header
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

@st.cache_data(ttl=3600) # 設定快取 1 小時，避免頻繁抓取被鎖
def fetch_taifex_rankings(limit=200):
    """抓取期交所市值排名"""
    url = "https://www.taifex.com.tw/cht/9/futuresQADetail"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        # 自動偵測編碼
        encoding = chardet.detect(resp.content)["encoding"] or resp.apparent_encoding
        html_text = resp.content.decode(encoding, errors="ignore")
        
        soup = BeautifulSoup(html_text, "lxml")
        rows = []
        
        # 解析邏輯整合 (依據原腳本邏輯)
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if not tds: continue
            
            rank, code, name = None, None, None
            txts = [td.get_text(strip=True) for td in tds]
            
            # 嘗試暴力解析：找純數字 -> 4碼代號 -> 中文名稱
            for s in txts:
                if rank is None and re.fullmatch(r"\d+", s):
                    rank = int(s)
                elif rank is not None and code is None and re.fullmatch(r"\d{4}", s):
                    code = s
                elif rank is not None and code is not None and name is None:
                    if not re.fullmatch(r"\d+", s): # 排除數字
                        name = s
                        break
            
            if rank and code and name:
                rows.append({"排名": rank, "股票代碼": code, "股票名稱": name})
        
        if not rows:
            # 備用方案：pandas read_html
            dfs = pd.read_html(io.StringIO(html_text), flavor=["lxml", "html5lib"])
            for df in dfs:
                # 簡單判斷欄位
                cols = "".join([str(c) for c in df.columns])
                if "排名" in cols and ("名稱" in cols or "代號" in cols):
                    # 清整欄位名稱
                    df.columns = [str(c).replace(" ", "") for c in df.columns]
                    # 映射欄位
                    col_map = {}
                    for c in df.columns:
                        if "排名" in c: col_map[c] = "排名"
                        elif "代" in c: col_map[c] = "股票代碼"
                        elif "名" in c: col_map[c] = "股票名稱"
                    
                    if "排名" in col_map.values():
                        df = df.rename(columns=col_map)
                        # 轉型處理
                        df = df[pd.to_numeric(df["排名"], errors='coerce').notnull()]
                        df["排名"] = df["排名"].astype(int)
                        df["股票代碼"] = df["股票代碼"].astype(str).str.extract(r'(\d{4})')[0]
                        return df.sort_values("排名").head(limit)

        df = pd.DataFrame(rows)
        return df.sort_values("排名").head(limit)
        
    except Exception as e:
        st.error(f"抓取市值排名失敗: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_msci_list():
    @st.cache_data(ttl=3600)
def fetch_msci_list():
    """抓取 MSCI 成分股"""
    url = "https://stock.capital.com.tw/z/zm/zmd/zmdc.djhtm?MSCI=0"
    try:
        # 注意這裡多了 verify=False
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        
        # (以下程式碼保持不變...)
        guess = chardet.detect(resp.content)
        encoding = guess['encoding'] if guess['encoding'] else 'cp950'
        html_text = resp.content.decode(encoding, errors="ignore")
        
        codes = set()
        for m in re.finditer(r"Link2Stk\('(\d{4})'\)", html_text):
            codes.add(m.group(1))
        
        if not codes:
            soup = BeautifulSoup(html_text, "lxml")
            txt = soup.get_text()
            for m in re.finditer(r"\b(\d{4})\b", txt):
                codes.add(m.group(1))
                
        return sorted(list(codes))
    except Exception as e:
        st.error(f"抓取 MSCI 名單失敗: {e}")
        return []

@st.cache_data(ttl=3600)
def fetch_0050_holdings():
    """抓取 MoneyDJ 0050 持股"""
    url = "https://www.moneydj.com/ETF/X/Basic/Basic0007a.xdjhtm?etfid=0050.TW"
    try:
        # 注意這裡多了 verify=False
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        resp.encoding = resp.apparent_encoding or "utf-8"
        
        # (以下程式碼保持不變...)
        dfs = pd.read_html(io.StringIO(resp.text), flavor="lxml")
        all_names = []
        
        for df in dfs:
            if isinstance(df.columns, pd.MultiIndex):
                cols = [str(c[-1]).strip() for c in df.columns]
            else:
                cols = [str(c).strip() for c in df.columns]
            
            df.columns = cols
            
            target_col = None
            for c in cols:
                if "名稱" in c:
                    target_col = c
                    break
            
            if target_col:
                names = df[target_col].astype(str).str.strip().tolist()
                all_names.extend([n for n in names if n != 'nan' and n != ''])
        
        unique_names = list(set(all_names))
        return pd.DataFrame({"股票名稱": unique_names})
        
    except Exception as e:
        st.error(f"抓取 0050 名單失敗: {e}")
        return pd.DataFrame()

# ==========================================
# 介面邏輯
# ==========================================

st.title("📊 台灣股市指數調整預測工具")
st.markdown("資料來源：期交所 (市值排名)、群益證券 (MSCI)、MoneyDJ (0050)")

# 側邊欄：重新整理按鈕
if st.sidebar.button("🔄 強制更新資料"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.info(f"資料快取時間：{datetime.now().strftime('%H:%M:%S')}")

# --- 準備資料 ---
with st.spinner("正在從交易所與財經網站抓取最新資料..."):
    df_mcap = fetch_taifex_rankings(limit=200)
    
    if df_mcap.empty:
        st.error("無法取得市值排名資料，請稍後再試。")
        st.stop()

    msci_codes = fetch_msci_list()
    df_0050 = fetch_0050_holdings()

# --- 分頁顯示 ---
tab1, tab2 = st.tabs(["🌍 MSCI 納入/剔除觀察", "🇹🇼 0050 成分股審核"])

# =======================
# Tab 1: MSCI 分析
# =======================
with tab1:
    st.subheader("MSCI 季度調整觀察 (以市值排名交叉比對)")
    
    # 提示訊息
    today = date.today()
    if today.month in [2, 5, 8, 11]:
        st.warning(f"🗓️ 本月 ({today.month}月) 為 MSCI 審核月份！請密切注意。")
    
    if msci_codes:
        # 邏輯處理
        # 1. 前 100 名 但不在 MSCI (潛在納入)
        cond1 = df_mcap[df_mcap["排名"] <= 100].copy()
        cond1 = cond1[~cond1["股票代碼"].isin(msci_codes)].reset_index(drop=True)
        
        # 2. 100 名後 但在 MSCI (潛在剔除風險)
        cond2 = df_mcap[df_mcap["排名"] > 100].copy()
        cond2 = cond2[cond2["股票代碼"].isin(msci_codes)].reset_index(drop=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🚀 潛在納入觀察 (前100未入列)")
            st.dataframe(cond1, use_container_width=True)
            
        with col2:
            st.markdown("#### ⚠️ 潛在剔除觀察 (排名>100仍在列)")
            st.dataframe(cond2, use_container_width=True)
            
        # Excel 下載
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            cond1.to_excel(writer, sheet_name='潛在納入', index=False)
            cond2.to_excel(writer, sheet_name='潛在剔除', index=False)
            df_mcap.to_excel(writer, sheet_name='市值前200', index=False)
        
        st.download_button(
            label="📥 下載 MSCI 分析報告 (Excel)",
            data=output.getvalue(),
            file_name=f"MSCI_Report_{today.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.warning("無法取得目前的 MSCI 名單，僅顯示市值排名。")
        st.dataframe(df_mcap)

# =======================
# Tab 2: 0050 分析
# =======================
with tab2:
    st.subheader("0050 成分股調整預測")
    st.markdown("""
    **規則參考：**
    - **必定納入**：市值排名 <= 40 且目前不在 0050
    - **必定剔除**：市值排名 > 60 且目前在 0050
    - **觀察區**：排名 41~60 之間 (視技術規則決定)
    """)
    
    if not df_0050.empty:
        # 資料前處理
        current_0050_names = set(df_0050["股票名稱"].astype(str).str.strip())
        
        df_0050_analysis = df_mcap.head(100).copy() # 取前100來分析即可
        df_0050_analysis["是否在0050中"] = df_0050_analysis["股票名稱"].apply(
            lambda x: "✅ 是" if x in current_0050_names else "❌ 否"
        )
        
        # 邏輯篩選
        # A. 必定進入 (Rank <= 40 & Not in 0050)
        must_in = df_0050_analysis[
            (df_0050_analysis["排名"] <= 40) & 
            (df_0050_analysis["是否在0050中"] == "❌ 否")
        ]
        
        # B. 必定剔除 (Rank > 60 & In 0050)
        # 注意：這裡需要確保我們有抓到夠後面的排名，df_mcap 我們抓了 200 筆，夠用了
        # 但要先找出目前在 0050 但排名掉到 60 以外的
        
        # 先找出所有在 0050 的股票目前的排名
        in_0050_df = df_mcap[df_mcap["股票名稱"].isin(current_0050_names)].copy()
        must_out = in_0050_df[in_0050_df["排名"] > 60]
        
        # C. 邊緣觀察 (排名 41-60)
        edge_watch = df_0050_analysis[
            (df_0050_analysis["排名"] > 40) & 
            (df_0050_analysis["排名"] <= 60)
        ]
        
        # 顯示結果
        c1, c2 = st.columns(2)
        with c1:
            st.error("#### 👋 預測剔除名單 (排名 > 60)")
            if must_out.empty:
                st.info("目前沒有符合必定剔除規則的個股")
            else:
                st.dataframe(must_out[["排名", "股票代碼", "股票名稱"]], use_container_width=True)

        with c2:
            st.success("#### 🎉 預測納入名單 (排名 <= 40)")
            if must_in.empty:
                st.info("目前沒有符合必定納入規則的個股")
            else:
                st.dataframe(must_in[["排名", "股票代碼", "股票名稱"]], use_container_width=True)
        
        st.markdown("#### 🧐 邊緣觀察區 (排名 41 ~ 60)")
        st.dataframe(edge_watch, use_container_width=True)

        # Excel 下載
        output_0050 = io.BytesIO()
        with pd.ExcelWriter(output_0050, engine='xlsxwriter') as writer:
            must_in.to_excel(writer, sheet_name='預測納入', index=False)
            must_out.to_excel(writer, sheet_name='預測剔除', index=False)
            edge_watch.to_excel(writer, sheet_name='邊緣觀察', index=False)
            df_0050.to_excel(writer, sheet_name='目前0050成分', index=False)
        
        st.download_button(
            label="📥 下載 0050 分析報告 (Excel)",
            data=output_0050.getvalue(),
            file_name=f"0050_Predict_{today.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.ms-excel"
        )
        
    else:
        st.warning("無法取得 0050 成分股資料，無法進行交叉分析。")
