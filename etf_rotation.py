"""
ETF 輪動策略模組
追蹤主題型 ETF 表現，提供輪動建議
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
import streamlit as st

from config import CACHE_TTL_SHORT


# =============================================================================
# ETF 配置
# =============================================================================

@dataclass
class ETFInfo:
    """ETF 資訊"""
    code: str
    name: str
    category: str
    description: str
    expense_ratio: float  # 內扣費用 %
    dividend_months: List[int]  # 配息月份


# 主題型 ETF 清單
THEME_ETFS = [
    # 半導體
    ETFInfo("00891", "中信關鍵半導體", "半導體", "追蹤台灣半導體供應鏈", 0.40, [2, 5, 8, 11]),
    ETFInfo("00892", "富邦台灣半導體", "半導體", "追蹤 ICE 台灣半導體指數", 0.35, [1, 4, 7, 10]),
    ETFInfo("00927", "群益半導體收益", "半導體", "半導體 + 高股息雙主題", 0.45, [3, 6, 9, 12]),

    # 5G / 電子
    ETFInfo("00881", "國泰台灣5G+", "5G/電子", "追蹤台灣 5G+ 通訊指數", 0.40, [2, 5, 8, 11]),
    ETFInfo("00876", "元大未來關鍵科技", "科技", "追蹤全球關鍵科技股", 0.55, [7]),

    # 高股息
    ETFInfo("0056", "元大高股息", "高股息", "市值前150大殖利率前30", 0.30, [1, 4, 7, 10]),
    ETFInfo("00878", "國泰永續高股息", "高股息", "ESG + 高股息雙篩選", 0.25, [2, 5, 8, 11]),
    ETFInfo("00919", "群益台灣精選高息", "高股息", "殖利率 + 獲利能力篩選", 0.30, [3, 6, 9, 12]),
    ETFInfo("00929", "復華台灣科技優息", "科技高息", "科技股 + 月配息", 0.35, list(range(1, 13))),

    # 市值型
    ETFInfo("0050", "元大台灣50", "市值型", "追蹤台灣前50大市值股", 0.32, [1, 7]),
    ETFInfo("006208", "富邦台50", "市值型", "追蹤台灣前50大市值股", 0.15, [7, 11]),
]

# 依類別分組
ETF_CATEGORIES = {
    "半導體": ["00891", "00892", "00927"],
    "5G/電子": ["00881", "00876"],
    "高股息": ["0056", "00878", "00919", "00929"],
    "市值型": ["0050", "006208"],
}


# =============================================================================
# 數據獲取
# =============================================================================

@st.cache_data(ttl=CACHE_TTL_SHORT)
def fetch_etf_performance(codes: List[str], period: str = "3mo") -> Dict[str, Dict[str, Any]]:
    """
    批量獲取 ETF 績效數據
    """
    result = {}
    tickers_str = " ".join([f"{c}.TW" for c in codes])

    try:
        tickers = yf.Tickers(tickers_str)

        for code in codes:
            try:
                ticker = tickers.tickers.get(f"{code}.TW")
                if not ticker:
                    result[code] = _empty_performance()
                    continue

                hist = ticker.history(period=period)
                if hist.empty or len(hist) < 2:
                    result[code] = _empty_performance()
                    continue

                # 計算績效指標
                current_price = hist["Close"].iloc[-1]
                start_price = hist["Close"].iloc[0]
                high_price = hist["Close"].max()
                low_price = hist["Close"].min()

                # 報酬率
                period_return = ((current_price - start_price) / start_price) * 100

                # 最大回撤
                rolling_max = hist["Close"].expanding().max()
                drawdown = ((hist["Close"] - rolling_max) / rolling_max) * 100
                max_drawdown = drawdown.min()

                # 波動率 (年化)
                daily_returns = hist["Close"].pct_change().dropna()
                volatility = daily_returns.std() * (252 ** 0.5) * 100

                # 成交量
                avg_volume = hist["Volume"].mean()

                # 距離高點
                from_high = ((current_price - high_price) / high_price) * 100

                result[code] = {
                    "現價": round(current_price, 2),
                    "報酬率": round(period_return, 2),
                    "最大回撤": round(max_drawdown, 2),
                    "波動率": round(volatility, 2),
                    "距高點": round(from_high, 2),
                    "日均量": int(avg_volume / 1000),  # 張
                    "raw_return": period_return,
                    "raw_drawdown": max_drawdown,
                    "raw_volatility": volatility,
                }

            except Exception as e:
                print(f"Error fetching {code}: {e}")
                result[code] = _empty_performance()

    except Exception as e:
        print(f"Batch ETF fetch error: {e}")
        for code in codes:
            result[code] = _empty_performance()

    return result


def _empty_performance() -> Dict[str, Any]:
    """空績效數據"""
    return {
        "現價": "-",
        "報酬率": "-",
        "最大回撤": "-",
        "波動率": "-",
        "距高點": "-",
        "日均量": "-",
        "raw_return": 0,
        "raw_drawdown": 0,
        "raw_volatility": 0,
    }


# =============================================================================
# 輪動策略計算
# =============================================================================

@dataclass
class RotationSignal:
    """輪動信號"""
    code: str
    name: str
    signal: str  # "強勢", "觀望", "弱勢"
    score: float
    reason: str


def calculate_rotation_signals(
    performance: Dict[str, Dict[str, Any]],
    category: str
) -> List[RotationSignal]:
    """
    計算 ETF 輪動信號

    評分邏輯:
    - 報酬率越高越好 (+)
    - 最大回撤越小越好 (+)
    - 波動率適中 (太高扣分)
    - 距高點越近越好 (+)
    """
    codes = ETF_CATEGORIES.get(category, [])
    signals = []

    for code in codes:
        perf = performance.get(code, {})
        etf_info = next((e for e in THEME_ETFS if e.code == code), None)

        if not etf_info:
            continue

        ret = perf.get("raw_return", 0)
        dd = perf.get("raw_drawdown", 0)
        vol = perf.get("raw_volatility", 0)
        from_high = perf.get("距高點", 0)

        # 評分計算
        score = 0
        reasons = []

        # 報酬率評分 (權重 40%)
        if ret > 10:
            score += 40
            reasons.append("報酬率優異")
        elif ret > 5:
            score += 30
            reasons.append("報酬率良好")
        elif ret > 0:
            score += 20
            reasons.append("正報酬")
        elif ret > -5:
            score += 10
            reasons.append("小幅回檔")
        else:
            reasons.append("報酬率偏弱")

        # 回撤評分 (權重 30%)
        if dd > -5:
            score += 30
            reasons.append("回撤控制佳")
        elif dd > -10:
            score += 20
            reasons.append("回撤可接受")
        elif dd > -15:
            score += 10
            reasons.append("回撤偏大")
        else:
            reasons.append("回撤過大")

        # 波動率評分 (權重 15%)
        if 10 < vol < 25:
            score += 15
            reasons.append("波動適中")
        elif vol < 10:
            score += 10
            reasons.append("波動偏低")
        else:
            score += 5
            reasons.append("波動偏高")

        # 距高點評分 (權重 15%)
        if isinstance(from_high, (int, float)):
            if from_high > -3:
                score += 15
                reasons.append("接近高點")
            elif from_high > -10:
                score += 10
                reasons.append("距高點適中")
            else:
                score += 5
                reasons.append("距高點較遠")

        # 判斷信號
        if score >= 70:
            signal = "強勢"
        elif score >= 50:
            signal = "觀望"
        else:
            signal = "弱勢"

        signals.append(RotationSignal(
            code=code,
            name=etf_info.name,
            signal=signal,
            score=score,
            reason="、".join(reasons[:2])  # 取前兩個原因
        ))

    # 依分數排序
    signals.sort(key=lambda x: x.score, reverse=True)
    return signals


# =============================================================================
# 除息日追蹤
# =============================================================================

def get_upcoming_dividends() -> List[Dict[str, Any]]:
    """
    取得即將到來的配息資訊
    """
    current_month = datetime.now().month
    next_month = (current_month % 12) + 1

    upcoming = []

    for etf in THEME_ETFS:
        # 檢查本月和下月是否有配息
        if current_month in etf.dividend_months:
            upcoming.append({
                "code": etf.code,
                "name": etf.name,
                "month": current_month,
                "status": "本月配息",
                "urgency": "high"
            })
        elif next_month in etf.dividend_months:
            upcoming.append({
                "code": etf.code,
                "name": etf.name,
                "month": next_month,
                "status": "下月配息",
                "urgency": "medium"
            })

    # 依緊急程度排序
    upcoming.sort(key=lambda x: 0 if x["urgency"] == "high" else 1)
    return upcoming


# =============================================================================
# 建立比較 DataFrame
# =============================================================================

def build_etf_comparison_df(
    codes: List[str],
    performance: Dict[str, Dict[str, Any]]
) -> pd.DataFrame:
    """建立 ETF 比較表"""
    rows = []

    for code in codes:
        etf_info = next((e for e in THEME_ETFS if e.code == code), None)
        perf = performance.get(code, {})

        if etf_info:
            rows.append({
                "代碼": code,
                "名稱": etf_info.name,
                "類別": etf_info.category,
                "現價": perf.get("現價", "-"),
                "報酬率(%)": perf.get("報酬率", "-"),
                "最大回撤(%)": perf.get("最大回撤", "-"),
                "波動率(%)": perf.get("波動率", "-"),
                "距高點(%)": perf.get("距高點", "-"),
                "日均量(張)": perf.get("日均量", "-"),
                "內扣(%)": etf_info.expense_ratio,
                "連結": f"https://tw.stock.yahoo.com/quote/{code}.TW",
                "raw_return": perf.get("raw_return", 0),
            })

    df = pd.DataFrame(rows)
    return df.sort_values("raw_return", ascending=False)
