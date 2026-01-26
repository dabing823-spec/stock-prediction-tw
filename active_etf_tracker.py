"""
主動型 ETF 持股追蹤模組
追蹤 00981A 等主動型 ETF 的持股變化，發掘建倉機會
"""
import os
import re
import time
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum

import pandas as pd
import requests
import streamlit as st

try:
    import yfinance as yf
except ImportError:
    yf = None


# =============================================================================
# 常數與設定
# =============================================================================

class PositionChangeType(Enum):
    """持股變動類型"""
    NEW = "新建倉"
    INCREASE = "加碼"
    DECREASE = "減碼"
    EXIT = "出清"
    UNCHANGED = "持平"


@dataclass
class ETFHolding:
    """ETF 持股資料"""
    code: str
    name: str
    shares: int
    weight: float
    price: Optional[float] = None
    value: Optional[float] = None


@dataclass
class HoldingChange:
    """持股變動"""
    code: str
    name: str
    weight: float
    shares_old: int
    shares_new: int
    shares_change: int
    change_pct: float
    change_type: PositionChangeType
    value_change: Optional[float] = None
    price: Optional[float] = None


@dataclass
class ETFSummary:
    """ETF 摘要指標"""
    units_outstanding: Optional[float] = None
    units_change: Optional[float] = None
    cash_amount: Optional[float] = None
    cash_change: Optional[float] = None
    cash_weight: Optional[float] = None
    cash_weight_change: Optional[float] = None
    nav_per_unit: Optional[float] = None
    nav_change: Optional[float] = None


@dataclass
class ComparisonResult:
    """比較結果"""
    date_new: str
    date_old: str
    new_positions: List[HoldingChange]
    increased: List[HoldingChange]
    decreased: List[HoldingChange]
    exited: List[HoldingChange]
    unchanged: List[HoldingChange]
    all_holdings: List[HoldingChange]
    summary: ETFSummary
    top_holdings: List[ETFHolding]


# 支援的主動型 ETF
ACTIVE_ETFS = {
    "00981A": {
        "name": "永豐台灣加權",
        "manager": "永豐投信",
        "description": "主動管理型台股 ETF",
    },
    "00905": {
        "name": "FT 臺灣 Smart",
        "manager": "富蘭克林華美",
        "description": "主動管理型台股 ETF",
    },
    "00912": {
        "name": "中信臺灣智慧 50",
        "manager": "中國信託",
        "description": "主動管理型台股 ETF",
    },
}


# =============================================================================
# 價格取得函數
# =============================================================================

def get_mis_prices(code: str, date_str: str) -> Optional[Tuple[float, float, float, float]]:
    """從證交所 MIS API 取得即時價格 (僅限今日)"""
    today_str = datetime.now().strftime("%Y%m%d")
    if date_str != today_str:
        return None
    try:
        for prefix in ('tse_', 'otc_'):
            url = f'https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={prefix}{code}.tw&json=1&delay=0'
            time.sleep(random.uniform(0.1, 0.3))
            r = requests.get(url, timeout=5)
            data = r.json()
            if 'msgArray' in data:
                for item in data['msgArray']:
                    if item.get('c') != code:
                        continue
                    o_val = item.get('o')
                    h_val = item.get('h')
                    l_val = item.get('l')
                    c_val = item.get('z') or item.get('oz') or item.get('ob')
                    if not all([o_val, h_val, l_val, c_val]) or '-' in [o_val, h_val, l_val, c_val]:
                        continue
                    try:
                        return float(o_val), float(h_val), float(l_val), float(c_val)
                    except:
                        continue
    except Exception as e:
        pass
    return None


