"""
台股 ETF 戰情室 - 主程式入口
(重構版 - 模組化架構)

此檔案為 Streamlit Cloud 入口點，實際邏輯已拆分至各模組：
- config.py: 配置常數
- data_fetcher.py: 數據獲取
- strategies.py: 策略計算
- ui_components.py: UI 組件
"""
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import urllib3

from config import TOP_150_LIMIT
from data_fetcher import (
    get_all_market_indicators,
    fetch_taifex_rankings,
    fetch_msci_list,
    fetch_all_etf_holdings,
)
from strategies import (
    analyze_0050_strategy,
    analyze_msci_strategy,
    analyze_0056_strategy,
    enrich_dataframe,
    enrich_with_dividend_yield,
    filter_high_yield_stocks,
    calculate_tech_alpha_portfolio,
    get_active_high_yield_schedules,
)
from ui_components import (
    inject_custom_css,
    render_vix_card,
    render_vixtwn_card,
    render_twii_card,
    render_link_card,
    render_0050_strategy_box,
    render_msci_strategy_box,
    render_0056_strategy_box,
    render_alpha_strategy_box,
    render_weight_strategy_box,
    render_alpha_short_position,
    get_column_config,
    render_etf_rotation_strategy_box,
    render_risk_management_strategy_box,
    render_dividend_alert,
    render_rotation_signal_card,
    render_stop_loss_result,
    render_position_size_result,
    render_kelly_result,
    render_allocation_chart,
    render_active_etf_strategy_box,
    render_etf_summary_card,
    render_position_change_card,
    render_top_holdings_table,
    render_holding_change_summary,
)
from etf_rotation import (
    THEME_ETFS,
    ETF_CATEGORIES,
    fetch_etf_performance,
    calculate_rotation_signals,
    get_upcoming_dividends,
    build_etf_comparison_df,
)
from risk_management import (
    RiskLevel,
    RISK_PARAMS,
    calculate_stop_loss,
    calculate_position_size,
    calculate_kelly_criterion,
    get_allocation_suggestion,
)
from active_etf_tracker import (
    ACTIVE_ETFS,
    parse_holdings_excel,
    compare_holdings,
    format_amount,
    format_shares,
    format_pct,
)


# =============================================================================
# 頁面設定
# =============================================================================

