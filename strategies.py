"""
策略計算模組
"""
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import yfinance as yf

from config import (
    THRESHOLD_0050_MUST_IN, THRESHOLD_0050_MUST_OUT,
    THRESHOLD_MSCI_PROB_IN, THRESHOLD_MSCI_PROB_OUT,
    THRESHOLD_0056_RANK_MIN, THRESHOLD_0056_RANK_MAX,
    HIGH_YIELD_SCHEDULES, TECH_SECTORS, TOP_50_LIMIT
)
from data_fetcher import (
    get_stock_info_batch, get_market_cap_batch,
    get_sector_batch, get_dividend_yield_batch
)


@dataclass
class StrategyResult:
    """策略分析結果"""
    potential_in: pd.DataFrame
    potential_out: pd.DataFrame
    all_codes: List[str]


def enrich_dataframe(
    df: pd.DataFrame,
    codes: List[str],
    add_weight: bool = False
) -> pd.DataFrame:
    """
    豐富 DataFrame 資料 (加入即時行情)
    """
    if df.empty:
        return df

    df = df.copy()
    info = get_stock_info_batch(codes)

    df["現價"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("現價", "-"))
    df["漲跌幅"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("漲跌", "-"))
    df["成交量"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("量能", "-"))
    df["成交值"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("成交值", "-"))
    df["raw_turnover"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("raw_turnover", 0))
    df["raw_vol"] = df["股票代碼"].map(lambda x: info.get(x, {}).get("raw_vol", 0))
    df["連結代碼"] = df["股票代碼"].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")

    if add_weight:
        weight_info = get_market_cap_batch(codes)
        df["總市值"] = df["股票代碼"].map(lambda x: weight_info.get(x, {}).get("市值", "-"))
        df["權重(Top150)"] = df["股票代碼"].map(lambda x: weight_info.get(x, {}).get("權重", "-"))

    return df


# =============================================================================
# 0050 策略
# =============================================================================

def analyze_0050_strategy(
    df_mcap: pd.DataFrame,
    holdings_0050: set
) -> StrategyResult:
    """
    0050 吃豆腐策略分析

    - 市值排名 ≤ 40 且未入選 → 潛在納入
    - 市值排名 > 60 且已入選 → 潛在剔除
    """
    df_analysis = df_mcap.head(100).copy()
    df_analysis["in_0050"] = df_analysis["股票名稱"].isin(holdings_0050)

    potential_in = df_analysis[
        (df_analysis["排名"] <= THRESHOLD_0050_MUST_IN) &
        (~df_analysis["in_0050"])
    ].copy()

    potential_out = df_analysis[
        (df_analysis["排名"] > THRESHOLD_0050_MUST_OUT) &
        (df_analysis["in_0050"])
    ].copy()

    all_codes = list(potential_in["股票代碼"]) + list(potential_out["股票代碼"])

    return StrategyResult(
        potential_in=potential_in,
        potential_out=potential_out,
        all_codes=all_codes
    )


# =============================================================================
# MSCI 策略
# =============================================================================

def analyze_msci_strategy(
    df_mcap: pd.DataFrame,
    msci_codes: List[str]
) -> StrategyResult:
    """
    MSCI 波動策略分析

    - 市值排名 ≤ 85 且未入選 MSCI → 潛在納入
    - 市值排名 > 100 且已入選 MSCI → 潛在剔除
    """
    msci_set = set(msci_codes)

    potential_in = df_mcap[
        (df_mcap["排名"] <= THRESHOLD_MSCI_PROB_IN) &
        (~df_mcap["股票代碼"].isin(msci_set))
    ].copy()

    potential_out = df_mcap[
        (df_mcap["排名"] > THRESHOLD_MSCI_PROB_OUT) &
        (df_mcap["股票代碼"].isin(msci_set))
    ].copy()

    all_codes = list(potential_in["股票代碼"]) + list(potential_out["股票代碼"])

    return StrategyResult(
        potential_in=potential_in,
        potential_out=potential_out,
        all_codes=all_codes
    )


# =============================================================================
# 0056 高股息策略
# =============================================================================

@dataclass
class HighYieldResult:
    """高股息策略結果"""
    df: pd.DataFrame
    codes: List[str]


def analyze_0056_strategy(
    df_mcap: pd.DataFrame,
    all_holdings: Dict[str, set]
) -> HighYieldResult:
    """
    0056 高股息策略分析

    選股池: 市值排名 50-150
    """
    mid_cap = df_mcap[
        (df_mcap["排名"] >= THRESHOLD_0056_RANK_MIN) &
        (df_mcap["排名"] <= THRESHOLD_0056_RANK_MAX)
    ].copy()

    # 標記已入選的 ETF
    mid_cap["已入選 ETF"] = mid_cap["股票名稱"].apply(
        lambda x: ", ".join([etf for etf, holdings in all_holdings.items() if x in holdings])
    )

    codes = list(mid_cap["股票代碼"])

    return HighYieldResult(df=mid_cap, codes=codes)


