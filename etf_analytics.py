"""
ETF 進階分析模組
- 現金水位監控
- 持股週期分析
- 部位權重訊號
"""
import os
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd
import streamlit as st

from active_etf_tracker import (
    get_available_dates,
    load_holdings_from_drive,
    extract_cash_weight,
    extract_nav_per_unit,
    extract_value_by_keyword,
    parse_weight_to_float,
    find_stock_header_index,
    ACTIVE_ETFS,
)


# =============================================================================
# 資料結構
# =============================================================================

@dataclass
class CashLevelRecord:
    """現金水位記錄"""
    date: str
    cash_weight: float
    cash_amount: Optional[float]
    nav: Optional[float]
    units_outstanding: Optional[float]


@dataclass
class HoldingRecord:
    """持股記錄"""
    code: str
    name: str
    date: str
    shares: int
    weight: float


@dataclass
class StockHoldingHistory:
    """個股持有歷史"""
    code: str
    name: str
    first_seen: str
    last_seen: str
    records: List[HoldingRecord]
    is_active: bool
    holding_days: int
    weight_trend: str  # "increasing", "decreasing", "stable"
    max_weight: float
    current_weight: float


@dataclass
class WeightSignal:
    """權重訊號"""
    code: str
    name: str
    current_weight: float
    prev_weight: float
    weight_change: float
    weight_rank: int
    prev_rank: int
    rank_change: int
    signal: str  # "高信心加碼", "持續看好", "信心下降", "新進場", "已出清"
    conviction_level: str  # "高", "中", "低"


# =============================================================================
# 歷史資料載入
# =============================================================================

@st.cache_data(ttl=600)
def load_historical_data(etf_code: str, num_dates: int = 10) -> Dict[str, Any]:
    """
    載入多期歷史資料
    返回: {"dates": [...], "holdings": {date: [holdings]}, "summaries": {date: summary}}
    """
    available = get_available_dates(etf_code)
    if not available:
        return {"dates": [], "holdings": {}, "summaries": {}}

    # 取最近 N 期
    dates_to_load = available[:num_dates]

    holdings_by_date = {}
    summaries_by_date = {}

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, date_info in enumerate(dates_to_load):
        date_str = date_info["date"]
        status_text.text(f"載入 {date_info['display']}...")

        df_raw, df_holdings = load_holdings_from_drive(date_info)

        if df_raw is not None and df_holdings is not None:
            # 解析持股
            holdings = []
            for _, row in df_holdings.iterrows():
                try:
                    code = str(row.get("股票代號", "")).strip()
                    name = str(row.get("股票名稱", "")).strip()
                    shares_raw = row.get("股數", 0)
                    weight_raw = row.get("持股權重", 0)

                    if not code or len(code) < 4:
                        continue

                    shares = int(str(shares_raw).replace(",", "")) if shares_raw else 0
                    weight = parse_weight_to_float(weight_raw) or 0

                    holdings.append(HoldingRecord(
                        code=code,
                        name=name,
                        date=date_str,
                        shares=shares,
                        weight=weight
                    ))
                except Exception:
                    continue

            holdings_by_date[date_str] = holdings

            # 解析摘要
            cash_weight = extract_cash_weight(df_raw)
            cash_amount = extract_value_by_keyword(df_raw, ["現金"])
            nav = extract_nav_per_unit(df_raw)
            units = extract_value_by_keyword(df_raw, ["流通在外單位數", "受益權單位數"])

            summaries_by_date[date_str] = CashLevelRecord(
                date=date_str,
                cash_weight=cash_weight or 0,
                cash_amount=cash_amount,
                nav=nav,
                units_outstanding=units
            )

        progress_bar.progress((i + 1) / len(dates_to_load))

    progress_bar.empty()
    status_text.empty()

    # 按日期排序 (舊到新)
    sorted_dates = sorted(holdings_by_date.keys())

    return {
        "dates": sorted_dates,
        "holdings": holdings_by_date,
        "summaries": summaries_by_date
    }


# =============================================================================
# 現金水位分析
# =============================================================================

