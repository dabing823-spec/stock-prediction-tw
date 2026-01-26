"""
風險管理工具模組
提供停損計算、部位管理、資金配置建議
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

import streamlit as st


# =============================================================================
# 風險等級定義
# =============================================================================

class RiskLevel(Enum):
    CONSERVATIVE = "保守型"
    MODERATE = "穩健型"
    AGGRESSIVE = "積極型"


# 風險等級對應參數
RISK_PARAMS = {
    RiskLevel.CONSERVATIVE: {
        "max_single_position": 0.05,  # 單一部位最大比例
        "max_sector_exposure": 0.20,  # 單一產業最大比例
        "stop_loss_pct": 0.05,        # 停損幅度
        "take_profit_pct": 0.10,      # 停利幅度
        "max_total_exposure": 0.60,   # 最大總曝險
        "cash_reserve": 0.40,         # 現金保留
    },
    RiskLevel.MODERATE: {
        "max_single_position": 0.10,
        "max_sector_exposure": 0.30,
        "stop_loss_pct": 0.08,
        "take_profit_pct": 0.15,
        "max_total_exposure": 0.80,
        "cash_reserve": 0.20,
    },
    RiskLevel.AGGRESSIVE: {
        "max_single_position": 0.15,
        "max_sector_exposure": 0.40,
        "stop_loss_pct": 0.10,
        "take_profit_pct": 0.25,
        "max_total_exposure": 0.95,
        "cash_reserve": 0.05,
    },
}


# =============================================================================
# 停損停利計算
# =============================================================================

@dataclass
class StopLossResult:
    """停損計算結果"""
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_pct: float
    take_profit_pct: float
    risk_reward_ratio: float
    max_loss_amount: float
    potential_profit: float


def calculate_stop_loss(
    entry_price: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    position_size: int,
) -> StopLossResult:
    """
    計算停損停利價位

    Args:
        entry_price: 進場價格
        stop_loss_pct: 停損百分比 (0.08 = 8%)
        take_profit_pct: 停利百分比 (0.15 = 15%)
        position_size: 持股股數
    """
    stop_loss_price = entry_price * (1 - stop_loss_pct)
    take_profit_price = entry_price * (1 + take_profit_pct)
    risk_reward_ratio = take_profit_pct / stop_loss_pct if stop_loss_pct > 0 else 0

    max_loss_amount = (entry_price - stop_loss_price) * position_size
    potential_profit = (take_profit_price - entry_price) * position_size

    return StopLossResult(
        entry_price=entry_price,
        stop_loss_price=round(stop_loss_price, 2),
        take_profit_price=round(take_profit_price, 2),
        stop_loss_pct=stop_loss_pct * 100,
        take_profit_pct=take_profit_pct * 100,
        risk_reward_ratio=round(risk_reward_ratio, 2),
        max_loss_amount=round(max_loss_amount, 0),
        potential_profit=round(potential_profit, 0),
    )


# =============================================================================
# 部位大小計算
# =============================================================================

@dataclass
class PositionSizeResult:
    """部位大小計算結果"""
    recommended_shares: int
    recommended_amount: float
    risk_amount: float
    portfolio_pct: float
    warning: Optional[str]


def calculate_position_size(
    total_capital: float,
    entry_price: float,
    stop_loss_price: float,
    risk_per_trade_pct: float = 0.02,  # 每筆交易風險 2%
    max_position_pct: float = 0.10,    # 最大部位比例 10%
) -> PositionSizeResult:
    """
    計算建議部位大小 (基於風險)

    使用固定風險百分比法:
    部位大小 = (總資金 × 風險比例) / (進場價 - 停損價)
    """
    if entry_price <= stop_loss_price:
        return PositionSizeResult(
            recommended_shares=0,
            recommended_amount=0,
            risk_amount=0,
            portfolio_pct=0,
            warning="停損價必須低於進場價"
        )

    # 計算每股風險
    risk_per_share = entry_price - stop_loss_price

    # 計算最大可承受風險金額
    max_risk_amount = total_capital * risk_per_trade_pct

    # 基於風險計算的股數
    risk_based_shares = int(max_risk_amount / risk_per_share)

    # 基於最大部位比例的股數
    max_position_amount = total_capital * max_position_pct
    max_position_shares = int(max_position_amount / entry_price)

    # 取較小值
    recommended_shares = min(risk_based_shares, max_position_shares)

    # 調整為整張 (1000股)
    recommended_shares = (recommended_shares // 1000) * 1000

    if recommended_shares < 1000:
        recommended_shares = 1000  # 最少一張

    recommended_amount = recommended_shares * entry_price
    actual_risk = recommended_shares * risk_per_share
    portfolio_pct = (recommended_amount / total_capital) * 100

    warning = None
    if recommended_amount > max_position_amount:
        warning = f"⚠️ 部位超過建議上限 ({max_position_pct*100:.0f}%)"

    return PositionSizeResult(
        recommended_shares=recommended_shares,
        recommended_amount=round(recommended_amount, 0),
        risk_amount=round(actual_risk, 0),
        portfolio_pct=round(portfolio_pct, 2),
        warning=warning
    )


# =============================================================================
# 凱利公式
# =============================================================================

@dataclass
class KellyResult:
    """凱利公式結果"""
    kelly_pct: float
    half_kelly_pct: float
    recommended_pct: float
    edge: float
    description: str


def calculate_kelly_criterion(
    win_rate: float,      # 勝率 (0.6 = 60%)
    avg_win: float,       # 平均獲利
    avg_loss: float,      # 平均虧損
    use_half_kelly: bool = True
) -> KellyResult:
    """
    計算凱利公式建議部位

    Kelly % = W - [(1-W) / R]
    W = 勝率
    R = 盈虧比 (平均獲利/平均虧損)
    """
    if avg_loss == 0:
        return KellyResult(
            kelly_pct=0,
            half_kelly_pct=0,
            recommended_pct=0,
            edge=0,
            description="平均虧損不可為零"
        )

    # 盈虧比
    win_loss_ratio = avg_win / avg_loss

    # 凱利公式
    kelly = win_rate - ((1 - win_rate) / win_loss_ratio)

    # 半凱利 (更保守)
    half_kelly = kelly / 2

    # 期望值 (edge)
    edge = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    # 建議值
    recommended = half_kelly if use_half_kelly else kelly
    recommended = max(0, min(recommended, 0.25))  # 限制在 0-25%

    # 描述
    if edge > 0:
        if kelly > 0.20:
            desc = "正期望值，可積極建倉"
        elif kelly > 0.10:
            desc = "正期望值，適度建倉"
        else:
            desc = "正期望值但邊際小，小量試單"
    else:
        desc = "負期望值，不建議進場"

    return KellyResult(
        kelly_pct=round(kelly * 100, 2),
        half_kelly_pct=round(half_kelly * 100, 2),
        recommended_pct=round(recommended * 100, 2),
        edge=round(edge, 2),
        description=desc
    )


# =============================================================================
# 資產配置建議
# =============================================================================

@dataclass
class AllocationItem:
    """配置項目"""
    category: str
    target_pct: float
    description: str


@dataclass
class AllocationResult:
    """資產配置結果"""
    items: List[AllocationItem]
    total_capital: float
    risk_level: str


def get_allocation_suggestion(
    total_capital: float,
    risk_level: RiskLevel,
    market_condition: str = "neutral"  # "bullish", "neutral", "bearish"
) -> AllocationResult:
    """
    取得資產配置建議
    """
    params = RISK_PARAMS[risk_level]

    if risk_level == RiskLevel.CONSERVATIVE:
        if market_condition == "bearish":
            items = [
                AllocationItem("現金/貨幣基金", 50, "市場不確定性高，保持高現金"),
                AllocationItem("債券型 ETF", 20, "防禦性配置"),
                AllocationItem("高股息 ETF", 20, "穩定現金流"),
                AllocationItem("市值型 ETF", 10, "少量參與市場"),
            ]
        else:
            items = [
                AllocationItem("現金/貨幣基金", 40, "保持流動性"),
                AllocationItem("高股息 ETF", 30, "穩定配息收入"),
                AllocationItem("市值型 ETF", 20, "核心持股"),
                AllocationItem("債券型 ETF", 10, "分散風險"),
            ]

    elif risk_level == RiskLevel.MODERATE:
        if market_condition == "bullish":
            items = [
                AllocationItem("市值型 ETF", 35, "核心持股"),
                AllocationItem("產業型 ETF", 25, "半導體/科技輪動"),
                AllocationItem("高股息 ETF", 20, "配息收入"),
                AllocationItem("現金", 20, "保留加碼空間"),
            ]
        elif market_condition == "bearish":
            items = [
                AllocationItem("現金", 35, "等待機會"),
                AllocationItem("高股息 ETF", 30, "防禦配置"),
                AllocationItem("市值型 ETF", 25, "分批佈局"),
                AllocationItem("產業型 ETF", 10, "小量試單"),
            ]
        else:
            items = [
                AllocationItem("市值型 ETF", 30, "核心持股"),
                AllocationItem("高股息 ETF", 25, "穩定配息"),
                AllocationItem("產業型 ETF", 20, "主題輪動"),
                AllocationItem("現金", 25, "保持彈性"),
            ]

    else:  # AGGRESSIVE
        if market_condition == "bullish":
            items = [
                AllocationItem("產業型 ETF", 40, "積極參與主題"),
                AllocationItem("市值型 ETF", 30, "核心持股"),
                AllocationItem("個股", 20, "精選標的"),
                AllocationItem("現金", 10, "最低流動性"),
            ]
        else:
            items = [
                AllocationItem("市值型 ETF", 35, "核心持股"),
                AllocationItem("產業型 ETF", 30, "主題輪動"),
                AllocationItem("高股息 ETF", 20, "現金流"),
                AllocationItem("現金", 15, "等待機會"),
            ]

    return AllocationResult(
        items=items,
        total_capital=total_capital,
        risk_level=risk_level.value
    )


# =============================================================================
# 風險檢查
# =============================================================================

@dataclass
class RiskCheckResult:
    """風險檢查結果"""
    passed: bool
    warnings: List[str]
    suggestions: List[str]


def check_portfolio_risk(
    positions: List[Dict],  # [{"code": "2330", "amount": 100000, "sector": "半導體"}, ...]
    total_capital: float,
    risk_level: RiskLevel
) -> RiskCheckResult:
    """
    檢查投資組合風險
    """
    params = RISK_PARAMS[risk_level]
    warnings = []
    suggestions = []

    # 計算各項指標
    total_exposure = sum(p["amount"] for p in positions)
    exposure_pct = total_exposure / total_capital

    # 檢查總曝險
    if exposure_pct > params["max_total_exposure"]:
        warnings.append(
            f"總曝險 {exposure_pct*100:.1f}% 超過建議上限 {params['max_total_exposure']*100:.0f}%"
        )
        suggestions.append("建議減少部位或增加現金")

    # 檢查單一部位
    for p in positions:
        position_pct = p["amount"] / total_capital
        if position_pct > params["max_single_position"]:
            warnings.append(
                f"{p.get('code', '未知')} 佔比 {position_pct*100:.1f}% 超過建議 {params['max_single_position']*100:.0f}%"
            )

    # 檢查產業集中度
    sector_exposure = {}
    for p in positions:
        sector = p.get("sector", "其他")
        sector_exposure[sector] = sector_exposure.get(sector, 0) + p["amount"]

    for sector, amount in sector_exposure.items():
        sector_pct = amount / total_capital
        if sector_pct > params["max_sector_exposure"]:
            warnings.append(
                f"{sector} 產業佔比 {sector_pct*100:.1f}% 超過建議 {params['max_sector_exposure']*100:.0f}%"
            )
            suggestions.append(f"建議分散 {sector} 產業部位")

    passed = len(warnings) == 0

    if passed:
        suggestions.append("✅ 投資組合風險在可接受範圍內")

    return RiskCheckResult(
        passed=passed,
        warnings=warnings,
        suggestions=suggestions
    )
