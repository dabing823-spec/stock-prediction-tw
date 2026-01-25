"""
台股 ETF 戰情室 - 主程式
"""
from datetime import datetime

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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🇹🇼 0050 權值",
        "🌍 MSCI 外資",
        "💰 0056 高股息",
        "📊 全市場權重",
        "⚡ 電子 Alpha 對沖"
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


if __name__ == "__main__":
    main()