def analyze_cash_levels(historical_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析現金水位趨勢
    """
    summaries = historical_data.get("summaries", {})
    dates = historical_data.get("dates", [])

    if not dates:
        return {"records": [], "trend": "unknown", "alert": None}

    records = []
    for date in dates:
        summary = summaries.get(date)
        if summary:
            records.append(summary)

    if len(records) < 2:
        return {"records": records, "trend": "unknown", "alert": None}

    # 計算趨勢
    recent_cash = records[-1].cash_weight if records else 0
    prev_cash = records[-2].cash_weight if len(records) > 1 else 0
    avg_cash = sum(r.cash_weight for r in records) / len(records) if records else 0

    # 判斷趨勢
    if recent_cash > prev_cash + 1:
        trend = "increasing"
    elif recent_cash < prev_cash - 1:
        trend = "decreasing"
    else:
        trend = "stable"

    # 警示
    alert = None
    if recent_cash > 5:
        alert = {
            "level": "warning",
            "message": f"現金水位偏高 ({recent_cash:.2f}%)，經理人可能預期回檔"
        }
    elif recent_cash < 1:
        alert = {
            "level": "info",
            "message": f"現金水位極低 ({recent_cash:.2f}%)，經理人滿倉操作"
        }
    elif recent_cash > avg_cash * 1.5:
        alert = {
            "level": "warning",
            "message": f"現金水位突然上升 ({prev_cash:.2f}% → {recent_cash:.2f}%)，注意獲利了結訊號"
        }

    return {
        "records": records,
        "trend": trend,
        "current": recent_cash,
        "previous": prev_cash,
        "average": avg_cash,
        "alert": alert
    }


# =============================================================================
# 持股週期分析
# =============================================================================

def analyze_holding_periods(historical_data: Dict[str, Any]) -> List[StockHoldingHistory]:
    """
    分析各股票的持有週期
    """
    holdings_by_date = historical_data.get("holdings", {})
    dates = historical_data.get("dates", [])

    if not dates:
        return []

    # 建立每檔股票的歷史記錄
    stock_history: Dict[str, List[HoldingRecord]] = defaultdict(list)

    for date in dates:
        holdings = holdings_by_date.get(date, [])
        for h in holdings:
            stock_history[h.code].append(h)

    # 分析每檔股票
    results = []
    latest_date = dates[-1] if dates else ""

    for code, records in stock_history.items():
        if not records:
            continue

        # 按日期排序
        records.sort(key=lambda x: x.date)

        first_seen = records[0].date
        last_seen = records[-1].date
        name = records[-1].name

        # 計算持有天數 (用交易日數估算)
        try:
            first_dt = datetime.strptime(first_seen, "%Y%m%d")
            last_dt = datetime.strptime(last_seen, "%Y%m%d")
            holding_days = (last_dt - first_dt).days
        except:
            holding_days = 0

        # 判斷是否仍持有
        is_active = (last_seen == latest_date)

        # 權重趨勢
        weights = [r.weight for r in records]
        max_weight = max(weights) if weights else 0
        current_weight = weights[-1] if weights else 0

        if len(weights) >= 2:
            recent_avg = sum(weights[-2:]) / 2
            early_avg = sum(weights[:2]) / 2 if len(weights) >= 2 else weights[0]

            if recent_avg > early_avg * 1.2:
                weight_trend = "increasing"
            elif recent_avg < early_avg * 0.8:
                weight_trend = "decreasing"
            else:
                weight_trend = "stable"
        else:
            weight_trend = "stable"

        results.append(StockHoldingHistory(
            code=code,
            name=name,
            first_seen=first_seen,
            last_seen=last_seen,
            records=records,
            is_active=is_active,
            holding_days=holding_days,
            weight_trend=weight_trend,
            max_weight=max_weight,
            current_weight=current_weight
        ))

    # 按當前權重排序
    results.sort(key=lambda x: x.current_weight, reverse=True)

    return results


def get_holding_statistics(histories: List[StockHoldingHistory]) -> Dict[str, Any]:
    """
    計算持股統計
    """
    if not histories:
        return {}

    active = [h for h in histories if h.is_active]
    exited = [h for h in histories if not h.is_active]

    # 平均持有天數
    all_days = [h.holding_days for h in histories if h.holding_days > 0]
    avg_holding_days = sum(all_days) / len(all_days) if all_days else 0

    exited_days = [h.holding_days for h in exited if h.holding_days > 0]
    avg_exited_days = sum(exited_days) / len(exited_days) if exited_days else 0

    # 權重分佈
    weight_buckets = {
        "核心持股 (>3%)": len([h for h in active if h.current_weight > 3]),
        "重點持股 (1-3%)": len([h for h in active if 1 <= h.current_weight <= 3]),
        "觀察持股 (<1%)": len([h for h in active if h.current_weight < 1]),
    }

    # 趨勢分佈
    trend_dist = {
        "increasing": len([h for h in active if h.weight_trend == "increasing"]),
        "stable": len([h for h in active if h.weight_trend == "stable"]),
        "decreasing": len([h for h in active if h.weight_trend == "decreasing"]),
    }

    return {
        "total_stocks": len(histories),
        "active_stocks": len(active),
        "exited_stocks": len(exited),
        "avg_holding_days": avg_holding_days,
        "avg_exited_days": avg_exited_days,
        "weight_buckets": weight_buckets,
        "trend_distribution": trend_dist
    }


# =============================================================================
# 權重訊號分析
# =============================================================================

def analyze_weight_signals(historical_data: Dict[str, Any]) -> List[WeightSignal]:
    """
    分析權重變化訊號
    """
    holdings_by_date = historical_data.get("holdings", {})
    dates = historical_data.get("dates", [])

    if len(dates) < 2:
        return []

    current_date = dates[-1]
    prev_date = dates[-2]

    current_holdings = {h.code: h for h in holdings_by_date.get(current_date, [])}
    prev_holdings = {h.code: h for h in holdings_by_date.get(prev_date, [])}

    # 計算權重排名
    current_ranked = sorted(current_holdings.values(), key=lambda x: x.weight, reverse=True)
    prev_ranked = sorted(prev_holdings.values(), key=lambda x: x.weight, reverse=True)

    current_rank = {h.code: i + 1 for i, h in enumerate(current_ranked)}
    prev_rank = {h.code: i + 1 for i, h in enumerate(prev_ranked)}

    signals = []
    all_codes = set(current_holdings.keys()) | set(prev_holdings.keys())

    for code in all_codes:
        curr = current_holdings.get(code)
        prev = prev_holdings.get(code)

        if curr and prev:
            # 持續持有
            weight_change = curr.weight - prev.weight
            rank_change = prev_rank.get(code, 999) - current_rank.get(code, 999)

            if weight_change > 1 and curr.weight > 3:
                signal = "高信心加碼"
                conviction = "高"
            elif weight_change > 0.5:
                signal = "持續看好"
                conviction = "中"
            elif weight_change < -1:
                signal = "信心下降"
                conviction = "低"
            elif weight_change < -0.3:
                signal = "小幅減碼"
                conviction = "中"
            else:
                signal = "維持"
                conviction = "中"

            signals.append(WeightSignal(
                code=code,
                name=curr.name,
                current_weight=curr.weight,
                prev_weight=prev.weight,
                weight_change=weight_change,
                weight_rank=current_rank.get(code, 999),
                prev_rank=prev_rank.get(code, 999),
                rank_change=rank_change,
                signal=signal,
                conviction_level=conviction
            ))

        elif curr and not prev:
            # 新進場
            signals.append(WeightSignal(
                code=code,
                name=curr.name,
                current_weight=curr.weight,
                prev_weight=0,
                weight_change=curr.weight,
                weight_rank=current_rank.get(code, 999),
                prev_rank=999,
                rank_change=999 - current_rank.get(code, 999),
                signal="新進場",
                conviction_level="高" if curr.weight > 2 else "中"
            ))

        elif prev and not curr:
            # 已出清
            signals.append(WeightSignal(
                code=code,
                name=prev.name,
                current_weight=0,
                prev_weight=prev.weight,
                weight_change=-prev.weight,
                weight_rank=999,
                prev_rank=prev_rank.get(code, 999),
                rank_change=-999,
                signal="已出清",
                conviction_level="低"
            ))

    # 按權重變化排序 (絕對值)
    signals.sort(key=lambda x: abs(x.weight_change), reverse=True)

    return signals


def get_conviction_summary(signals: List[WeightSignal]) -> Dict[str, Any]:
    """
    統計信心度分佈
    """
    if not signals:
        return {}

    high_conviction = [s for s in signals if s.conviction_level == "高"]
    medium_conviction = [s for s in signals if s.conviction_level == "中"]
    low_conviction = [s for s in signals if s.conviction_level == "低"]

    # 按訊號分類
    signal_counts = defaultdict(int)
    for s in signals:
        signal_counts[s.signal] += 1

    return {
        "high_conviction": len(high_conviction),
        "medium_conviction": len(medium_conviction),
        "low_conviction": len(low_conviction),
        "signal_counts": dict(signal_counts),
        "top_increases": [s for s in signals if s.weight_change > 0][:5],
        "top_decreases": [s for s in signals if s.weight_change < 0][:5],
        "new_entries": [s for s in signals if s.signal == "新進場"],
        "exits": [s for s in signals if s.signal == "已出清"],
    }


# =============================================================================
# 綜合分析報告
# =============================================================================

def generate_analysis_report(etf_code: str, num_periods: int = 10) -> Dict[str, Any]:
    """
    產生綜合分析報告
    """
    # 載入歷史資料
    historical_data = load_historical_data(etf_code, num_periods)

    if not historical_data.get("dates"):
        return {"error": "無法載入歷史資料"}

    # 各項分析
    cash_analysis = analyze_cash_levels(historical_data)
    holding_histories = analyze_holding_periods(historical_data)
    holding_stats = get_holding_statistics(holding_histories)
    weight_signals = analyze_weight_signals(historical_data)
    conviction_summary = get_conviction_summary(weight_signals)

    return {
        "etf_code": etf_code,
        "etf_info": ACTIVE_ETFS.get(etf_code, {}),
        "periods_analyzed": len(historical_data.get("dates", [])),
        "date_range": {
            "start": historical_data.get("dates", [""])[0],
            "end": historical_data.get("dates", [""])[-1] if historical_data.get("dates") else ""
        },
        "cash_analysis": cash_analysis,
        "holding_histories": holding_histories,
        "holding_stats": holding_stats,
        "weight_signals": weight_signals,
        "conviction_summary": conviction_summary,
    }
