"""
UI 組件模組 - Streamlit 介面元件 (優化版)
"""
from typing import Any, Dict, Optional

import streamlit as st

from config import VIXTWN_HIGH, VIXTWN_LOW


# =============================================================================
# CSS 樣式 (優化版)
# =============================================================================

def inject_custom_css():
    """注入自定義 CSS 樣式 - 現代化設計"""
    st.markdown("""
    <style>
        /* ===== 全局樣式 ===== */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* ===== 指標卡片 - 玻璃擬態設計 ===== */
        .metric-card {
            background: linear-gradient(135deg, rgba(38, 39, 48, 0.9) 0%, rgba(30, 35, 41, 0.95) 100%);
            backdrop-filter: blur(10px);
            padding: 16px 12px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-left: 4px solid #FF4B4B;
            text-align: center;
            margin-bottom: 12px;
            min-height: 120px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3),
                        0 1px 2px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
        }

        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            border-color: rgba(255, 255, 255, 0.15);
        }

        .metric-label {
            font-size: 12px;
            font-weight: 500;
            color: rgba(170, 170, 170, 0.9);
            margin-bottom: 8px;
            letter-spacing: 0.3px;
            text-transform: uppercase;
        }

        .metric-value {
            font-size: 28px;
            font-weight: 700;
            color: #fff;
            font-family: 'JetBrains Mono', monospace;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            line-height: 1.2;
        }

        .metric-sub {
            font-size: 13px;
            margin-top: 8px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 20px;
            background: rgba(0, 0, 0, 0.2);
        }

        .metric-delta {
            font-size: 14px;
            font-weight: 500;
            margin-left: 6px;
        }

        .metric-delta.positive { color: #ef4444; }
        .metric-delta.negative { color: #22c55e; }

        /* ===== 策略說明框 ===== */
        .strategy-box {
            background: linear-gradient(145deg, #1a1d24 0%, #13161c 100%);
            padding: 20px 24px;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.06);
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
            position: relative;
        }

        .strategy-box::after {
            content: '';
            position: absolute;
            top: 0;
            left: 24px;
            right: 24px;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(241, 196, 15, 0.3), transparent);
        }

        .strategy-title {
            color: #f1c40f;
            font-size: 17px;
            font-weight: 700;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .strategy-list {
            color: rgba(221, 221, 221, 0.95);
            font-size: 14px;
            line-height: 1.8;
        }

        .strategy-list b {
            color: #fff;
            font-weight: 600;
        }

        .buy-signal {
            color: #55efc4 !important;
            font-weight: 700;
            text-shadow: 0 0 10px rgba(85, 239, 196, 0.3);
        }

        .sell-signal {
            color: #ff7675 !important;
            font-weight: 700;
            text-shadow: 0 0 10px rgba(255, 118, 117, 0.3);
        }

        /* ===== Alpha 對沖卡片 ===== */
        .alpha-long {
            background: linear-gradient(135deg, rgba(85, 239, 196, 0.1) 0%, rgba(45, 52, 54, 0.95) 100%);
            border-left: 4px solid #55efc4;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 16px;
            box-shadow: 0 4px 16px rgba(85, 239, 196, 0.1);
        }

        .alpha-short {
            background: linear-gradient(135deg, rgba(255, 118, 117, 0.1) 0%, rgba(45, 52, 54, 0.95) 100%);
            border-left: 4px solid #ff7675;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(255, 118, 117, 0.1);
        }

        .alpha-short h4 {
            color: #fff;
            font-size: 16px;
            margin-bottom: 12px;
            font-weight: 600;
        }

        .alpha-short ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .alpha-short li {
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            color: rgba(255,255,255,0.8);
            font-size: 14px;
        }

        .alpha-short li:last-child {
            border-bottom: none;
        }

        .alpha-short li b {
            color: #fff;
        }

        /* ===== 狀態指示器 ===== */
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .status-danger {
            background: rgba(255, 118, 117, 0.2);
            color: #ff7675;
            border: 1px solid rgba(255, 118, 117, 0.3);
        }

        .status-success {
            background: rgba(85, 239, 196, 0.2);
            color: #55efc4;
            border: 1px solid rgba(85, 239, 196, 0.3);
        }

        .status-warning {
            background: rgba(255, 234, 167, 0.2);
            color: #ffeaa7;
            border: 1px solid rgba(255, 234, 167, 0.3);
        }

        .status-neutral {
            background: rgba(178, 190, 195, 0.2);
            color: #b2bec3;
            border: 1px solid rgba(178, 190, 195, 0.3);
        }

        /* ===== 表格優化 ===== */
        .stDataFrame {
            border-radius: 12px !important;
            overflow: hidden !important;
        }

        .stDataFrame > div {
            border-radius: 12px !important;
        }

        [data-testid="stDataFrame"] > div {
            background: linear-gradient(180deg, #1a1d24 0%, #13161c 100%) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 12px !important;
        }

        /* ===== Tabs 優化 ===== */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: rgba(0, 0, 0, 0.2);
            padding: 8px;
            border-radius: 12px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            padding: 12px 20px;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.2s ease;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }

        /* ===== 按鈕優化 ===== */
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 10px;
            padding: 12px 24px;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }

        /* ===== 側邊欄優化 ===== */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1a1d24 0%, #0d1117 100%);
        }

        [data-testid="stSidebar"] .stMarkdown h1,
        [data-testid="stSidebar"] .stMarkdown h2,
        [data-testid="stSidebar"] .stMarkdown h3 {
            color: #fff;
        }

        /* ===== 輸入框優化 ===== */
        .stNumberInput > div > div > input,
        .stTextInput > div > div > input {
            background: rgba(30, 35, 41, 0.8) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 10px !important;
            color: #fff !important;
            font-family: 'JetBrains Mono', monospace !important;
        }

        .stNumberInput > div > div > input:focus,
        .stTextInput > div > div > input:focus {
            border-color: #667eea !important;
            box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2) !important;
        }

        /* ===== Slider 優化 ===== */
        .stSlider > div > div > div > div {
            background: linear-gradient(90deg, #667eea, #764ba2) !important;
        }

        /* ===== 分隔線優化 ===== */
        hr {
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
            margin: 24px 0;
        }

        /* ===== 警告/提示框優化 ===== */
        .stAlert {
            border-radius: 12px !important;
            border: none !important;
        }

        /* ===== 動畫效果 ===== */
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        .loading-pulse {
            animation: pulse 1.5s ease-in-out infinite;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .slide-in {
            animation: slideIn 0.4s ease-out;
        }

        /* ===== 響應式設計 ===== */
        @media (max-width: 768px) {
            .metric-card {
                min-height: 100px;
                padding: 12px 8px;
            }

            .metric-value {
                font-size: 22px;
            }

            .metric-label {
                font-size: 10px;
            }

            .strategy-box {
                padding: 16px;
            }

            .strategy-title {
                font-size: 15px;
            }

            .strategy-list {
                font-size: 13px;
            }
        }
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# 指標卡片 (優化版)
# =============================================================================

def render_metric_card(
    label: str,
    value: Any,
    border_color: str = "#FF4B4B",
    sub_text: Optional[str] = None,
    sub_color: Optional[str] = None,
    delta: Optional[float] = None,
    icon: str = ""
):
    """渲染指標卡片 - 優化版"""
    value_html = f'<span>{value}</span>'

    if delta is not None and isinstance(delta, (int, float)):
        delta_class = "positive" if delta > 0 else "negative"
        delta_sign = "+" if delta > 0 else ""
        value_html = f'''
            <span>{value}</span>
            <span class="metric-delta {delta_class}">({delta_sign}{delta:.2f})</span>
        '''

    sub_html = ""
    if sub_text:
        color = sub_color or "#aaa"
        sub_html = f'<div class="metric-sub" style="color: {color};">{sub_text}</div>'

    label_with_icon = f"{icon} {label}" if icon else label

    st.markdown(f"""
    <div class="metric-card slide-in" style="border-left-color: {border_color};">
        <div class="metric-label">{label_with_icon}</div>
        <div class="metric-value">{value_html}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def render_link_card(label: str, url: str, border_color: str = "#f1c40f", icon: str = ""):
    """渲染連結卡片"""
    label_with_icon = f"{icon} {label}" if icon else label

    st.markdown(f"""
    <div class="metric-card slide-in" style="border-left-color: {border_color};">
        <div class="metric-label">{label_with_icon}</div>
        <div class="metric-value" style="font-size: 16px;">
            <a href="{url}" target="_blank" style="
                color: #fff;
                text-decoration: none;
                padding: 8px 16px;
                background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
                border-radius: 8px;
                transition: all 0.2s ease;
                display: inline-block;
            " onmouseover="this.style.background='linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.08) 100%)'"
               onmouseout="this.style.background='linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)'">
                點擊查看 →
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_vix_card(vix_data: Dict[str, Any]):
    """渲染美國 VIX 卡片"""
    val = vix_data.get('val', '-')
    delta = vix_data.get('delta', 0)

    # VIX 顏色判斷
    if isinstance(val, (int, float)):
        if val > 25:
            border_color = "#ff7675"
        elif val < 15:
            border_color = "#55efc4"
        else:
            border_color = "#ffeaa7"
    else:
        border_color = "#e74c3c"

    render_metric_card(
        label="VIX 恐慌指數",
        value=val,
        border_color=border_color,
        delta=delta if isinstance(delta, (int, float)) else None,
        icon="🇺🇸"
    )


def render_vixtwn_card(vixtwn_data: Dict[str, Any]):
    """渲染台灣 VIXTWN 卡片"""
    val = vixtwn_data.get('val')

    # 決定狀態
    msg = "正常區間"
    msg_color = "#b2bec3"
    border_color = "#74b9ff"
    status_icon = "⚪"

    if val:
        if val > VIXTWN_HIGH:
            msg = "買PUT 降部位"
            msg_color = "#ff7675"
            border_color = "#ff7675"
            status_icon = "🔴"
        elif val < VIXTWN_LOW:
            msg = "可上槓桿"
            msg_color = "#55efc4"
            border_color = "#55efc4"
            status_icon = "🟢"
        else:
            msg = "震盪觀察"
            msg_color = "#ffeaa7"
            border_color = "#ffeaa7"
            status_icon = "🟡"

    val_display = f"{val:.2f}" if val else "讀取中..."

    render_metric_card(
        label="VIXTWN",
        value=val_display,
        border_color=border_color,
        sub_text=f"{status_icon} {msg}",
        sub_color=msg_color,
        icon="🇹🇼"
    )


def render_twii_card(twii_data: Dict[str, Any]):
    """渲染加權指數卡片"""
    val = twii_data.get('val', '-')
    status = twii_data.get('status', '-')

    # 判斷顏色
    if "站上月線" in status and "站上季線" in status:
        border_color = "#55efc4"
        status_icon = "📈"
    elif "跌破月線" in status and "跌破季線" in status:
        border_color = "#ff7675"
        status_icon = "📉"
    else:
        border_color = "#ffeaa7"
        status_icon = "📊"

    # 格式化數值
    if isinstance(val, (int, float)):
        val_display = f"{val:,}"
    else:
        val_display = val

    st.markdown(f"""
    <div class="metric-card slide-in" style="border-left-color: {border_color};">
        <div class="metric-label">🇹🇼 加權指數</div>
        <div class="metric-value">{val_display}</div>
        <div class="metric-sub" style="color: {border_color}; font-size: 11px;">
            {status_icon} {status}
        </div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# 策略說明框 (優化版)
# =============================================================================

def render_strategy_box(title: str, content: str, icon: str = "📜"):
    """渲染策略說明框"""
    st.markdown(f"""
    <div class="strategy-box slide-in">
        <div class="strategy-title">{icon} {title}</div>
        <div class="strategy-list">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def render_0050_strategy_box():
    """渲染 0050 策略說明"""
    render_strategy_box(
        "0050 吃豆腐戰法 (SOP)",
        """
        <table style="width:100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0; width: 80px;"><b>核心邏輯</b></td>
                <td style="padding: 8px 0;">市值前 40 名必定納入，利用「市值排名」提前預測</td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>進場時機</b></td>
                <td style="padding: 8px 0;"><span class="buy-signal">公告前 1 個月</span> → 掃描 Rank ≤ 40 但未入選者</td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>出場時機</b></td>
                <td style="padding: 8px 0;"><span class="sell-signal">生效日 13:30</span> → 掛跌停價倒貨給 ETF</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><b>風險控制</b></td>
                <td style="padding: 8px 0;">若公告前漲幅 > 20%，勿追</td>
            </tr>
        </table>
        """,
        "🎯"
    )


def render_msci_strategy_box():
    """渲染 MSCI 策略說明"""
    render_strategy_box(
        "MSCI 波動戰法 (SOP)",
        """
        <table style="width:100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0; width: 80px;"><b>核心邏輯</b></td>
                <td style="padding: 8px 0;">追蹤全球資金流，重點在「生效日尾盤爆量」</td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>進場時機</b></td>
                <td style="padding: 8px 0;"><span class="buy-signal">公布日早晨</span> → 搶進意外黑馬</td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>出場時機</b></td>
                <td style="padding: 8px 0;"><span class="sell-signal">生效日 13:30</span> → 掛跌停價賣出</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><b>風險控制</b></td>
                <td style="padding: 8px 0;">右側「剔除區」勿輕易接刀</td>
            </tr>
        </table>
        """,
        "🌍"
    )


def render_0056_strategy_box():
    """渲染 0056 策略說明"""
    render_strategy_box(
        "0056 高股息戰法 (元大官方邏輯)",
        """
        <table style="width:100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0; width: 80px;"><b>選股池</b></td>
                <td style="padding: 8px 0;">市值前 150 大</td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>納入門檻</b></td>
                <td style="padding: 8px 0;">殖利率排名 <span class="buy-signal">前 35 名</span></td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>剔除門檻</b></td>
                <td style="padding: 8px 0;">殖利率排名 <span class="sell-signal">跌出 66 名</span></td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><b>換股期</b></td>
                <td style="padding: 8px 0;">0056 有 5 天換股期，可分批調節</td>
            </tr>
        </table>
        """,
        "💰"
    )


def render_alpha_strategy_box():
    """渲染 Alpha 對沖策略說明"""
    render_strategy_box(
        "電子權值 Alpha 對沖策略",
        """
        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 200px;">
                <div style="color: #55efc4; font-weight: 600; margin-bottom: 8px;">🟢 多方 (現貨)</div>
                <div>從 Top 50 市值中篩選電子/半導體股</div>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <div style="color: #ff7675; font-weight: 600; margin-bottom: 8px;">🔴 空方 (期貨)</div>
                <div>放空台指期對沖系統性風險</div>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <div style="color: #ffeaa7; font-weight: 600; margin-bottom: 8px;">⚡ Alpha 收益</div>
                <div>賺取電子股優於大盤的超額報酬</div>
            </div>
        </div>
        """,
        "🤖"
    )


def render_weight_strategy_box():
    """渲染市場權重策略說明"""
    render_strategy_box(
        "全市場市值權重排行 (Top 150)",
        """
        <div style="display: flex; align-items: center; gap: 16px;">
            <div style="font-size: 32px;">📊</div>
            <div>
                <div style="font-weight: 600; margin-bottom: 4px;">台股多空地圖</div>
                <div style="color: rgba(255,255,255,0.7);">前 150 檔佔大盤約 90% 市值，掌握這些就掌握大盤</div>
            </div>
        </div>
        """,
        "📈"
    )


# =============================================================================
# Alpha 對沖顯示 (優化版)
# =============================================================================

def render_alpha_short_position(short_info: Dict[str, Any]):
    """渲染空方部位資訊"""
    st.markdown(f"""
    <div class="alpha-short slide-in">
        <h4>🎯 避險標的：微台指 (MTX)</h4>
        <ul>
            <li>
                <span style="color: rgba(255,255,255,0.6);">當前指數</span>
                <b style="float: right; font-family: 'JetBrains Mono', monospace;">{short_info['index_price']:,}</b>
            </li>
            <li>
                <span style="color: rgba(255,255,255,0.6);">合約價值</span>
                <b style="float: right; font-family: 'JetBrains Mono', monospace;">${short_info['micro_val']:,}</b>
            </li>
            <li style="background: rgba(255, 118, 117, 0.1); margin: 8px -20px; padding: 12px 20px; border-radius: 8px;">
                <span style="color: rgba(255,255,255,0.8);">建議放空</span>
                <b style="float: right; color: #ff7675; font-size: 24px; font-family: 'JetBrains Mono', monospace;">
                    {short_info['contracts']} 口
                </b>
            </li>
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


# =============================================================================
# ETF 輪動策略 UI
# =============================================================================

def render_etf_rotation_strategy_box():
    """渲染 ETF 輪動策略說明"""
    render_strategy_box(
        "ETF 輪動策略 (動能追蹤)",
        """
        <table style="width:100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0; width: 80px;"><b>核心邏輯</b></td>
                <td style="padding: 8px 0;">追蹤主題型 ETF 相對強弱，輪動配置資金</td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>強勢信號</b></td>
                <td style="padding: 8px 0;"><span class="buy-signal">報酬率高 + 回撤小 + 接近高點</span></td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>弱勢信號</b></td>
                <td style="padding: 8px 0;"><span class="sell-signal">報酬率低 + 回撤大 + 遠離高點</span></td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><b>輪動週期</b></td>
                <td style="padding: 8px 0;">每月檢視，季度調整</td>
            </tr>
        </table>
        """,
        "🔄"
    )


def render_rotation_signal_card(signal_type: str, count: int, color: str):
    """渲染輪動信號統計卡片"""
    st.markdown(f"""
    <div class="metric-card slide-in" style="border-left-color: {color}; min-height: 80px;">
        <div class="metric-label">{signal_type}</div>
        <div class="metric-value" style="font-size: 36px; color: {color};">{count}</div>
    </div>
    """, unsafe_allow_html=True)


def render_dividend_alert(upcoming: list):
    """渲染配息提醒"""
    if not upcoming:
        return

    high_urgency = [d for d in upcoming if d.get("urgency") == "high"]
    med_urgency = [d for d in upcoming if d.get("urgency") == "medium"]

    content = ""
    if high_urgency:
        items = ", ".join([f"{d['code']} {d['name']}" for d in high_urgency[:3]])
        content += f'<div style="color: #ff7675; margin-bottom: 8px;">🔴 本月配息: {items}</div>'

    if med_urgency:
        items = ", ".join([f"{d['code']} {d['name']}" for d in med_urgency[:3]])
        content += f'<div style="color: #ffeaa7;">🟡 下月配息: {items}</div>'

    st.markdown(f"""
    <div class="strategy-box slide-in" style="border-left: 4px solid #f1c40f;">
        <div class="strategy-title">📅 配息追蹤</div>
        <div class="strategy-list">{content}</div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# 風險管理工具 UI
# =============================================================================

def render_risk_management_strategy_box():
    """渲染風險管理策略說明"""
    render_strategy_box(
        "風險管理工具箱",
        """
        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 200px;">
                <div style="color: #ff7675; font-weight: 600; margin-bottom: 8px;">🛑 停損停利</div>
                <div>自動計算停損價、停利價、盈虧比</div>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <div style="color: #74b9ff; font-weight: 600; margin-bottom: 8px;">📐 部位計算</div>
                <div>依據風險比例計算建議部位大小</div>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <div style="color: #55efc4; font-weight: 600; margin-bottom: 8px;">🎰 凱利公式</div>
                <div>基於勝率和盈虧比的最佳部位</div>
            </div>
        </div>
        """,
        "🛡️"
    )


def render_stop_loss_result(result):
    """渲染停損停利計算結果"""
    rr_color = "#55efc4" if result.risk_reward_ratio >= 2 else "#ffeaa7" if result.risk_reward_ratio >= 1.5 else "#ff7675"

    st.markdown(f"""
    <div class="strategy-box slide-in">
        <div class="strategy-title">📊 停損停利分析</div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 12px;">
            <div style="text-align: center; padding: 16px; background: rgba(255,118,117,0.1); border-radius: 12px;">
                <div style="color: rgba(255,255,255,0.6); font-size: 12px; margin-bottom: 4px;">停損價</div>
                <div style="color: #ff7675; font-size: 24px; font-weight: 700; font-family: 'JetBrains Mono', monospace;">
                    ${result.stop_loss_price:,.2f}
                </div>
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">-{result.stop_loss_pct:.1f}%</div>
            </div>
            <div style="text-align: center; padding: 16px; background: rgba(116,185,255,0.1); border-radius: 12px;">
                <div style="color: rgba(255,255,255,0.6); font-size: 12px; margin-bottom: 4px;">進場價</div>
                <div style="color: #74b9ff; font-size: 24px; font-weight: 700; font-family: 'JetBrains Mono', monospace;">
                    ${result.entry_price:,.2f}
                </div>
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">基準</div>
            </div>
            <div style="text-align: center; padding: 16px; background: rgba(85,239,196,0.1); border-radius: 12px;">
                <div style="color: rgba(255,255,255,0.6); font-size: 12px; margin-bottom: 4px;">停利價</div>
                <div style="color: #55efc4; font-size: 24px; font-weight: 700; font-family: 'JetBrains Mono', monospace;">
                    ${result.take_profit_price:,.2f}
                </div>
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">+{result.take_profit_pct:.1f}%</div>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 16px;">
            <div style="text-align: center;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">最大虧損</div>
                <div style="color: #ff7675; font-size: 16px; font-weight: 600;">${result.max_loss_amount:,.0f}</div>
            </div>
            <div style="text-align: center;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">盈虧比</div>
                <div style="color: {rr_color}; font-size: 16px; font-weight: 600;">1:{result.risk_reward_ratio}</div>
            </div>
            <div style="text-align: center;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">潛在獲利</div>
                <div style="color: #55efc4; font-size: 16px; font-weight: 600;">${result.potential_profit:,.0f}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_position_size_result(result):
    """渲染部位計算結果"""
    st.markdown(f"""
    <div class="alpha-long slide-in">
        <h4 style="color: #fff; margin-bottom: 16px;">📐 建議部位</h4>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;">
            <div>
                <div style="color: rgba(255,255,255,0.6); font-size: 12px;">建議股數</div>
                <div style="color: #55efc4; font-size: 28px; font-weight: 700; font-family: 'JetBrains Mono', monospace;">
                    {result.recommended_shares:,} 股
                </div>
            </div>
            <div>
                <div style="color: rgba(255,255,255,0.6); font-size: 12px;">建議金額</div>
                <div style="color: #fff; font-size: 28px; font-weight: 700; font-family: 'JetBrains Mono', monospace;">
                    ${result.recommended_amount:,.0f}
                </div>
            </div>
            <div>
                <div style="color: rgba(255,255,255,0.6); font-size: 12px;">風險金額</div>
                <div style="color: #ff7675; font-size: 18px; font-weight: 600;">${result.risk_amount:,.0f}</div>
            </div>
            <div>
                <div style="color: rgba(255,255,255,0.6); font-size: 12px;">佔總資金</div>
                <div style="color: #74b9ff; font-size: 18px; font-weight: 600;">{result.portfolio_pct:.1f}%</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if result.warning:
        st.warning(result.warning)


def render_kelly_result(result):
    """渲染凱利公式結果"""
    edge_color = "#55efc4" if result.edge > 0 else "#ff7675"

    st.markdown(f"""
    <div class="strategy-box slide-in">
        <div class="strategy-title">🎰 凱利公式分析</div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 12px;">
            <div style="text-align: center; padding: 12px; background: rgba(0,0,0,0.2); border-radius: 8px;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">凱利比例</div>
                <div style="color: #ffeaa7; font-size: 20px; font-weight: 600;">{result.kelly_pct:.1f}%</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(0,0,0,0.2); border-radius: 8px;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">半凱利</div>
                <div style="color: #74b9ff; font-size: 20px; font-weight: 600;">{result.half_kelly_pct:.1f}%</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(85,239,196,0.15); border-radius: 8px;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">建議比例</div>
                <div style="color: #55efc4; font-size: 20px; font-weight: 600;">{result.recommended_pct:.1f}%</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(0,0,0,0.2); border-radius: 8px;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px;">期望值</div>
                <div style="color: {edge_color}; font-size: 20px; font-weight: 600;">{result.edge:+.2f}</div>
            </div>
        </div>
        <div style="margin-top: 12px; padding: 12px; background: rgba(0,0,0,0.15); border-radius: 8px; text-align: center;">
            <span style="color: rgba(255,255,255,0.7);">💡 {result.description}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_allocation_chart(result):
    """渲染資產配置建議"""
    colors = ["#55efc4", "#74b9ff", "#ffeaa7", "#ff7675", "#a29bfe"]

    items_html = ""
    for i, item in enumerate(result.items):
        color = colors[i % len(colors)]
        amount = result.total_capital * (item.target_pct / 100)
        items_html += f"""
        <div style="display: flex; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
            <div style="width: 8px; height: 8px; background: {color}; border-radius: 50%; margin-right: 12px;"></div>
            <div style="flex: 1;">
                <div style="color: #fff; font-weight: 500;">{item.category}</div>
                <div style="color: rgba(255,255,255,0.5); font-size: 12px;">{item.description}</div>
            </div>
            <div style="text-align: right;">
                <div style="color: {color}; font-weight: 600; font-family: 'JetBrains Mono', monospace;">{item.target_pct:.0f}%</div>
                <div style="color: rgba(255,255,255,0.5); font-size: 12px;">${amount:,.0f}</div>
            </div>
        </div>
        """

    st.markdown(f"""
    <div class="strategy-box slide-in">
        <div class="strategy-title">📊 {result.risk_level} 配置建議</div>
        <div style="margin-top: 8px;">
            {items_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_risk_check_result(result):
    """渲染風險檢查結果"""
    status_class = "status-success" if result.passed else "status-danger"
    status_text = "通過" if result.passed else "警告"

    warnings_html = ""
    if result.warnings:
        warnings_html = "<div style='margin-top: 12px;'>"
        for w in result.warnings:
            warnings_html += f"<div style='color: #ff7675; padding: 4px 0;'>⚠️ {w}</div>"
        warnings_html += "</div>"

    suggestions_html = ""
    if result.suggestions:
        suggestions_html = "<div style='margin-top: 12px;'>"
        for s in result.suggestions:
            suggestions_html += f"<div style='color: rgba(255,255,255,0.7); padding: 4px 0;'>💡 {s}</div>"
        suggestions_html += "</div>"

    st.markdown(f"""
    <div class="strategy-box slide-in">
        <div class="strategy-title">
            🔍 風險檢查
            <span class="{status_class}" style="margin-left: 12px;">{status_text}</span>
        </div>
        {warnings_html}
        {suggestions_html}
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# 主動型 ETF 追蹤 UI
# =============================================================================

def render_active_etf_strategy_box():
    """渲染主動型 ETF 追蹤策略說明"""
    render_strategy_box(
        "主動型 ETF 持股追蹤戰法",
        """
        <table style="width:100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0; width: 80px;"><b>核心邏輯</b></td>
                <td style="padding: 8px 0;">追蹤主動型 ETF (如 00981A) 持股變動，跟隨專業經理人佈局</td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>新建倉</b></td>
                <td style="padding: 8px 0;"><span class="buy-signal">重點追蹤！</span> ETF 剛開始買進的標的，提早跟進</td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>大幅加碼</b></td>
                <td style="padding: 8px 0;"><span class="buy-signal">持續看好</span> 經理人加碼 >20% 的標的</td>
            </tr>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                <td style="padding: 8px 0;"><b>減碼/出清</b></td>
                <td style="padding: 8px 0;"><span class="sell-signal">避開風險</span> ETF 正在退出的標的</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><b>資料來源</b></td>
                <td style="padding: 8px 0;">上傳投信官網公布的持股明細 Excel</td>
            </tr>
        </table>
        """,
        "🎯"
    )


def render_etf_summary_card(summary, date_new: str, date_old: str):
    """渲染 ETF 摘要卡片"""
    from active_etf_tracker import format_amount

    def fmt_units(v):
        if v is None:
            return "—"
        return f"{v/1e9:.2f}B" if v >= 1e9 else f"{v/1e6:.1f}M"

    def fmt_cash(v):
        if v is None:
            return "—"
        return format_amount(v)

    def fmt_pct(v):
        if v is None:
            return "—"
        return f"{v:.2f}%"

    def fmt_nav(v):
        if v is None:
            return "—"
        return f"${v:.2f}"

    def fmt_change(v, is_pct=False):
        if v is None:
            return "—"
        color = "#55efc4" if v > 0 else "#ff7675" if v < 0 else "#b2bec3"
        sign = "+" if v > 0 else ""
        if is_pct:
            return f'<span style="color: {color};">{sign}{v:.2f}%</span>'
        return f'<span style="color: {color};">{format_amount(v)}</span>'

    st.markdown(f"""
    <div class="strategy-box slide-in">
        <div class="strategy-title">📊 ETF 摘要 ({date_old} → {date_new})</div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 12px;">
            <div style="text-align: center; padding: 16px; background: rgba(0,0,0,0.2); border-radius: 12px;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px; margin-bottom: 4px;">流通單位數</div>
                <div style="color: #74b9ff; font-size: 18px; font-weight: 600;">{fmt_units(summary.units_outstanding)}</div>
                <div style="font-size: 12px; margin-top: 4px;">{fmt_change(summary.units_change)}</div>
            </div>
            <div style="text-align: center; padding: 16px; background: rgba(0,0,0,0.2); border-radius: 12px;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px; margin-bottom: 4px;">現金部位</div>
                <div style="color: #ffeaa7; font-size: 18px; font-weight: 600;">{fmt_cash(summary.cash_amount)}</div>
                <div style="font-size: 12px; margin-top: 4px;">{fmt_change(summary.cash_change)}</div>
            </div>
            <div style="text-align: center; padding: 16px; background: rgba(0,0,0,0.2); border-radius: 12px;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px; margin-bottom: 4px;">現金權重</div>
                <div style="color: #a29bfe; font-size: 18px; font-weight: 600;">{fmt_pct(summary.cash_weight)}</div>
                <div style="font-size: 12px; margin-top: 4px;">{fmt_change(summary.cash_weight_change, is_pct=True)}</div>
            </div>
            <div style="text-align: center; padding: 16px; background: rgba(0,0,0,0.2); border-radius: 12px;">
                <div style="color: rgba(255,255,255,0.5); font-size: 11px; margin-bottom: 4px;">每單位淨值</div>
                <div style="color: #55efc4; font-size: 18px; font-weight: 600;">{fmt_nav(summary.nav_per_unit)}</div>
                <div style="font-size: 12px; margin-top: 4px;">{fmt_change(summary.nav_change)}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_position_change_card(title: str, holdings: list, change_type: str, icon: str, color: str):
    """渲染持股變動卡片"""
    from active_etf_tracker import format_shares, format_pct, format_amount

    if not holdings:
        st.markdown(f"""
        <div style="padding: 16px; background: rgba(0,0,0,0.2); border-radius: 12px; border-left: 4px solid {color}; margin-bottom: 12px;">
            <div style="font-size: 16px; font-weight: 600; color: {color};">{icon} {title}</div>
            <div style="color: rgba(255,255,255,0.5); margin-top: 8px;">無變動</div>
        </div>
        """, unsafe_allow_html=True)
        return

    items_html = ""
    for h in holdings[:10]:  # 最多顯示 10 筆
        value_str = format_amount(h.value_change) if h.value_change else "—"
        pct_str = format_pct(h.change_pct) if h.change_pct else ""

        if change_type == "new":
            detail = f"股數: {format_shares(h.shares_new)} | 權重: {h.weight:.2f}%"
        elif change_type == "exit":
            detail = f"原股數: {format_shares(h.shares_old)}"
        else:
            detail = f"{format_shares(h.shares_old)} → {format_shares(h.shares_new)} ({pct_str})"

        items_html += f"""
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
            <div>
                <div style="font-weight: 600; color: #fff;">{h.code} {h.name}</div>
                <div style="font-size: 12px; color: rgba(255,255,255,0.5);">{detail}</div>
            </div>
            <div style="text-align: right;">
                <div style="color: {color}; font-weight: 600; font-family: 'JetBrains Mono', monospace;">{value_str}</div>
            </div>
        </div>
        """

    count_str = f"({len(holdings)} 檔)" if len(holdings) > 0 else ""

    st.markdown(f"""
    <div style="padding: 16px; background: rgba(0,0,0,0.2); border-radius: 12px; border-left: 4px solid {color}; margin-bottom: 12px;">
        <div style="font-size: 16px; font-weight: 600; color: {color}; margin-bottom: 12px;">{icon} {title} {count_str}</div>
        {items_html}
    </div>
    """, unsafe_allow_html=True)


def render_top_holdings_table(holdings: list):
    """渲染 Top 持股表格"""
    if not holdings:
        st.info("無持股資料")
        return

    from active_etf_tracker import format_shares

    items_html = ""
    for i, h in enumerate(holdings[:15], 1):
        price_str = f"${h.price:.2f}" if h.price else "—"
        items_html += f"""
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
            <td style="padding: 10px 8px; color: rgba(255,255,255,0.5);">{i}</td>
            <td style="padding: 10px 8px; font-weight: 600;">{h.code}</td>
            <td style="padding: 10px 8px;">{h.name}</td>
            <td style="padding: 10px 8px; text-align: right; color: #55efc4; font-family: 'JetBrains Mono', monospace;">{h.weight:.2f}%</td>
            <td style="padding: 10px 8px; text-align: right; font-family: 'JetBrains Mono', monospace;">{format_shares(h.shares)}</td>
            <td style="padding: 10px 8px; text-align: right; color: #74b9ff;">{price_str}</td>
        </tr>
        """

    st.markdown(f"""
    <div class="strategy-box slide-in">
        <div class="strategy-title">🏆 Top 15 持股</div>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <thead>
                <tr style="border-bottom: 2px solid rgba(255,255,255,0.1);">
                    <th style="padding: 8px; text-align: left; color: rgba(255,255,255,0.6); font-size: 12px;">#</th>
                    <th style="padding: 8px; text-align: left; color: rgba(255,255,255,0.6); font-size: 12px;">代碼</th>
                    <th style="padding: 8px; text-align: left; color: rgba(255,255,255,0.6); font-size: 12px;">名稱</th>
                    <th style="padding: 8px; text-align: right; color: rgba(255,255,255,0.6); font-size: 12px;">權重</th>
                    <th style="padding: 8px; text-align: right; color: rgba(255,255,255,0.6); font-size: 12px;">股數</th>
                    <th style="padding: 8px; text-align: right; color: rgba(255,255,255,0.6); font-size: 12px;">現價</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)


def render_holding_change_summary(result):
    """渲染持股變動統計"""
    st.markdown(f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;">
        <div class="metric-card slide-in" style="border-left-color: #00b894; min-height: 80px;">
            <div class="metric-label">新建倉</div>
            <div class="metric-value" style="font-size: 32px; color: #00b894;">{len(result.new_positions)}</div>
        </div>
        <div class="metric-card slide-in" style="border-left-color: #55efc4; min-height: 80px;">
            <div class="metric-label">加碼</div>
            <div class="metric-value" style="font-size: 32px; color: #55efc4;">{len(result.increased)}</div>
        </div>
        <div class="metric-card slide-in" style="border-left-color: #fdcb6e; min-height: 80px;">
            <div class="metric-label">減碼</div>
            <div class="metric-value" style="font-size: 32px; color: #fdcb6e;">{len(result.decreased)}</div>
        </div>
        <div class="metric-card slide-in" style="border-left-color: #ff7675; min-height: 80px;">
            <div class="metric-label">出清</div>
            <div class="metric-value" style="font-size: 32px; color: #ff7675;">{len(result.exited)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