st.set_page_config(
    page_title="台股 ETF 戰情室 (VIXTWN 加強版)",
    layout="wide",
    initial_sidebar_state="expanded"
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
inject_custom_css()


# =============================================================================
# 快取數據載入
# =============================================================================

@st.cache_data(ttl=300)
def load_market_indicators():
    """載入市場指標 (5分鐘快取)"""
    return get_all_market_indicators()


@st.cache_data(ttl=3600)
def load_market_data():
    """載入市場數據 (1小時快取)"""
    df_mcap = fetch_taifex_rankings()
    msci_codes = fetch_msci_list()
    holdings = fetch_all_etf_holdings()
    return df_mcap, msci_codes, holdings


# =============================================================================
# 主程式
# =============================================================================

def main():
    # 標題
    st.title("🚀 台股 ETF 戰情室 (全攻略版)")
    st.caption("0050 | MSCI | 高股息 | VIXTWN 監控 | Alpha 對沖")

    # 載入市場指標
    indicators = load_market_indicators()

    # 頂部指標列 (5 欄)
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        render_vix_card(indicators.get("VIX", {}))

    with col2:
        render_vixtwn_card(indicators.get("VIXTWN", {}))

    with col3:
        render_link_card(
            "🇺🇸 CNN 恐懼貪婪",
            "https://edition.cnn.com/markets/fear-and-greed",
            "#f1c40f"
        )

    with col4:
        render_twii_card(indicators.get("TWII", {}))

    with col5:
        render_link_card(
            "📊 融資維持率",
            "https://www.macromicro.me/charts/53117/taiwan-taiex-maintenance-margin",
            "#9b59b6"
        )

    st.divider()

    # 載入市場數據
    with st.spinner("正在進行全市場掃描..."):
        df_mcap, msci_codes, holdings = load_market_data()

    if df_mcap.empty:
        st.error("無法取得市值資料，請稍後再試。")
        st.stop()

    # 側邊欄
    with st.sidebar:
        st.header("📡 市場雷達")

        active_schedules = get_active_high_yield_schedules()
        if active_schedules:
            st.error(f"🔥 **本月焦點:** {', '.join(active_schedules)}")
        else:
            st.info("本月無大型調整")

        st.divider()

        if st.button("🔄 更新行情", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption(f"最後更新: {datetime.now().strftime('%H:%M')}")

    # 分頁
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🇹🇼 0050 權值",
        "🌍 MSCI 外資",
        "💰 0056 高股息",
        "📊 全市場權重",
        "⚡ Alpha 對沖",
        "🔄 ETF 輪動",
        "🛡️ 風險管理",
        "🎯 主動型 ETF"
    ])

    column_cfg = get_column_config()
    display_columns = ["排名", "連結代碼", "股票名稱", "現價", "成交值", "漲跌幅", "成交量"]

    # ==========================================================================
    # Tab 1: 0050 權值
    # ==========================================================================
    with tab1:
        render_0050_strategy_box()

        if holdings.get("0050"):
            result = analyze_0050_strategy(df_mcap, holdings["0050"])

            col_in, col_out = st.columns(2)

            with col_in:
                st.success("🟢 **潛在納入 (Rank ≤ 40)**")
                if not result.potential_in.empty:
                    df_show = enrich_dataframe(result.potential_in, result.all_codes)
                    st.dataframe(
                        df_show[display_columns],
                        hide_index=True,
                        column_config=column_cfg
                    )
                else:
                    st.info("目前無潛在納入標的")

            with col_out:
                st.error("🔴 **潛在剔除 (Rank > 60)**")
                if not result.potential_out.empty:
                    df_show = enrich_dataframe(result.potential_out, result.all_codes)
                    st.dataframe(
                        df_show[display_columns],
                        hide_index=True,
                        column_config=column_cfg
                    )
                else:
                    st.info("目前無潛在剔除標的")

    # ==========================================================================
    # Tab 2: MSCI 外資
    # ==========================================================================
    with tab2:
        render_msci_strategy_box()

        if msci_codes:
            result = analyze_msci_strategy(df_mcap, msci_codes)

            col_in, col_out = st.columns(2)

            with col_in:
                st.success("🟢 **潛在納入 (外資買盤)**")
                if not result.potential_in.empty:
                    df_show = enrich_dataframe(result.potential_in, result.all_codes)
                    st.dataframe(
                        df_show[display_columns],
                        hide_index=True,
                        column_config=column_cfg
                    )
                else:
                    st.info("目前無潛在納入標的")

            with col_out:
                st.error("🔴 **潛在剔除 (外資賣盤)**")
                if not result.potential_out.empty:
                    df_show = enrich_dataframe(result.potential_out, result.all_codes)
                    st.dataframe(
                        df_show[display_columns],
                        hide_index=True,
                        column_config=column_cfg
                    )
                else:
                    st.info("目前無潛在剔除標的")
        else:
            st.warning("無法取得 MSCI 成分股資料")

    # ==========================================================================
    # Tab 3: 0056 高股息
    # ==========================================================================
    with tab3:
        render_0056_strategy_box()

        hy_result = analyze_0056_strategy(df_mcap, holdings)

        with st.spinner("計算殖利率排行中..."):
            df_enriched = enrich_with_dividend_yield(hy_result.df, hy_result.codes)
            df_enriched = enrich_dataframe(df_enriched, hy_result.codes)

        # 篩選模式
        sort_method = st.radio(
            "🔍 掃描模式：",
            ["💰 殖利率排行 (抓高息)", "🔥 量能爆發 (抓偷跑)", "💎 尚未入選 (抓遺珠)"],
            horizontal=True
        )

        if "殖利率" in sort_method:
            df_show = filter_high_yield_stocks(df_enriched, "yield")
        elif "量能" in sort_method:
            df_show = filter_high_yield_stocks(df_enriched, "volume")
        else:
            df_show = filter_high_yield_stocks(df_enriched, "not_selected")

        hy_columns = ["排名", "連結代碼", "股票名稱", "殖利率(%)", "已入選 ETF",
                      "現價", "成交值", "漲跌幅", "成交量"]

        st.dataframe(
            df_show[hy_columns],
            hide_index=True,
            column_config=column_cfg
        )

    # ==========================================================================
    # Tab 4: 全市場權重
    # ==========================================================================
    with tab4:
        render_weight_strategy_box()

        top150 = df_mcap.head(TOP_150_LIMIT).copy()
        codes = list(top150["股票代碼"])

        with st.spinner("計算權重中..."):
            df_150 = enrich_dataframe(top150, codes, add_weight=True)

        weight_columns = ["排名", "連結代碼", "股票名稱", "權重(Top150)",
                         "總市值", "現價", "成交值", "漲跌幅"]

        st.dataframe(
            df_150[weight_columns],
            hide_index=True,
            column_config=column_cfg
        )

    # ==========================================================================
    # Tab 5: 電子 Alpha 對沖
    # ==========================================================================
    with tab5:
        render_alpha_strategy_box()

        col_input, col_info = st.columns([1, 2])

        with col_input:
            capital = st.number_input(
                "總投資金額 (TWD)",
                min_value=100000,
                value=1000000,
                step=50000
            )
            hedge_ratio = st.slider(
                "多空比率 (Long/Short Ratio)",
                0.8, 1.5, 1.0, 0.1
            )
            st.info(f"💡 每買 {int(capital):,} 元股票，需放空約 {int(capital/hedge_ratio):,} 元期貨。")

        with col_info:
            with st.spinner("正在篩選 Top 50 電子/半導體股..."):
                alpha_result = calculate_tech_alpha_portfolio(capital, hedge_ratio, df_mcap)

        if alpha_result.success and alpha_result.long_positions is not None:
            col_long, col_short = st.columns(2)

            with col_long:
                st.markdown(f"### 🟢 多方部位 (現貨: ${int(capital):,})")

                alpha_columns = ["股票名稱", "Sector", "連結代碼", "現價",
                                "配置權重(%)", "分配金額", "建議買進(股)"]

                st.dataframe(
                    alpha_result.long_positions[alpha_columns],
                    hide_index=True,
                    column_config=column_cfg
                )

                with st.expander("查看原始產業分類 (Debug)"):
                    st.dataframe(alpha_result.debug_df, hide_index=True)

            with col_short:
                st.markdown(f"### 🔴 空方部位 (期貨: ${alpha_result.short_info['short_value']:,})")
                render_alpha_short_position(alpha_result.short_info)
        else:
            st.warning("無法找到符合條件的電子/半導體股，請檢查資料來源。")

            with st.expander("查看產業分類 (Debug)"):
                st.dataframe(alpha_result.debug_df, hide_index=True)

    # ==========================================================================
    # Tab 6: ETF 輪動
    # ==========================================================================
    with tab6:
        render_etf_rotation_strategy_box()

        # 配息提醒
        upcoming_dividends = get_upcoming_dividends()
        render_dividend_alert(upcoming_dividends)

        # 選擇 ETF 類別
        category = st.selectbox(
            "選擇 ETF 類別",
            options=list(ETF_CATEGORIES.keys()),
            index=0
        )

        # 選擇績效區間
        period = st.radio(
            "績效區間",
            ["1mo", "3mo", "6mo", "1y"],
            horizontal=True,
            index=1,
            format_func=lambda x: {"1mo": "1個月", "3mo": "3個月", "6mo": "6個月", "1y": "1年"}[x]
        )

        # 獲取績效數據
        with st.spinner("載入 ETF 績效數據..."):
            all_codes = [etf.code for etf in THEME_ETFS]
            performance = fetch_etf_performance(all_codes, period)

        # 計算輪動信號
        signals = calculate_rotation_signals(performance, category)

        # 信號統計
        col_s1, col_s2, col_s3 = st.columns(3)
        strong_count = len([s for s in signals if s.signal == "強勢"])
        watch_count = len([s for s in signals if s.signal == "觀望"])
        weak_count = len([s for s in signals if s.signal == "弱勢"])

        with col_s1:
            render_rotation_signal_card("強勢", strong_count, "#55efc4")
        with col_s2:
            render_rotation_signal_card("觀望", watch_count, "#ffeaa7")
        with col_s3:
            render_rotation_signal_card("弱勢", weak_count, "#ff7675")

        st.divider()

        # 輪動信號表
        st.subheader(f"📊 {category} ETF 輪動信號")

        for signal in signals:
            if signal.signal == "強勢":
                icon, color = "🟢", "#55efc4"
            elif signal.signal == "觀望":
                icon, color = "🟡", "#ffeaa7"
            else:
                icon, color = "🔴", "#ff7675"

            perf = performance.get(signal.code, {})

            col_info, col_perf = st.columns([1, 2])

            with col_info:
                st.markdown(f"""
                <div style="padding: 12px; background: rgba(0,0,0,0.2); border-radius: 8px; border-left: 4px solid {color};">
                    <div style="font-size: 18px; font-weight: 600;">{icon} {signal.code} {signal.name}</div>
                    <div style="color: rgba(255,255,255,0.6); font-size: 13px; margin-top: 4px;">{signal.reason}</div>
                    <div style="color: {color}; font-size: 14px; font-weight: 600; margin-top: 4px;">評分: {signal.score}/100</div>
                </div>
                """, unsafe_allow_html=True)

            with col_perf:
                st.markdown(f"""
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; text-align: center;">
                    <div style="padding: 8px; background: rgba(0,0,0,0.15); border-radius: 6px;">
                        <div style="color: rgba(255,255,255,0.5); font-size: 10px;">現價</div>
                        <div style="color: #fff; font-weight: 600;">{perf.get('現價', '-')}</div>
                    </div>
                    <div style="padding: 8px; background: rgba(0,0,0,0.15); border-radius: 6px;">
                        <div style="color: rgba(255,255,255,0.5); font-size: 10px;">報酬率</div>
                        <div style="color: {'#55efc4' if perf.get('raw_return', 0) > 0 else '#ff7675'}; font-weight: 600;">{perf.get('報酬率', '-')}%</div>
                    </div>
                    <div style="padding: 8px; background: rgba(0,0,0,0.15); border-radius: 6px;">
                        <div style="color: rgba(255,255,255,0.5); font-size: 10px;">最大回撤</div>
                        <div style="color: #ff7675; font-weight: 600;">{perf.get('最大回撤', '-')}%</div>
                    </div>
                    <div style="padding: 8px; background: rgba(0,0,0,0.15); border-radius: 6px;">
                        <div style="color: rgba(255,255,255,0.5); font-size: 10px;">波動率</div>
                        <div style="color: #74b9ff; font-weight: 600;">{perf.get('波動率', '-')}%</div>
                    </div>
                    <div style="padding: 8px; background: rgba(0,0,0,0.15); border-radius: 6px;">
                        <div style="color: rgba(255,255,255,0.5); font-size: 10px;">距高點</div>
                        <div style="color: #ffeaa7; font-weight: 600;">{perf.get('距高點', '-')}%</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.write("")

        # ETF 比較表
        with st.expander("📋 查看完整 ETF 比較表"):
            category_codes = ETF_CATEGORIES.get(category, [])
            df_compare = build_etf_comparison_df(category_codes, performance)
            st.dataframe(df_compare, hide_index=True, column_config=column_cfg)

    # ==========================================================================
    # Tab 7: 風險管理
    # ==========================================================================
    with tab7:
        render_risk_management_strategy_box()

        # 風險等級選擇
        risk_level_name = st.radio(
            "選擇風險屬性",
            ["保守型", "穩健型", "積極型"],
            horizontal=True,
            index=1
        )

        risk_level_map = {
            "保守型": RiskLevel.CONSERVATIVE,
            "穩健型": RiskLevel.MODERATE,
            "積極型": RiskLevel.AGGRESSIVE
        }
        risk_level = risk_level_map[risk_level_name]
        params = RISK_PARAMS[risk_level]

        # 顯示風險參數
        st.info(f"""
        📋 **{risk_level_name}參數**:
        單一部位上限 {params['max_single_position']*100:.0f}% |
        停損 {params['stop_loss_pct']*100:.0f}% |
        停利 {params['take_profit_pct']*100:.0f}% |
        總曝險上限 {params['max_total_exposure']*100:.0f}%
        """)

        st.divider()

        # 三個工具並列
        tool_tab1, tool_tab2, tool_tab3 = st.tabs([
            "🛑 停損停利計算",
            "📐 部位大小計算",
            "🎰 凱利公式"
        ])

        # 停損停利計算
        with tool_tab1:
            col_input1, col_result1 = st.columns([1, 2])

            with col_input1:
                st.markdown("#### 輸入參數")
                entry_price = st.number_input(
                    "進場價格",
                    min_value=1.0,
                    value=100.0,
                    step=0.5,
                    key="sl_entry"
                )
                position_size = st.number_input(
                    "持股股數",
                    min_value=1000,
                    value=1000,
                    step=1000,
                    key="sl_size"
                )
                stop_loss_pct = st.slider(
                    "停損幅度 (%)",
                    1, 20,
                    int(params['stop_loss_pct'] * 100),
                    key="sl_pct"
                ) / 100
                take_profit_pct = st.slider(
                    "停利幅度 (%)",
                    5, 50,
                    int(params['take_profit_pct'] * 100),
                    key="tp_pct"
                ) / 100

            with col_result1:
                st.markdown("#### 計算結果")
                sl_result = calculate_stop_loss(
                    entry_price, stop_loss_pct, take_profit_pct, position_size
                )
                render_stop_loss_result(sl_result)

        # 部位大小計算
        with tool_tab2:
            col_input2, col_result2 = st.columns([1, 2])

            with col_input2:
                st.markdown("#### 輸入參數")
                total_capital = st.number_input(
                    "總資金",
                    min_value=100000,
                    value=1000000,
                    step=100000,
                    key="ps_capital"
                )
                ps_entry = st.number_input(
                    "進場價格",
                    min_value=1.0,
                    value=100.0,
                    step=0.5,
                    key="ps_entry"
                )
                ps_stop = st.number_input(
                    "停損價格",
                    min_value=1.0,
                    value=92.0,
                    step=0.5,
                    key="ps_stop"
                )
                risk_per_trade = st.slider(
                    "每筆交易風險 (%)",
                    1, 5, 2,
                    key="ps_risk"
                ) / 100

            with col_result2:
                st.markdown("#### 計算結果")
                ps_result = calculate_position_size(
                    total_capital,
                    ps_entry,
                    ps_stop,
                    risk_per_trade,
                    params['max_single_position']
                )
                render_position_size_result(ps_result)

        # 凱利公式
        with tool_tab3:
            col_input3, col_result3 = st.columns([1, 2])

            with col_input3:
                st.markdown("#### 輸入參數")
                win_rate = st.slider(
                    "勝率 (%)",
                    30, 80, 55,
                    key="kelly_wr"
                ) / 100
                avg_win = st.number_input(
                    "平均獲利金額",
                    min_value=1000,
                    value=15000,
                    step=1000,
                    key="kelly_win"
                )
                avg_loss = st.number_input(
                    "平均虧損金額",
                    min_value=1000,
                    value=10000,
                    step=1000,
                    key="kelly_loss"
                )
                use_half = st.checkbox("使用半凱利 (更保守)", value=True, key="kelly_half")

            with col_result3:
                st.markdown("#### 計算結果")
                kelly_result = calculate_kelly_criterion(
                    win_rate, avg_win, avg_loss, use_half
                )
                render_kelly_result(kelly_result)

        st.divider()

        # 資產配置建議
        st.subheader("📊 資產配置建議")

        col_alloc_input, col_alloc_result = st.columns([1, 2])

        with col_alloc_input:
            alloc_capital = st.number_input(
                "總投資資金",
                min_value=100000,
                value=1000000,
                step=100000,
                key="alloc_cap"
            )
            market_condition = st.radio(
                "市場狀態",
                ["bullish", "neutral", "bearish"],
                horizontal=True,
                index=1,
                format_func=lambda x: {"bullish": "🐂 多頭", "neutral": "⚖️ 中性", "bearish": "🐻 空頭"}[x]
            )

        with col_alloc_result:
            alloc_result = get_allocation_suggestion(
                alloc_capital, risk_level, market_condition
            )
            render_allocation_chart(alloc_result)

    # ==========================================================================
    # Tab 8: 主動型 ETF 追蹤
    # ==========================================================================
    with tab8:
        render_active_etf_strategy_box()

        # ETF 選擇
        etf_options = {f"{code} {info['name']}": code for code, info in ACTIVE_ETFS.items()}
        selected_etf_display = st.selectbox(
            "選擇追蹤的主動型 ETF",
            options=list(etf_options.keys()),
            index=0
        )
        selected_etf = etf_options[selected_etf_display]
        etf_info = ACTIVE_ETFS[selected_etf]

        st.info(f"📋 **{etf_info['name']}** | 經理公司: {etf_info['manager']} | {etf_info['description']}")

        st.divider()

        # 檔案上傳區
        st.subheader("📁 上傳持股明細")
        st.caption("請從投信官網下載 ETF 持股明細 Excel 檔案")

        col_upload1, col_upload2 = st.columns(2)

        with col_upload1:
            st.markdown("#### 📅 今日持股")
            file_new = st.file_uploader(
                "上傳今日持股 Excel",
                type=['xlsx', 'xls'],
                key="active_etf_new",
                help="格式: ETF_Investment_Portfolio_YYYYMMDD.xlsx"
            )
            date_new = st.text_input("今日日期 (YYYYMMDD)", value=datetime.now().strftime("%Y%m%d"), key="date_new")

        with col_upload2:
            st.markdown("#### 📅 比較日持股")
            file_old = st.file_uploader(
                "上傳比較日持股 Excel",
                type=['xlsx', 'xls'],
                key="active_etf_old",
                help="格式: ETF_Investment_Portfolio_YYYYMMDD.xlsx"
            )
            date_old = st.text_input("比較日日期 (YYYYMMDD)", value=(datetime.now() - timedelta(days=2)).strftime("%Y%m%d"), key="date_old")

        if file_new and file_old:
            try:
                with st.spinner("解析持股資料中..."):
                    # 解析 Excel
                    df_raw_new, df_holdings_new = parse_holdings_excel(file_new, is_streamlit_upload=True)
                    file_old.seek(0)
                    df_raw_old, df_holdings_old = parse_holdings_excel(file_old, is_streamlit_upload=True)

                    # 比較持股
                    fetch_prices = st.checkbox("取得即時股價 (較慢)", value=False, key="fetch_prices")

                    if st.button("🔍 開始比較分析", type="primary", use_container_width=True):
                        with st.spinner("比較持股變化中..." + (" (含股價查詢)" if fetch_prices else "")):
                            result = compare_holdings(
                                df_holdings_new, df_holdings_old,
                                df_raw_new, df_raw_old,
                                date_new, date_old,
                                fetch_prices=fetch_prices
                            )

                        st.success(f"✅ 分析完成！比較期間: {date_old} → {date_new}")

                        # ETF 摘要
                        render_etf_summary_card(result.summary, date_new, date_old)

                        # 變動統計
                        render_holding_change_summary(result)

                        st.divider()

                        # 變動明細
                        col_changes1, col_changes2 = st.columns(2)

                        with col_changes1:
                            render_position_change_card(
                                "新建倉 (重點追蹤!)",
                                result.new_positions,
                                "new",
                                "🌟",
                                "#00b894"
                            )
                            render_position_change_card(
                                "加碼中",
                                [h for h in result.increased if h.change_pct >= 10],
                                "increase",
                                "📈",
                                "#55efc4"
                            )

                        with col_changes2:
                            render_position_change_card(
                                "出清 (避開)",
                                result.exited,
                                "exit",
                                "🚫",
                                "#ff7675"
                            )
                            render_position_change_card(
                                "減碼中",
                                [h for h in result.decreased if h.change_pct <= -10],
                                "decrease",
                                "📉",
                                "#fdcb6e"
                            )

                        st.divider()

                        # Top 持股
                        render_top_holdings_table(result.top_holdings)

                        # 完整資料表
                        with st.expander("📋 查看完整持股變動明細"):
                            df_display = pd.DataFrame([
                                {
                                    "代碼": h.code,
                                    "名稱": h.name,
                                    "權重(%)": f"{h.weight:.2f}" if h.weight else "—",
                                    "前股數": format_shares(h.shares_old),
                                    "今股數": format_shares(h.shares_new),
                                    "股數變化": format_shares(h.shares_change),
                                    "變化%": format_pct(h.change_pct),
                                    "類型": h.change_type.value,
                                    "現價": f"${h.price:.2f}" if h.price else "—",
                                    "金額變化": format_amount(h.value_change) if h.value_change else "—",
                                }
                                for h in result.all_holdings
                            ])
                            st.dataframe(df_display, hide_index=True, use_container_width=True)

                        # 下載報告
                        st.download_button(
                            "📥 下載分析報告 (CSV)",
                            df_display.to_csv(index=False).encode('utf-8-sig'),
                            file_name=f"{selected_etf}_changes_{date_old}_to_{date_new}.csv",
                            mime="text/csv"
                        )

            except Exception as e:
                st.error(f"❌ 解析錯誤: {str(e)}")
                st.caption("請確認上傳的檔案格式正確，需包含「股票代號」「股票名稱」「股數」等欄位")

        else:
            st.warning("👆 請上傳兩個日期的持股明細 Excel 檔案進行比較")

            # 使用說明
            with st.expander("📖 使用說明"):
                st.markdown("""
                ### 如何取得持股明細？

                1. **永豐投信 (00981A)**
                   - 前往 [永豐投信官網](https://www.sinopac.com/sinopacFunds/)
                   - 找到 ETF 持股明細下載區

                2. **其他投信**
                   - 各投信官網通常有 ETF 持股明細 Excel 下載

                ### 檔案格式要求

                Excel 檔案需包含以下欄位：
                - 股票代號
                - 股票名稱
                - 股數
                - 持股權重 (可選)

                ### 策略應用

                - **新建倉**: ETF 剛開始買進的標的，可能是經理人看好的新機會
                - **大幅加碼**: 經理人持續看好，可考慮跟進
                - **減碼/出清**: ETF 正在退出的標的，宜避開
                """)


if __name__ == "__main__":
    main()
