"""
UI 組件模組 - Streamlit 介面元件
"""
from typing import Any, Dict, Optional

import streamlit as st

from config import VIXTWN_HIGH, VIXTWN_LOW


# =============================================================================
# CSS 樣式
# =============================================================================

def inject_custom_css():
    """注入自定義 CSS 樣式"""
    st.markdown("""
    <style>
        .metric-card {
            background-color: #262730;
            padding: 10px;
            border-radius: 5px;
            border-left: 4px solid #FF4B4B;
            text-align: center;
            margin-bottom: 10px;
            height: 110px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .metric-label { font-size: 13px; color: #aaa; margin-bottom: 5px; }
        .metric-value { font-size: 22px; font-weight: bold; color: #fff; }
        .metric-sub { font-size: 14px; margin-top: 5px; font-weight: bold; }

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

        .alpha-long { border-left: 4px solid #55efc4; background-color: #2d3436; padding: 10px; border-radius: 5px; }
        .alpha-short { border-left: 4px solid #ff7675; background-color: #2d3436; padding: 10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# 指標卡片
# =============================================================================

def render_metric_card(
    label: str,
    value: Any,
    border_color: str = "#FF4B4B",
    sub_text: Optional[str] = None,
    sub_color: Optional[str] = None,
    delta: Optional[float] = None
):
    """渲染指標卡片"""
    value_html = str(value)

    if delta is not None:
        delta_color = "red" if delta > 0 else "green"
        value_html = f'{value} <span style="font-size:14px; color:{delta_color};">({delta:+.2f})</span>'

    sub_html = ""
    if sub_text:
        color = sub_color or "#aaa"
        sub_html = f'<div class="metric-sub" style="color: {color};">{sub_text}</div>'

    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {border_color};">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value_html}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def render_link_card(label: str, url: str, border_color: str = "#f1c40f"):
    """渲染連結卡片"""
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {border_color};">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="font-size:16px; padding-top:4px;">
            <a href="{url}" target="_blank" style="color:#fff;">點擊查看</a>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_vix_card(vix_data: Dict[str, Any]):
    """渲染美國 VIX 卡片"""
    val = vix_data.get('val', '-')
    delta = vix_data.get('delta', 0)
    render_metric_card(
        label="🇺🇸 VIX 恐慌指數",
        value=val,
        border_color="#e74c3c",
        delta=delta if isinstance(delta, (int, float)) else None
    )


def render_vixtwn_card(vixtwn_data: Dict[str, Any]):
    """渲染台灣 VIXTWN 卡片"""
    val = vixtwn_data.get('val')

    # 決定狀態
    msg = "⚪ 正常區間"
    msg_color = "#b2bec3"
    border_color = "#74b9ff"

    if val:
        if val > VIXTWN_HIGH:
            msg = "🔴 買PUT 降部位"
            msg_color = "#ff7675"
            border_color = "#ff7675"
        elif val < VIXTWN_LOW:
            msg = "🟢 可上槓桿"
            msg_color = "#55efc4"
            border_color = "#55efc4"
        else:
            msg = "🟡 震盪觀察"
            msg_color = "#ffeaa7"
            border_color = "#ffeaa7"

    val_display = f"{val:.2f}" if val else "讀取中..."

    render_metric_card(
        label="🇹🇼 VIXTWN (StockQ)",
        value=val_display,
        border_color=border_color,
        sub_text=msg,
        sub_color=msg_color
    )


def render_twii_card(twii_data: Dict[str, Any]):
    """渲染加權指數卡片"""
    val = twii_data.get('val', '-')
    status = twii_data.get('status', '-')
    border_color = "#2ecc71" if "站上" in status else "#e74c3c"

    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {border_color};">
        <div class="metric-label">🇹🇼 加權指數</div>
        <div class="metric-value">{val}</div>
        <div class="metric-label" style="color:{border_color}; font-size:11px;">{status}</div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# 策略說明框
# =============================================================================

def render_strategy_box(title: str, content: str):
    """渲染策略說明框"""
    st.markdown(f"""
    <div class="strategy-box">
        <div class="strategy-title">{title}</div>
        <div class="strategy-list">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def render_0050_strategy_box():
    """渲染 0050 策略說明"""
    render_strategy_box(
        "📜 0050 吃豆腐戰法 (SOP)",
        """
        1. <b>核心邏輯：</b> 市值前 40 名必定納入。利用「市值排名」提前預測。<br>
        2. <b>進場時機：</b> <span class="buy-signal">公告前 1 個月</span>。掃描下方 Rank ≤ 40 但未入選者。<br>
        3. <b>出場時機：</b> <span class="sell-signal">生效日當天 13:30</span>。掛「跌停價」倒貨給 ETF。<br>
        4. <b>避險：</b> 若公告前漲幅 > 20%，勿追。
        """
    )


def render_msci_strategy_box():
    """渲染 MSCI 策略說明"""
    render_strategy_box(
        "📜 MSCI 波動戰法 (SOP)",
        """
        1. <b>核心邏輯：</b> 追蹤全球資金流，重點在「生效日尾盤爆量」。<br>
        2. <b>進場時機：</b> <span class="buy-signal">公布日早晨</span>。搶進意外黑馬。<br>
        3. <b>出場時機：</b> <span class="sell-signal">生效日 13:30</span>。掛「跌停價」賣出。<br>
        4. <b>避險：</b> 右側「剔除區」勿輕易接刀。
        """
    )


def render_0056_strategy_box():
    """渲染 0056 策略說明"""
    render_strategy_box(
        "📜 0056 高股息戰法 (元大官方邏輯)",
        """
        1. <b>選股池：</b> 市值前 150 大。<br>
        2. <b>門檻：</b> 殖利率排名 <span class="buy-signal">前 35 納入</span>；<span class="sell-signal">跌出 66 剔除</span>。<br>
        3. <b>操作：</b> 觀察下方列表，找<b>殖利率高</b>且<b>未入選</b>者。<br>
        4. <b>出場：</b> 0056 有 5 天換股期，可分批調節。
        """
    )


def render_alpha_strategy_box():
    """渲染 Alpha 對沖策略說明"""
    render_strategy_box(
        "🤖 電子權值 Alpha 對沖策略 (自動篩選)",
        """
        <b>邏輯：</b> 自動從 Top 50 市值中，篩選出電子/半導體股做多，
        同時放空台指期，賺取電子股優於大盤的 Alpha。
        """
    )


def render_weight_strategy_box():
    """渲染市場權重策略說明"""
    render_strategy_box(
        "📊 全市場市值權重排行 (Top 150)",
        "台股多空地圖。前 150 檔佔大盤 90% 市值。"
    )


# =============================================================================
# Alpha 對沖顯示
# =============================================================================

def render_alpha_short_position(short_info: Dict[str, Any]):
    """渲染空方部位資訊"""
    st.markdown(f"""
    <div class="alpha-short">
        <h4>避險標的：微台 (TMF)</h4>
        <ul>
            <li>當前指數：<b>{short_info['index_price']}</b></li>
            <li>合約價值：<b>${short_info['micro_val']:,}</b></li>
            <li>建議放空：<b style='color:#ff7675; font-size:24px;'>{short_info['contracts']} 口</b></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# DataFrame 欄位設定
# =============================================================================

def get_column_config():
    """取得標準欄位設定"""
    return {
        "連結代碼": st.column_config.LinkColumn(
            "代號",
            display_text=r"https://tw\.stock\.yahoo\.com/quote/(\d+)",
            width="small"
        ),
        "raw_turnover": None,
        "raw_vol": None,
        "raw_yield": None,
        "raw_mcap": None,
        "raw_change": None,
        "raw_price": None,
        "in_0050": None,
    }