def get_twse_prices(code: str, date_str: str) -> Optional[Tuple[float, float, float, float]]:
    """從證交所歷史資料取得價格"""
    today_str = datetime.now().strftime("%Y%m%d")
    if date_str >= today_str:
        return None
    y, m = int(date_str[:4]), int(date_str[4:6])
    month_first = f"{y}{m:02d}01"
    url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={month_first}&stockNo={code}'
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get('stat') == 'OK' and data.get('data'):
            def to_roc_date(s):
                yy, mm, dd = s.split('/')
                return f"{int(yy) + 1911:04d}{mm}{dd}"
            for row in data['data']:
                if to_roc_date(row[0]) == date_str:
                    try:
                        return (
                            float(row[3].replace(',', '')),
                            float(row[4].replace(',', '')),
                            float(row[5].replace(',', '')),
                            float(row[6].replace(',', ''))
                        )
                    except:
                        return None
    except Exception:
        pass
    return None


def get_yf_prices(code: str, date_str: str) -> Optional[Tuple[float, float, float, float]]:
    """從 yfinance 取得價格"""
    if yf is None:
        return None

    def try_yf(ticker):
        try:
            d = datetime.strptime(date_str, "%Y%m%d")
            df = yf.Ticker(ticker).history(
                start=d.strftime('%Y-%m-%d'),
                end=(d + timedelta(days=1)).strftime('%Y-%m-%d')
            )
            if df.empty:
                return None
            df = df.reset_index()
            df['Date'] = df['Date'].dt.strftime('%Y%m%d')
            idx_list = df.index[df['Date'] == date_str].tolist()
            if not idx_list:
                return None
            idx = idx_list[0]
            return (
                float(df.loc[idx, 'Open']),
                float(df.loc[idx, 'High']),
                float(df.loc[idx, 'Low']),
                float(df.loc[idx, 'Close'])
            )
        except Exception:
            return None

    result = try_yf(f"{code}.TWO")
    if result:
        return result
    return try_yf(f"{code}.TW")


def get_close_price(code: str, date_str: str) -> Optional[float]:
    """取得收盤價"""
    # 過濾無效代碼
    if not code or len(code) < 4 or not code.isdigit():
        return None

    p = get_mis_prices(code, date_str)
    if p:
        return p[3]
    p = get_twse_prices(code, date_str)
    if p:
        return p[3]
    p = get_yf_prices(code, date_str)
    if p:
        return p[3]
    return None


# =============================================================================
# Excel 解析函數
# =============================================================================

def find_stock_header_index(df_raw: pd.DataFrame) -> Optional[int]:
    """找到股票表格的標題列"""
    keywords = ['股票', '股票代號', '股票名稱', '股數']
    for idx, row in df_raw.iterrows():
        cells = row.astype(str).tolist()
        if all(any(k in c for c in cells) for k in keywords):
            return idx
    return None


def parse_weight_to_float(x) -> Optional[float]:
    """解析權重欄位"""
    try:
        s = str(x).strip()
        if s.endswith('%'):
            s = s[:-1]
        s = s.replace(',', '')
        return float(s)
    except Exception:
        return None


def try_parse_number(s: str) -> Optional[float]:
    """嘗試解析數字"""
    if s is None:
        return None
    t = str(s).strip()
    if not t or t == "nan":
        return None
    t = t.replace(',', '').replace(' ', '')
    t = re.split(r'[:：]', t)[-1]
    t = t.replace('元', '').replace('台幣', '').replace('新台幣', '')
    t = t.replace('份', '').replace('單位', '').replace('股', '')
    t = t.replace('％', '%')
    if t.endswith('%'):
        t = t[:-1]
    m = re.search(r'-?\d+(\.\d+)?', t)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def extract_value_by_keyword(df_raw: pd.DataFrame, keyword_list: List[str]) -> Optional[float]:
    """根據關鍵字從 DataFrame 提取數值"""
    try:
        n_rows, n_cols = df_raw.shape
        for i in range(n_rows):
            row = df_raw.iloc[i]
            for j in range(n_cols):
                cell = row.iloc[j]
                cell_str = "" if pd.isna(cell) else str(cell)
                if any(k in cell_str for k in keyword_list):
                    v = try_parse_number(cell_str)
                    if v is not None:
                        return v
                    for dj in (1, 2, 3):
                        jj = j + dj
                        if jj < n_cols:
                            v2 = try_parse_number(df_raw.iloc[i, jj])
                            if v2 is not None:
                                return v2
                    ii = i + 1
                    if ii < n_rows:
                        v3 = try_parse_number(df_raw.iloc[ii, j])
                        if v3 is not None:
                            return v3
        return None
    except Exception:
        return None


