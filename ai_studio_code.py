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
# 1. 基礎設定 & CSS
# -------------------------------------------
st.set_page_config(page_title="台股 ETF 戰情室 (全攻略版)", layout="wide")
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
        # VIX
        vix = yf.Ticker("^VIX").history(period="5d")
        if not vix.empty:
            curr = vix["Close"].iloc[-1]
            prev = vix["Close"].iloc[-2]
            indicators["VIX"] = {"val": round(curr, 2), "delta": round(curr - prev, 2)}
        else: indicators["VIX"] = {"val": "-", "delta": 0}

        # 加權指數 (月季線)
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

# 新增：計算市值與權重 (針對 Tab 4)
@st.cache_data(ttl=3600)
def calculate_market_weights(codes):
    """利用 yfinance fast_info 取得市值並計算權重"""
    if not codes: return {}
    try:
        # 由於 yfinance 批量抓取 market_cap 比較慢，這裡用 tickers.tickers 迭代
        # 為了效能，我們假設輸入已經是 top N 列表
        mcap_data = {}
        tickers = " ".join([f"{c}.TW" for c in codes])
        data = yf.Tickers(tickers)
        
        for c in codes:
            try:
                # 使用 fast_info 比較快
                mcap = data.tickers[f"{c}.TW"].fast_info.market_cap
                if mcap:
                    mcap_data[c] = mcap
            except:
                mcap_data[c] = 0
        
        total_mcap = sum(mcap_data.values())
        res = {}
        for c, mcap in mcap_data.items():
            if total_mcap > 0:
                weight = (mcap / total_mcap) * 100
            else:
                weight = 0
            
            # 格式化市值 (億)
            mcap_str = f"{mcap/100000000:.0f}億"
            res[c] = {"市值": mcap_str, "權重": f"{weight:.2f}%"}
        return res
    except: return {}

def enrich_df(df, codes_list, add_weight=False):
    if df.empty: return df
    info = get_advanced_stock_info(codes_list)
    
    # 基本行情
    df["現價"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("現價", "-"))
    df["漲跌幅"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("漲跌", "-"))
    df["成交量"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    df["成交值"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("成交值", "-"))
    df["raw_turnover"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("raw_turnover", 0))
    df["raw_vol"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("raw_vol", 0))
    df["連結代碼"] = df["股票代碼"].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
    
    # 權重計算 (僅用於 Tab 4)
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
    "raw_turnover": None, "raw_vol": None
}

# -------------------------------------------
# 4. 主程式 UI
# -------------------------------------------
st.title("🚀 台股 ETF 戰情室 (全攻略版)")
st.caption("0050 | MSCI | 0056/00878 | 全市場權重")

# --- A. 大盤儀表板 (Dashboard) ---
m_inds = get_market_indicators()
col1, col2, col3, col4 = st.columns(4)

with col1:
    v = m_inds.get("VIX", {})
    delta_color = "red" if v.get('delta',0) > 0 else "green"
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #e74c3c;">
        <div class="metric-label">🇺🇸 VIX 恐慌指數</div>
        <div class="metric-value">{v.get('val','-')} <span style="font-size:14px; color:{delta_color};">({v.get('delta','-'):+.2f})</span></div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #f1c40f;">
        <div class="metric-label">🇺🇸 CNN 恐懼貪婪</div>
        <div class="metric-value" style="font-size:16px; padding-top:4px;"><a href="https://edition.cnn.com/markets/fear-and-greed" target="_blank" style="color:#fff;">點擊查看 (API Limit)</a></div>
    </div>""", unsafe_allow_html=True)

with col3:
    t = m_inds.get("TWII", {})
    color = "#2ecc71" if "站上" in t.get('status','') else "#e74c3c"
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {color};">
        <div class="metric-label">🇹🇼 加權指數 (月/季線)</div>
        <div class="metric-value">{t.get('val','-')}</div>
        <div class="metric-label" style="color:{color};">{t.get('status','-')}</div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #9b59b6;">
        <div class="metric-label">📊 融資維持率 (大盤多空)</div>
        <div class="metric-value" style="font-size:16px; padding-top:4px;">
            <a href="https://www.macromicro.me/charts/53117/taiwan-taiex-maintenance-margin" target="_blank" style="color:#fff;">
            財經M平方 查詢
            </a>
        </div>
    </div>""", unsafe_allow_html=True)

st.divider()