def enrich_with_dividend_yield(
    df: pd.DataFrame,
    codes: List[str]
) -> pd.DataFrame:
    """為 DataFrame 加入殖利率資訊"""
    df = df.copy()
    yield_data = get_dividend_yield_batch(codes)

    df["raw_yield"] = df["股票代碼"].map(lambda x: yield_data.get(x, 0))
    df["殖利率(%)"] = df["raw_yield"].apply(lambda x: f"{x:.2f}%")

    return df


def filter_high_yield_stocks(
    df: pd.DataFrame,
    mode: str
) -> pd.DataFrame:
    """
    依模式篩選高股息股票

    mode: "yield" | "volume" | "not_selected"
    """
    df = df.copy()

    if mode == "yield":
        return df.sort_values("raw_yield", ascending=False).head(30)
    elif mode == "volume":
        return df.sort_values("raw_vol", ascending=False).head(30)
    else:  # not_selected
        return df[df["已入選 ETF"] == ""].sort_values("排名").head(30)


# =============================================================================
# 電子 Alpha 對沖策略
# =============================================================================

@dataclass
class AlphaHedgeResult:
    """Alpha 對沖策略結果"""
    long_positions: Optional[pd.DataFrame]
    short_info: Optional[Dict[str, Any]]
    debug_df: pd.DataFrame
    success: bool


def calculate_tech_alpha_portfolio(
    total_capital: int,
    hedge_ratio: float,
    df_mcap: pd.DataFrame
) -> AlphaHedgeResult:
    """
    電子權值 Alpha 對沖策略

    從 Top 50 市值中篩選電子/半導體股做多，
    同時計算需要放空的台指期口數
    """
    # 取 Top 50
    top50_df = df_mcap.head(TOP_50_LIMIT).copy()
    top50_codes = top50_df["股票代碼"].tolist()

    # 獲取產業分類
    sector_map = get_sector_batch(top50_codes)
    top50_df["Sector"] = top50_df["股票代碼"].map(sector_map)

    # 篩選電子/半導體股
    tech_df = top50_df[top50_df["Sector"].isin(TECH_SECTORS)].copy()

    if tech_df.empty:
        return AlphaHedgeResult(
            long_positions=None,
            short_info=None,
            debug_df=top50_df[["股票名稱", "Sector"]],
            success=False
        )

    target_codes = tech_df["股票代碼"].tolist()

    # 獲取市值權重
    weight_info = get_market_cap_batch(target_codes)
    tech_df["raw_mcap"] = tech_df["股票代碼"].map(
        lambda x: weight_info.get(x, {}).get("raw_mcap", 0)
    )

    total_mcap = tech_df["raw_mcap"].sum()
    tech_df["配置權重(%)"] = tech_df["raw_mcap"] / total_mcap

    # 獲取即時價格
    price_info = get_stock_info_batch(target_codes)
    tech_df["現價"] = tech_df["股票代碼"].map(
        lambda x: price_info.get(x, {}).get("raw_price", 0)
    )

    # 計算配置
    tech_df["分配金額"] = total_capital * tech_df["配置權重(%)"]
    tech_df["建議買進(股)"] = (tech_df["分配金額"] / tech_df["現價"]).fillna(0).astype(int)

    # 格式化顯示
    tech_df["連結代碼"] = tech_df["股票代碼"].apply(
        lambda x: f"https://tw.stock.yahoo.com/quote/{x}"
    )
    tech_df["配置權重(%)"] = (tech_df["配置權重(%)"] * 100).map(lambda x: f"{x:.2f}%")
    tech_df["分配金額"] = tech_df["分配金額"].map(lambda x: f"${int(x):,}")

    # 計算空方部位 (台指期)
    try:
        twii_price = yf.Ticker("^TWII").history(period="1d")["Close"].iloc[-1]
    except Exception:
        twii_price = 23000  # Fallback

    short_value_needed = total_capital / hedge_ratio
    micro_contract_val = twii_price * 10  # 微台指每點 10 元
    num_micro = short_value_needed / micro_contract_val

    short_info = {
        "index_price": int(twii_price),
        "micro_val": int(micro_contract_val),
        "short_value": int(short_value_needed),
        "contracts": round(num_micro, 1)
    }

    return AlphaHedgeResult(
        long_positions=tech_df,
        short_info=short_info,
        debug_df=top50_df[["股票名稱", "Sector"]],
        success=True
    )


# =============================================================================
# 輔助函數
# =============================================================================

def get_active_high_yield_schedules() -> List[str]:
    """取得本月有調整的高股息 ETF"""
    current_month = date.today().month
    active = [
        schedule.name
        for schedule in HIGH_YIELD_SCHEDULES
        if current_month in schedule.adjustment_months
    ]
    return active