def parse_percent_cell(cell) -> Optional[float]:
    """解析百分比欄位"""
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    s = str(cell).strip()
    if not s or s.lower() == "nan":
        return None
    has_pct = ('%' in s) or ('％' in s)
    v = try_parse_number(s)
    if v is None:
        return None
    if has_pct:
        return v
    if 0 <= abs(v) <= 1:
        return v * 100
    return v


def extract_cash_weight(df_raw: pd.DataFrame) -> Optional[float]:
    """提取現金權重"""
    try:
        n_rows, n_cols = df_raw.shape
        header_row = None
        weight_col = None
        weight_keywords = ["權重", "比重", "weight", "%"]

        for i in range(min(n_rows, 80)):
            row_vals = ["" if pd.isna(x) else str(x).strip() for x in df_raw.iloc[i].tolist()]
            joined = " ".join(row_vals)
            if any(wk in joined for wk in weight_keywords):
                for j, v in enumerate(row_vals):
                    if any(wk in v for wk in ["權重", "比重", "weight"]):
                        header_row = i
                        weight_col = j
                        break
                if header_row is not None and weight_col is not None:
                    break

        if header_row is None or weight_col is None:
            return None

        cash_keywords = ["現金", "cash"]
        for i in range(header_row + 1, min(n_rows, header_row + 60)):
            row_vals = ["" if pd.isna(x) else str(x).strip() for x in df_raw.iloc[i].tolist()]
            if any(any(ck in v.lower() for ck in cash_keywords) for v in row_vals):
                if weight_col < n_cols:
                    val = parse_percent_cell(df_raw.iloc[i, weight_col])
                    if val is not None:
                        return val
        return None
    except Exception:
        return None


def extract_nav_per_unit(df_raw: pd.DataFrame) -> Optional[float]:
    """提取每單位淨值"""
    try:
        n_rows, n_cols = df_raw.shape
        header_row = None
        nav_col = None
        nav_keywords = ["每單位淨值", "單位淨值", "NAV", "nav"]
        fund_asset_keywords = ["基金資產"]

        for i in range(min(n_rows, 80)):
            row_vals = ["" if pd.isna(x) else str(x).strip() for x in df_raw.iloc[i].tolist()]
            joined = " ".join(row_vals)
            if any(k in joined for k in nav_keywords):
                for j, v in enumerate(row_vals):
                    if "每單位淨值" in v or "單位淨值" in v or v.lower() == "nav":
                        header_row = i
                        nav_col = j
                        break
                if header_row is not None and nav_col is not None:
                    break

        if header_row is None or nav_col is None:
            return None

        for i in range(header_row + 1, min(n_rows, header_row + 60)):
            row_vals = ["" if pd.isna(x) else str(x).strip() for x in df_raw.iloc[i].tolist()]
            if any(any(fk in v for fk in fund_asset_keywords) for v in row_vals):
                if nav_col < n_cols:
                    val = try_parse_number(df_raw.iloc[i, nav_col])
                    if val is not None:
                        return val
        return None
    except Exception:
        return None


# =============================================================================
# 核心比較邏輯
# =============================================================================

