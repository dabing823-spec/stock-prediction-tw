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
    render_cash_level_analysis,
    render_holding_period_analysis,
    render_weight_signals,
    # PocketStock 風格組件
    render_pocketstock_summary_cards,
    render_consecutive_changes_box,
    render_holdings_table_with_search,
    render_etf_header_card,
    # 擁擠交易與 P/C Ratio 組件
    render_crowded_trade_guide,
    render_pc_ratio_analysis,
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
    get_available_dates,
    load_holdings_from_drive,
)
from etf_analytics import (
    load_historical_data,
    analyze_cash_levels,
    analyze_holding_periods,
    get_holding_statistics,
    analyze_weight_signals,
)
from institutional_tracker import (
    get_institutional_signal,
    InstitutionalSignal,
    analyze_pc_ratio,
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

def _render_etf_analysis_result(result, etf_code: str, date_new: str, date_old: str):
    """渲染 ETF 持股分析結果 (共用函數)"""
    # 格式化日期顯示
    if len(date_new) == 8:
        formatted_date = f"{date_new[:4]}-{date_new[4:6]}-{date_new[6:8]}"
    else:
        formatted_date = date_new

    # PocketStock 風格摘要卡片
    total_holdings = len([h for h in result.all_holdings if h.shares_new > 0])
    new_increased = len(result.new_positions) + len([h for h in result.increased if h.change_pct >= 10])
    removed_decreased = len(result.exited) + len([h for h in result.decreased if h.change_pct <= -10])

    render_pocketstock_summary_cards(
        total_holdings=total_holdings,
        last_update=formatted_date,
        new_increased=new_increased,
        removed_decreased=removed_decreased
    )

    # ETF 摘要 (原有)
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

    # 完整資料表 (含搜尋功能)
    with st.expander("📋 查看完整持股變動明細", expanded=False):
        df_display = pd.DataFrame([
            {
                "股票代號": h.code,
                "股票名稱": h.name,
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

        # 搜尋功能
        search_query = st.text_input(
            "🔍 搜尋股票代號或名稱...",
            placeholder="輸入代號或名稱篩選",
            key="holdings_detail_search"
        )

        if search_query:
            mask = (
                df_display["股票代號"].astype(str).str.contains(search_query, case=False, na=False) |
                df_display["股票名稱"].astype(str).str.contains(search_query, case=False, na=False)
            )
            filtered_df = df_display[mask]
            st.caption(f"找到 {len(filtered_df)} 筆結果")
        else:
            filtered_df = df_display

        st.dataframe(filtered_df, hide_index=True, use_container_width=True)

    # 下載報告
    st.download_button(
        "📥 下載分析報告 (CSV)",
        df_display.to_csv(index=False).encode('utf-8-sig'),
        file_name=f"{etf_code}_changes_{date_old}_to_{date_new}.csv",
        mime="text/csv"
    )


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

        # === 法人籌碼訊號 (次等訊號) ===
        st.subheader("📊 法人籌碼")

        try:
            inst_signal = get_institutional_signal()

            # 紅綠燈顯示
            signal_colors = {
                "green": "🟢",
                "red": "🔴",
                "yellow": "🟡"
            }

            # 訊號強度顯示
            strength_display = "★" * inst_signal.strength + "☆" * (5 - inst_signal.strength)

            # 主要訊號卡片
            if inst_signal.signal == "bullish":
                st.success(f"{inst_signal.emoji} **偏多** {strength_display}")
            elif inst_signal.signal == "bearish":
                st.error(f"{inst_signal.emoji} **偏空** {strength_display}")
            else:
                st.warning(f"{inst_signal.emoji} **中性** {strength_display}")

            st.caption(inst_signal.summary)

            # 展開詳細資訊
            with st.expander("📋 詳細籌碼", expanded=False):
                for detail in inst_signal.details:
                    st.write(detail)

                if inst_signal.futures_position:
                    f = inst_signal.futures_position
                    st.markdown("**台指期部位:**")
                    st.write(f"外資淨: {f.foreign_net:,} 口 (今日 {f.foreign_net_change:+,})")
                    st.write(f"自營淨: {f.dealer_net:,} 口")
                    st.write(f"投信淨: {f.trust_net:,} 口")

                if inst_signal.pc_ratio:
                    pc = inst_signal.pc_ratio
                    st.markdown("**選擇權 P/C Ratio:**")
                    st.write(f"未平倉: {pc.pc_oi_ratio:.2f}")
                    st.write(f"成交量: {pc.pc_volume_ratio:.2f}")

                st.caption(f"資料日期: {inst_signal.date}")

        except Exception as e:
            st.warning("籌碼資料載入中...")
            st.caption(f"({str(e)[:30]})")

        st.divider()

        if st.button("🔄 更新行情", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption(f"最後更新: {datetime.now().strftime('%H:%M')}")

    # 分頁 (標籤已縮短以優化手機顯示)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🇹🇼 0050",
        "🌍 MSCI",
        "💰 高股息",
        "📊 權重",
        "⚡ Alpha",
        "🔄 輪動",
        "🛡️ 風控",
        "🎯 主動ETF"
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

        # 初始化 session_state
        if "tab3_dividend_loaded" not in st.session_state:
            st.session_state.tab3_dividend_loaded = False
            st.session_state.tab3_df_enriched = None

        # 手動觸發殖利率載入
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            load_dividend = st.button(
                "💰 載入殖利率排行",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.tab3_dividend_loaded
            )
        with col_info:
            if st.session_state.tab3_dividend_loaded:
                st.success("✅ 殖利率資料已載入")
            else:
                st.info("⏱️ 載入殖利率約需 5-10 秒 (150 檔股票並行查詢)")

        # 載入殖利率資料
        if load_dividend and not st.session_state.tab3_dividend_loaded:
            with st.spinner("計算殖利率排行中... (並行查詢 150 檔)"):
                df_enriched = enrich_with_dividend_yield(hy_result.df, hy_result.codes)
                df_enriched = enrich_dataframe(df_enriched, hy_result.codes)
                st.session_state.tab3_df_enriched = df_enriched
                st.session_state.tab3_dividend_loaded = True
                st.rerun()

        # 使用快取的資料或基本資料
        if st.session_state.tab3_dividend_loaded and st.session_state.tab3_df_enriched is not None:
            df_enriched = st.session_state.tab3_df_enriched

            # 篩選模式 (含殖利率)
            sort_method = st.radio(
                "🔍 掃描模式：",
                ["💰 殖利率排行 (抓高息)", "🔥 量能爆發 (抓偷跑)", "💎 尚未入選 (抓遺珠)"],
                horizontal=True,
                key="tab3_sort_with_yield"
            )

            if "殖利率" in sort_method:
                df_show = filter_high_yield_stocks(df_enriched, "yield")
            elif "量能" in sort_method:
                df_show = filter_high_yield_stocks(df_enriched, "volume")
            else:
                df_show = filter_high_yield_stocks(df_enriched, "not_selected")

            hy_columns = ["排名", "連結代碼", "股票名稱", "殖利率(%)", "已入選 ETF",
                          "現價", "成交值", "漲跌幅", "成交量"]

        else:
            # 未載入殖利率時，只顯示基本資料
            df_basic = enrich_dataframe(hy_result.df, hy_result.codes)

            # 篩選模式 (無殖利率)
            sort_method = st.radio(
                "🔍 掃描模式：",
                ["🔥 量能爆發 (抓偷跑)", "💎 尚未入選 (抓遺珠)"],
                horizontal=True,
                key="tab3_sort_no_yield"
            )

            if "量能" in sort_method:
                df_show = filter_high_yield_stocks(df_basic, "volume")
            else:
                df_show = filter_high_yield_stocks(df_basic, "not_selected")

            hy_columns = ["排名", "連結代碼", "股票名稱", "已入選 ETF",
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

        st.divider()

        # ==========================================================================
        # P/C Ratio 完整分析
        # ==========================================================================
        try:
            pc_analysis = analyze_pc_ratio()
            render_pc_ratio_analysis(pc_analysis)
        except Exception as e:
            st.warning(f"P/C Ratio 分析載入失敗: {str(e)[:50]}")

        st.divider()

        # ==========================================================================
        # 個股擁擠交易檢測指南
        # ==========================================================================
        render_crowded_trade_guide()

    # ==========================================================================
    # Tab 8: 主動型 ETF 追蹤
    # ==========================================================================
    with tab8:
        # ETF 選擇
        etf_options = {f"{code} {info['name']}": code for code, info in ACTIVE_ETFS.items()}
        selected_etf_display = st.selectbox(
            "選擇追蹤的主動型 ETF",
            options=list(etf_options.keys()),
            index=0,
            label_visibility="collapsed"
        )
        selected_etf = etf_options[selected_etf_display]
        etf_info = ACTIVE_ETFS[selected_etf]

        # PocketStock 風格標題卡片
        render_etf_header_card(
            etf_name=etf_info['name'],
            etf_code=selected_etf,
            manager=etf_info.get('manager')
        )

        # 載入連續加碼/減碼資料 (如果有 Google Drive)
        has_drive = etf_info.get("drive_folder") is not None
        if has_drive:
            # 嘗試載入歷史資料以分析連續變化
            if "tab8_consecutive_data" not in st.session_state:
                st.session_state.tab8_consecutive_data = None

            col_load, col_status = st.columns([1, 3])
            with col_load:
                if st.button("🔄 載入連續加碼分析", use_container_width=True):
                    with st.spinner("分析連續加碼/減碼趨勢..."):
                        try:
                            historical = load_historical_data(selected_etf, num_dates=5)
                            if historical.get("dates"):
                                consecutive_data = analyze_consecutive_changes(historical)
                                st.session_state.tab8_consecutive_data = consecutive_data
                                st.session_state.tab8_last_update = historical["dates"][-1] if historical["dates"] else ""
                                st.session_state.tab8_total_holdings = len(historical["holdings"].get(historical["dates"][-1], [])) if historical["dates"] else 0
                        except Exception as e:
                            st.error(f"載入失敗: {e}")

            # 顯示連續加碼/減碼
            if st.session_state.get("tab8_consecutive_data"):
                consecutive_data = st.session_state.tab8_consecutive_data
                last_update = st.session_state.get("tab8_last_update", "")
                total_holdings = st.session_state.get("tab8_total_holdings", 0)

                # 格式化日期
                if last_update and len(last_update) == 8:
                    formatted_date = f"{last_update[:4]}-{last_update[4:6]}-{last_update[6:8]}"
                else:
                    formatted_date = last_update

                # 摘要卡片
                new_increased = len(consecutive_data.get("increases", []))
                removed_decreased = len(consecutive_data.get("decreases", []))
                render_pocketstock_summary_cards(
                    total_holdings=total_holdings,
                    last_update=formatted_date,
                    new_increased=new_increased,
                    removed_decreased=removed_decreased
                )

                # 連續加碼/減碼提示框
                render_consecutive_changes_box(consecutive_data)

        st.divider()

        # 資料來源選擇
        has_drive = etf_info.get("drive_folder") is not None
        if has_drive:
            data_source = st.radio(
                "📂 資料來源",
                ["☁️ Google Drive (自動)", "📁 手動上傳"],
                horizontal=True,
                index=0
            )
        else:
            data_source = "📁 手動上傳"
            st.warning(f"⚠️ {etf_info['name']} 尚未設定 Google Drive 資料夾，請使用手動上傳")

        # ========== Google Drive 模式 ==========
        if "Google Drive" in data_source:
            st.subheader("☁️ 從 Google Drive 載入")

            # 取得可用日期
            with st.spinner("正在掃描 Google Drive 資料夾..."):
                available_dates = get_available_dates(selected_etf)

            if not available_dates:
                st.error("❌ 無法取得檔案列表，請確認 Google Drive 資料夾權限或改用手動上傳")
            else:
                st.success(f"✅ 找到 {len(available_dates)} 個持股明細檔案")

                # 日期選擇
                col_date1, col_date2 = st.columns(2)

                date_options = {f"{d['display']} ({d['date']})": d for d in available_dates}

                with col_date1:
                    st.markdown("#### 📅 今日持股")
                    selected_new = st.selectbox(
                        "選擇日期",
                        options=list(date_options.keys()),
                        index=0,
                        key="drive_date_new"
                    )
                    date_info_new = date_options[selected_new]

                with col_date2:
                    st.markdown("#### 📅 比較日持股")
                    # 預設選第二個日期
                    default_idx = min(1, len(date_options) - 1)
                    selected_old = st.selectbox(
                        "選擇日期",
                        options=list(date_options.keys()),
                        index=default_idx,
                        key="drive_date_old"
                    )
                    date_info_old = date_options[selected_old]

                # 選項
                fetch_prices = st.checkbox(
                    "取得即時股價 (可計算金額，約需 30-60 秒)",
                    value=False,
                    key="drive_fetch_prices",
                    help="勾選後將查詢所有持股即時價格，以計算金額變化。不勾選則只顯示股數變化。"
                )

                # 開始分析
                if st.button("🚀 開始比較分析", type="primary", use_container_width=True):
                    try:
                        # 下載並解析檔案
                        with st.spinner(f"正在下載 {date_info_new['name']}..."):
                            df_raw_new, df_holdings_new = load_holdings_from_drive(date_info_new)

                        if df_raw_new is None:
                            st.error(f"❌ 無法下載或解析: {date_info_new['name']}")
                            st.stop()

                        with st.spinner(f"正在下載 {date_info_old['name']}..."):
                            df_raw_old, df_holdings_old = load_holdings_from_drive(date_info_old)

                        if df_raw_old is None:
                            st.error(f"❌ 無法下載或解析: {date_info_old['name']}")
                            st.stop()

                        # 比較持股
                        with st.spinner("比較持股變化中..." + (" (含股價查詢)" if fetch_prices else "")):
                            result = compare_holdings(
                                df_holdings_new, df_holdings_old,
                                df_raw_new, df_raw_old,
                                date_info_new['date'], date_info_old['date'],
                                fetch_prices=fetch_prices
                            )

                        st.success(f"✅ 分析完成！比較期間: {date_info_old['display']} → {date_info_new['display']}")

                        # 顯示結果
                        _render_etf_analysis_result(result, selected_etf, date_info_new['date'], date_info_old['date'])

                    except Exception as e:
                        st.error(f"❌ 分析錯誤: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())

        # ========== 手動上傳模式 ==========
        else:
            st.subheader("📁 手動上傳持股明細")
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
                    # 比較持股
                    fetch_prices = st.checkbox(
                        "取得即時股價 (約需 30-60 秒)",
                        value=False,
                        key="fetch_prices",
                        help="勾選後將查詢所有持股即時價格，以計算金額變化。"
                    )

                    if st.button("🔍 開始比較分析", type="primary", use_container_width=True):
                        with st.spinner("解析持股資料中..."):
                            # 解析 Excel
                            df_raw_new, df_holdings_new = parse_holdings_excel(file_new, is_streamlit_upload=True)
                            file_old.seek(0)
                            df_raw_old, df_holdings_old = parse_holdings_excel(file_old, is_streamlit_upload=True)

                        with st.spinner("比較持股變化中..." + (" (含股價查詢)" if fetch_prices else "")):
                            result = compare_holdings(
                                df_holdings_new, df_holdings_old,
                                df_raw_new, df_raw_old,
                                date_new, date_old,
                                fetch_prices=fetch_prices
                            )

                        st.success(f"✅ 分析完成！比較期間: {date_old} → {date_new}")

                        # 顯示結果
                        _render_etf_analysis_result(result, selected_etf, date_new, date_old)

                except Exception as e:
                    st.error(f"❌ 解析錯誤: {str(e)}")
                    st.caption("請確認上傳的檔案格式正確，需包含「股票代號」「股票名稱」「股數」等欄位")

            else:
                st.warning("👆 請上傳兩個日期的持股明細 Excel 檔案進行比較")

        # 使用說明
        with st.expander("📖 使用說明"):
            st.markdown("""
            ### 資料來源

            **☁️ Google Drive (自動)**
            - 自動從設定的 Google Drive 共享資料夾抓取檔案
            - 目前支援: 00981A 永豐台灣加權

            **📁 手動上傳**
            - 從投信官網下載持股明細 Excel
            - 適用於未設定 Google Drive 的 ETF

            ### 檔案格式要求

            Excel 檔案需包含以下欄位：
            - 股票代號
            - 股票名稱
            - 股數
            - 持股權重 (可選)

            ### 策略應用

            - **🌟 新建倉**: ETF 剛開始買進的標的，可能是經理人看好的新機會 → **重點追蹤！**
            - **📈 大幅加碼**: 經理人持續看好，可考慮跟進
            - **📉 減碼/🚫 出清**: ETF 正在退出的標的，宜避開
            """)

        # ==========================================================================
        # 進階分析區塊
        # ==========================================================================
        st.divider()
        st.subheader("📈 進階分析 (多期歷史)")

        if not etf_info.get("drive_folder"):
            st.warning("⚠️ 進階分析需要 Google Drive 資料夾設定，此 ETF 尚未支援")
        else:
            st.markdown("""
            載入多期歷史資料，分析經理人操作行為：
            - 💵 **現金水位監控** - 追蹤現金配置變化，判斷經理人對市場看法
            - ⏱️ **持股週期分析** - 了解持股習慣，核心持股 vs 短線操作
            - 📊 **部位權重訊號** - 找出高信心標的，追蹤權重變化趨勢
            """)

            col_analytics1, col_analytics2 = st.columns([1, 3])

            with col_analytics1:
                num_periods = st.slider(
                    "分析期數",
                    min_value=3,
                    max_value=20,
                    value=10,
                    step=1,
                    key="analytics_periods",
                    help="載入越多期資料分析越準確，但速度較慢"
                )

            with col_analytics2:
                run_analytics = st.button(
                    "🚀 開始進階分析",
                    type="primary",
                    use_container_width=True,
                    key="run_analytics_btn"
                )

            if run_analytics:
                try:
                    # 載入歷史資料
                    with st.spinner(f"正在載入 {num_periods} 期歷史資料..."):
                        historical_data = load_historical_data(selected_etf, num_periods)

                    if not historical_data.get("dates"):
                        st.error("❌ 無法載入歷史資料")
                    else:
                        dates = historical_data.get("dates", [])
                        st.success(f"✅ 已載入 {len(dates)} 期資料 ({dates[0]} ~ {dates[-1]})")

                        # 使用分頁顯示三種分析
                        analytics_tab1, analytics_tab2, analytics_tab3 = st.tabs([
                            "💵 現金水位",
                            "⏱️ 持股週期",
                            "📊 權重訊號"
                        ])

                        with analytics_tab1:
                            cash_analysis = analyze_cash_levels(historical_data)
                            render_cash_level_analysis(cash_analysis)

                        with analytics_tab2:
                            holding_histories = analyze_holding_periods(historical_data)
                            holding_stats = get_holding_statistics(holding_histories)
                            render_holding_period_analysis(holding_stats, holding_histories)

                        with analytics_tab3:
                            weight_signals = analyze_weight_signals(historical_data)
                            conviction_summary = get_conviction_summary(weight_signals)
                            render_weight_signals(weight_signals, conviction_summary)

                except Exception as e:
                    st.error(f"❌ 分析錯誤: {str(e)}")
                    import traceback
                    with st.expander("錯誤詳情"):
                        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
