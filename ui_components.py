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