def parse_holdings_excel(file_content, is_streamlit_upload: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    解析持股 Excel 檔案
    返回: (raw_df, holdings_df)
    """
    if is_streamlit_upload:
        df_raw = pd.read_excel(file_content, header=None)
    else:
        df_raw = pd.read_excel(file_content, header=None)

    header_idx = find_stock_header_index(df_raw)
    if header_idx is None:
        raise ValueError("找不到股票表格標題列")

    if is_streamlit_upload:
        file_content.seek(0)
        df_holdings = pd.read_excel(file_content, header=header_idx)
    else:
        df_holdings = pd.read_excel(file_content, header=header_idx)

    return df_raw, df_holdings


def extract_etf_summary(df_raw_new: pd.DataFrame, df_raw_old: pd.DataFrame) -> ETFSummary:
    """提取 ETF 摘要指標"""
    # 流通在外單位數
    units_new = extract_value_by_keyword(df_raw_new, ["流通在外單位數", "流通在外", "在外單位", "受益權單位數"])
    units_old = extract_value_by_keyword(df_raw_old, ["流通在外單位數", "流通在外", "在外單位", "受益權單位數"])

    # 現金
    cash_new = extract_value_by_keyword(df_raw_new, ["現金"])
    cash_old = extract_value_by_keyword(df_raw_old, ["現金"])

    # 現金權重
    cash_weight_new = extract_cash_weight(df_raw_new)
    cash_weight_old = extract_cash_weight(df_raw_old)

    # 每單位淨值
    nav_new = extract_nav_per_unit(df_raw_new)
    nav_old = extract_nav_per_unit(df_raw_old)

    return ETFSummary(
        units_outstanding=units_new,
        units_change=(units_new - units_old) if units_new and units_old else None,
        cash_amount=cash_new,
        cash_change=(cash_new - cash_old) if cash_new and cash_old else None,
        cash_weight=cash_weight_new,
        cash_weight_change=(cash_weight_new - cash_weight_old) if cash_weight_new and cash_weight_old else None,
        nav_per_unit=nav_new,
        nav_change=(nav_new - nav_old) if nav_new and nav_old else None,
    )


def compare_holdings(
    df_new: pd.DataFrame,
    df_old: pd.DataFrame,
    df_raw_new: pd.DataFrame,
    df_raw_old: pd.DataFrame,
    date_new: str,
    date_old: str,
    fetch_prices: bool = True
) -> ComparisonResult:
    """
    比較兩期持股變化
    """
    # 標準化欄位
    required_cols = ['股票代號', '股票名稱', '股數']
    for df in [df_new, df_old]:
        df['股票代號'] = df['股票代號'].astype(str).str.strip()
        df['股票名稱'] = df['股票名稱'].astype(str).str.strip()

    # 準備比較用 DataFrame
    df_new_prep = df_new[['股票代號', '股票名稱', '股數']].copy()
    df_new_prep.rename(columns={'股數': '股數_new', '股票名稱': '名稱_new'}, inplace=True)

    if '持股權重' in df_new.columns:
        df_new_prep['權重'] = df_new['持股權重'].apply(parse_weight_to_float)
    else:
        df_new_prep['權重'] = 0.0

    df_old_prep = df_old[['股票代號', '股票名稱', '股數']].copy()
    df_old_prep.rename(columns={'股數': '股數_old', '股票名稱': '名稱_old'}, inplace=True)

    # 合併
    merged = pd.merge(df_old_prep, df_new_prep, on='股票代號', how='outer')
    merged['股票名稱'] = merged['名稱_new'].combine_first(merged['名稱_old'])

    # 數值處理
    merged['股數_old'] = pd.to_numeric(
        merged['股數_old'].astype(str).str.replace(',', ''),
        errors='coerce'
    ).fillna(0).astype(int)
    merged['股數_new'] = pd.to_numeric(
        merged['股數_new'].astype(str).str.replace(',', ''),
        errors='coerce'
    ).fillna(0).astype(int)
    merged['股數變化'] = merged['股數_new'] - merged['股數_old']
    merged['權重'] = merged['權重'].fillna(0)

    # 取得價格
    prices = {}
    if fetch_prices:
        unique_codes = merged['股票代號'].unique()
        for code in unique_codes:
            if code and len(code) >= 4:
                prices[code] = get_close_price(code, date_new)

    # 分類變動
    new_positions = []
    increased = []
    decreased = []
    exited = []
    unchanged = []
    all_holdings = []

    for _, row in merged.iterrows():
        code = row['股票代號']
        name = row['股票名稱']
        weight = row['權重']
        old_shares = row['股數_old']
        new_shares = row['股數_new']
        change = row['股數變化']

        # 計算變動百分比
        if old_shares > 0:
            change_pct = (change / old_shares) * 100
        elif new_shares > 0:
            change_pct = 100.0  # 新建倉
        else:
            change_pct = 0.0

        # 決定類型
        if old_shares == 0 and new_shares > 0:
            change_type = PositionChangeType.NEW
        elif old_shares > 0 and new_shares == 0:
            change_type = PositionChangeType.EXIT
        elif change > 0:
            change_type = PositionChangeType.INCREASE
        elif change < 0:
            change_type = PositionChangeType.DECREASE
        else:
            change_type = PositionChangeType.UNCHANGED

        # 計算價值變動
        price = prices.get(code)
        value_change = (change * price) if price else None

        holding_change = HoldingChange(
            code=code,
            name=name,
            weight=weight,
            shares_old=old_shares,
            shares_new=new_shares,
            shares_change=change,
            change_pct=change_pct,
            change_type=change_type,
            value_change=value_change,
            price=price
        )

        all_holdings.append(holding_change)

        if change_type == PositionChangeType.NEW:
            new_positions.append(holding_change)
        elif change_type == PositionChangeType.INCREASE:
            increased.append(holding_change)
        elif change_type == PositionChangeType.DECREASE:
            decreased.append(holding_change)
        elif change_type == PositionChangeType.EXIT:
            exited.append(holding_change)
        else:
            unchanged.append(holding_change)

    # 排序
    new_positions.sort(key=lambda x: x.weight, reverse=True)
    increased.sort(key=lambda x: x.change_pct, reverse=True)
    decreased.sort(key=lambda x: x.change_pct)
    exited.sort(key=lambda x: x.shares_old, reverse=True)

    # 提取 ETF 摘要
    summary = extract_etf_summary(df_raw_new, df_raw_old)

    # Top 持股
    top_holdings = []
    df_top = df_new.copy()
    if '持股權重' in df_top.columns:
        df_top['權重_sort'] = df_top['持股權重'].apply(parse_weight_to_float)
        df_top = df_top.sort_values('權重_sort', ascending=False).head(20)
        for _, row in df_top.iterrows():
            code = str(row['股票代號']).strip()
            top_holdings.append(ETFHolding(
                code=code,
                name=str(row['股票名稱']).strip(),
                shares=int(str(row['股數']).replace(',', '')),
                weight=parse_weight_to_float(row['持股權重']) or 0,
                price=prices.get(code),
            ))

    return ComparisonResult(
        date_new=date_new,
        date_old=date_old,
        new_positions=new_positions,
        increased=increased,
        decreased=decreased,
        exited=exited,
        unchanged=unchanged,
        all_holdings=all_holdings,
        summary=summary,
        top_holdings=top_holdings
    )


# =============================================================================
# 格式化函數
# =============================================================================

def format_amount(n: float) -> str:
    """格式化金額"""
    if n is None or pd.isna(n):
        return "—"
    n = float(n)
    absn = abs(n)
    sign = "-" if n < 0 else "+" if n > 0 else ""
    YI = 100_000_000
    WAN = 10_000
    if absn >= YI:
        val = absn / YI
        s = f"{val:.2f}億"
    elif absn >= WAN:
        val = absn / WAN
        s = f"{val:.1f}萬"
    else:
        s = f"{int(round(absn)):,}"
    return sign + s


def format_shares(n: int) -> str:
    """格式化股數"""
    if n is None:
        return "—"
    return f"{n:,}"


def format_pct(n: float, show_sign: bool = True) -> str:
    """格式化百分比"""
    if n is None or pd.isna(n):
        return "—"
    if show_sign:
        return f"{n:+.1f}%"
    return f"{n:.1f}%"


# =============================================================================
# Streamlit 快取
# =============================================================================

@st.cache_data(ttl=300)
def get_cached_prices(codes: List[str], date_str: str) -> Dict[str, Optional[float]]:
    """快取價格查詢"""
    prices = {}
    for code in codes:
        if code and len(code) >= 4:
            prices[code] = get_close_price(code, date_str)
    return prices