# --- B. 資料載入 ---
with st.spinner("正在掃描全市場數據與計算資金流向..."):
    df_mcap = fetch_taifex_rankings(limit=200)
    msci_codes = fetch_msci_list()
    holdings = {}
    for etf in ["0050", "0056", "00878", "00919"]:
        holdings[etf] = set(fetch_etf_holdings(etf))

    if df_mcap.empty:
        st.error("無法取得市值排名"); st.stop()

# 側邊欄
with st.sidebar:
    st.header("📡 市場雷達")
    active_hy = get_high_yield_schedule()
    if active_hy:
        st.error(f"🔥 **本月重頭戲:** {', '.join([h['name'] for h in active_hy])}")
    else:
        st.info("本月無大型高股息調整")
    
    st.divider()
    if st.button("🔄 更新行情"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Update: {datetime.now().strftime('%H:%M')}")

# --- C. 戰情室分頁 ---
tab1, tab2, tab3, tab4 = st.tabs(["🇹🇼 0050 權值", "🌍 MSCI 外資", "💰 0056 高股息", "📊 全市場權重(Top150)"])

# ==================================================
# Tab 1: 0050 (吃豆腐)
# ==================================================
with tab1:
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📜 0050 吃豆腐戰法 (SOP)</div>
        <div class="strategy-list">
            1. <b>核心邏輯：</b> 市值前 40 名必定納入。我們利用「市值排名」提前預測，不看新聞。<br>
            2. <b>進場時機 (佈局期)：</b> <span class="buy-signal">公告前 1 個月</span>。掃描下方左側「潛在納入」股 (Rank ≤ 40 但未入選)，若成交量縮，提早佈局。<br>
            3. <b>出場時機 (收割期)：</b> <span class="sell-signal">生效日當天 13:30 (最後一盤)</span>。<br>
            4. <b>操作細節：</b> 生效日尾盤掛 <span class="strategy-highlight">「跌停價」</span> 賣出 (確保 100% 倒貨給 ETF，成交價會是當下市價)。<br>
            5. <b>避險：</b> 若公告前股價漲幅 > 20%，代表市場已反應 (Priced-in)，利多出盡機率高，勿追。
        </div>
    </div>
    """, unsafe_allow_html=True)

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
            st.success("🟢 **潛在納入區 (買方)**")
            if not must_in.empty:
                st.markdown("**🔥 必然納入 (Rank ≤ 40)**")
                st.dataframe(enrich_df(must_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            if not candidate_in.empty:
                st.markdown("**⚔️ 關鍵挑戰者 (Rank 41-50)**")
                st.dataframe(enrich_df(candidate_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

        with c2:
            st.error("🔴 **潛在剔除區 (賣方)**")
            if not must_out.empty:
                st.markdown("**👋 必然剔除 (Rank > 60)**")
                st.dataframe(enrich_df(must_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            if not danger_out.empty:
                st.markdown("**⚠️ 危險邊緣 (Rank 41-60)**")
                st.dataframe(enrich_df(danger_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

# ==================================================
# Tab 2: MSCI
# ==================================================
with tab2:
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📜 MSCI 波動戰法 (SOP)</div>
        <div class="strategy-list">
            1. <b>核心邏輯：</b> 追蹤外資「被動買盤」。MSCI 重視「自由流通市值」，非單純總市值。Rank 85 內為安全區。<br>
            2. <b>進場時機 (佈局期)：</b> <span class="buy-signal">公布日早晨 (開盤)</span>。若發現「意外入選」的黑馬 (市場未預期)，開盤市價敲進當沖。<br>
            3. <b>出場時機 (收割期)：</b> <span class="sell-signal">生效日當天 13:30 (最後一盤)</span>。<br>
            4. <b>操作細節：</b> 若持有納入股，不要在盤中賣。等到 13:25 後，掛 <span class="strategy-highlight">「跌停價」</span> 賣出。當天尾盤通常會爆量拉高 (或殺低)，要吃到這段被動買盤。<br>
            5. <b>避險：</b> 若股票在右側「剔除區」，且外資連續賣超，千萬別去接刀 (外資部位太大，賣不完)。
        </div>
    </div>
    """, unsafe_allow_html=True)

    if msci_codes:
        prob_in = df_mcap[(df_mcap["排名"] <= 85) & (~df_mcap["股票代碼"].isin(msci_codes))]
        watch_in = df_mcap[(df_mcap["排名"] > 85) & (df_mcap["排名"] <= 100) & (~df_mcap["股票代碼"].isin(msci_codes))]
        prob_out = df_mcap[(df_mcap["排名"] > 100) & (df_mcap["股票代碼"].isin(msci_codes))]
        
        all_codes = list(prob_in["股票代碼"]) + list(watch_in["股票代碼"]) + list(prob_out["股票代碼"])
        
        c1, c2 = st.columns(2)
        with c1:
            st.success("🟢 **潛在納入 (外資買盤)**")
            if not prob_in.empty:
                st.dataframe(enrich_df(prob_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)
            if not watch_in.empty:
                st.markdown("**🧐 邊緣觀察**")
                st.dataframe(enrich_df(watch_in, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

        with c2:
            st.error("🔴 **潛在剔除 (外資賣盤)**")
            if not prob_out.empty:
                st.dataframe(enrich_df(prob_out, all_codes)[["排名","連結代碼","股票名稱","現價","成交值","漲跌幅","成交量"]], hide_index=True, column_config=column_cfg)

# ==================================================
# Tab 3: 0056/00878 高股息
# ==================================================
with tab3:
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📜 0056/00878 高股息預測 (SOP)</div>
        <div class="strategy-list">
            1. <b>核心邏輯：</b> 預測「未來殖利率」。高股息 ETF 必須剔除殖利率變低、納入殖利率變高者。選股池多為 Rank 50~150。<br>
            2. <b>進場時機 (佈局期)：</b> <span class="buy-signal">公告前 1 個月</span>。找出 Rank 50~150 且「尚未入選」的遺珠，配合「殖利率 > 5%」且「成交量放大」者。<br>
            3. <b>出場時機 (收割期)：</b> <span class="sell-signal">公告日 (見報日)</span>。高股息調整通常會吸引散戶追價，公告當天利多見報時，往往是短線高點，可先行獲利了結。<br>
            4. <b>操作細節：</b> 善用下方「資金熱度」排序，找出投信正在偷吃貨的標的。<br>
            5. <b>避險：</b> 殖利率陷阱 (賺了股息賠了價差)。若股價已在歷史高檔，即便納入也不宜追高。
        </div>
    </div>
    """, unsafe_allow_html=True)

    mid_cap = df_mcap[(df_mcap["排名"] >= 50) & (df_mcap["排名"] <= 150)].copy()
    
    def check_status(name):
        tags = []
        if name in holdings["0056"]: tags.append("0056")
        if name in holdings["00878"]: tags.append("00878")
        if name in holdings["00919"]: tags.append("00919")
        return ", ".join(tags) if tags else "-"
    
    mid_cap["已入選 ETF"] = mid_cap["股票名稱"].apply(check_status)
    
    codes = list(mid_cap["股票代碼"])
    c1, c2 = st.columns([1, 2])
    with c1:
        sort_method = st.radio("🔍 掃描模式：", ["💰 資金熱度 (抓投信)", "🔥 量能爆發 (抓偷跑)", "💎 尚未入選 (抓遺珠)"])

    if sort_method == "💰 資金熱度 (抓投信)":
        df_show = enrich_df(mid_cap, codes).sort_values("raw_turnover", ascending=False).head(30)
    elif sort_method == "🔥 量能爆發 (抓偷跑)":
        df_show = enrich_df(mid_cap, codes).sort_values("raw_vol", ascending=False).head(30)
    else:
        df_show = enrich_df(mid_cap[mid_cap["已入選 ETF"] == "-"], codes).sort_values("排名").head(30)

    st.dataframe(
        df_show[["排名", "連結代碼", "股票名稱", "已入選 ETF", "現價", "成交值", "漲跌幅", "成交量"]],
        use_container_width=True,
        hide_index=True,
        column_config=column_cfg
    )

# ==================================================
# Tab 4: 全市場權重 (Top 150)
# ==================================================
with tab4:
    st.markdown("""
    <div class="strategy-box">
        <div class="strategy-title">📊 全市場市值權重排行 (Top 150)</div>
        <div class="strategy-list">
            這是台股的「地圖」。前 150 檔股票佔了大盤約 90% 的市值。<br>
            <b>權重(Top150)：</b> 該股佔前150大總市值的百分比 (近似大盤權重)。<br>
            <b>用途：</b> 觀察權值股的資金流向，判斷大盤指數的多空。
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    top150 = df_mcap.head(150).copy()
    codes_150 = list(top150["股票代碼"])
    
    with st.spinner("正在計算 150 檔權值股權重..."):
        df_150 = enrich_df(top150, codes_150, add_weight=True)
    
    st.dataframe(
        df_150[["排名", "連結代碼", "股票名稱", "權重(Top150)", "總市值", "現價", "成交值", "漲跌幅"]],
        use_container_width=True,
        hide_index=True,
        column_config=column_cfg
    )
