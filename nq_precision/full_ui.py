import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from nq_precision.full_data import (
    calculate_sentiment_score,
    exchange_schwab_auth_code,
    generate_daily_bread,
    get_cboe_options,
    get_economic_calendar,
    get_expirations_by_type,
    get_fear_greed_index,
    get_market_overview_yahoo,
    get_nq_intraday_data,
    get_nq_price_auto,
    get_quote_age_label,
    get_qqq_price,
    get_runtime_health,
    get_rss_news,
    get_top_movers,
    process_expiration,
    process_multi_asset,
    schwab_is_configured,
)


def _theme_css(bg_color, card_bg, text_color, accent_color, border_color):
    st.markdown(
        f"""
<style>
    .main {{
        background-color: {bg_color};
    }}
    .stMetric {{
        background-color: {card_bg};
        padding: 15px;
        border-radius: 10px;
        border: 1px solid {border_color};
    }}
    .stMetric label {{
        color: #888;
        font-size: 14px;
    }}
    .stMetric [data-testid="stMetricValue"] {{
        font-size: 28px;
        color: {accent_color};
    }}
    h1 {{
        color: {accent_color};
        font-weight: 700;
    }}
    h2, h3 {{
        color: {text_color};
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 24px;
        background-color: {card_bg};
        padding: 10px;
        border-radius: 10px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent;
        color: #888;
        font-weight: 600;
        padding: 10px 20px;
        border-radius: 5px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {accent_color};
        color: #000;
    }}
    .quick-glance {{
        background: linear-gradient(135deg, {card_bg} 0%, {border_color} 100%);
        padding: 25px;
        border-radius: 15px;
        border: 2px solid {accent_color};
        margin-bottom: 20px;
    }}
    .sentiment-meter {{
        height: 30px;
        background: linear-gradient(90deg, #FF4444 0%, #FFAA00 50%, #44FF44 100%);
        border-radius: 15px;
        position: relative;
    }}
    .sentiment-marker {{
        position: absolute;
        width: 4px;
        height: 40px;
        background: #000;
        top: -5px;
        border-radius: 2px;
    }}
    .keyboard-hint {{
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: {card_bg};
        padding: 10px;
        border-radius: 8px;
        font-size: 12px;
        color: #888;
        border: 1px solid {border_color};
    }}
</style>
""",
        unsafe_allow_html=True,
    )


def _build_level_interactions(nq_data, data_0dte):
    if nq_data is None or nq_data.empty or not data_0dte:
        return None

    levels = {
        "Delta Neutral": data_0dte["dn_nq"],
        "Gamma Flip": data_0dte["g_flip_nq"],
        "Primary Wall": data_0dte["p_wall"],
        "Primary Floor": data_0dte["p_floor"],
    }
    interactions = []
    prev_close = nq_data["Close"].shift(1)
    for name, level in levels.items():
        touches_mask = (nq_data["Low"] <= level) & (nq_data["High"] >= level)
        breaks_above = ((prev_close < level) & (nq_data["Close"] >= level)).sum()
        breaks_below = ((prev_close > level) & (nq_data["Close"] <= level)).sum()
        touches = int(touches_mask.sum())
        rejections = max(0, touches - int(breaks_above) - int(breaks_below))
        interactions.append(
            {
                "Level": name,
                "Price": round(level, 2),
                "Touches": touches,
                "Breaks Up": int(breaks_above),
                "Breaks Down": int(breaks_below),
                "Rejections": int(rejections),
            }
        )
    return pd.DataFrame(interactions)


def run_full_app():
    st.set_page_config(
        page_title="NQ Precision Map", layout="wide", initial_sidebar_state="expanded"
    )

    if "theme" not in st.session_state:
        st.session_state.theme = "dark"

    def toggle_theme():
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

    if st.session_state.theme == "dark":
        bg_color = "#0E1117"
        card_bg = "#1E1E1E"
        text_color = "#FFF"
        accent_color = "#00D9FF"
        border_color = "#333"
    else:
        bg_color = "#FFFFFF"
        card_bg = "#F0F2F6"
        text_color = "#000"
        accent_color = "#0066CC"
        border_color = "#DDD"

    _theme_css(bg_color, card_bg, text_color, accent_color, border_color)

    st.markdown(
        """
<div class="keyboard-hint">
⌨️ Shortcuts: R=Refresh | 1-6=Tabs | T=Theme
</div>
""",
        unsafe_allow_html=True,
    )

    st.title("📊 NQ Precision Map")
    st.markdown("**Multi-Timeframe GEX & Delta Analysis** • Powered by CBOE Data")

    default_key = ""
    try:
        default_key = st.secrets.get("FINNHUB_KEY", "")
    except Exception:
        default_key = ""

    st.sidebar.header("⚙️ Settings")
    finnhub_key = st.sidebar.text_input(
        "Finnhub API Key", value=default_key, type="password"
    )
    if schwab_is_configured():
        st.sidebar.caption("Realtime futures source: Schwab (with Yahoo fallback)")
    else:
        st.sidebar.caption("Realtime futures source: Yahoo Finance")

    with st.sidebar.expander("System Health", expanded=False):
        for check_name, ok, detail in get_runtime_health():
            if ok:
                st.success(f"{check_name}: {detail}")
            else:
                st.warning(f"{check_name}: {detail}")

    with st.sidebar.expander("Schwab OAuth (one-time setup)", expanded=False):
        default_redirect = "https://developer.schwab.com/oauth2-redirect.html"
        try:
            default_redirect = st.secrets.get("SCHWAB_REDIRECT_URI", default_redirect)
        except Exception:
            pass
        redirect_uri = st.text_input("Redirect URI", value=default_redirect, key="schwab_redirect_uri")
        auth_code = st.text_input("Auth Code", value="", key="schwab_auth_code")
        if st.button("Exchange Code for Tokens"):
            token_payload, err = exchange_schwab_auth_code(auth_code, redirect_uri)
            if err:
                st.error(err)
            else:
                refresh_token = token_payload.get("refresh_token", "")
                access_token = token_payload.get("access_token", "")
                st.success("Token exchange succeeded.")
                st.code(
                    "\n".join(
                        [
                            "# Add these to .streamlit/secrets.toml",
                            f'SCHWAB_REFRESH_TOKEN = "{refresh_token}"',
                            f'# Optional short-lived token: SCHWAB_ACCESS_TOKEN = "{access_token}"',
                        ]
                    ),
                    language="toml",
                )

    if st.sidebar.button("🎨 Toggle Theme"):
        toggle_theme()
        st.rerun()

    manual_override = st.sidebar.checkbox("✏️ Manual NQ Override")
    auto_refresh = st.sidebar.checkbox("🔄 Auto-Refresh (60s)", value=True)
    if auto_refresh:
        refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 30, 300, 60)

    if auto_refresh:
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = time.time()

        time_since_refresh = time.time() - st.session_state.last_refresh
        time_until_refresh = max(0, refresh_interval - int(time_since_refresh))

        if time_until_refresh == 0:
            st.session_state.last_refresh = time.time()
            st.rerun()

        st.sidebar.markdown(f"**Next refresh in:** {time_until_refresh}s")
        placeholder = st.sidebar.empty()
        placeholder.progress((refresh_interval - time_until_refresh) / refresh_interval)

    if not finnhub_key:
        st.warning("Enter your Finnhub API key in the sidebar to load data.")
        st.stop()

    with st.spinner("🔄 Loading multi-timeframe data..."):
        qqq_price = get_qqq_price(finnhub_key)
        if not qqq_price:
            st.error("Could not fetch QQQ price")
            st.stop()

        if manual_override:
            nq_now = st.sidebar.number_input(
                "NQ Price",
                min_value=10000.0,
                max_value=50000.0,
                value=24760.0,
                step=0.25,
                format="%.2f",
            )
            nq_source = "Manual"
        else:
            nq_now, nq_source = get_nq_price_auto(finnhub_key)
            if not nq_now:
                nq_now = st.sidebar.number_input(
                    "NQ Price (auto-fetch failed)",
                    min_value=10000.0,
                    max_value=50000.0,
                    value=24760.0,
                    step=0.25,
                    format="%.2f",
                )
                nq_source = "Manual Fallback"

        ratio = nq_now / qqq_price if qqq_price > 0 else 0
        nq_day_change_pct = 0.0
        try:
            nq_hist = yf.Ticker("NQ=F").history(period="1d")
            if not nq_hist.empty:
                nq_prev_close = nq_hist["Open"].iloc[0]
                nq_day_change_pct = (
                    (nq_now - nq_prev_close) / nq_prev_close * 100 if nq_prev_close != 0 else 0
                )
        except Exception:
            nq_day_change_pct = 0.0

        df_raw, cboe_price = get_cboe_options("QQQ")
        if df_raw is None:
            st.error("Failed to fetch options")
            st.stop()

        if qqq_price == 0:
            qqq_price = cboe_price

        exp_0dte, exp_weekly, exp_monthly = get_expirations_by_type(df_raw)

        data_0dte = None
        data_weekly = None
        data_monthly = None

        if exp_0dte:
            data_0dte = process_expiration(df_raw, exp_0dte, qqq_price, ratio, nq_now)

        if exp_weekly and exp_weekly != exp_0dte:
            data_weekly = process_expiration(
                df_raw, exp_weekly, qqq_price, ratio, nq_now
            )

        if exp_monthly and exp_monthly not in [exp_0dte, exp_weekly]:
            data_monthly = process_expiration(
                df_raw, exp_monthly, qqq_price, ratio, nq_now
            )

        market_data = get_market_overview_yahoo()
        vix_level = market_data.get("vix", {}).get("price", 15)
        fg = get_fear_greed_index()
        sentiment_score = calculate_sentiment_score(data_0dte, nq_now, vix_level, fg["score"])

    if data_0dte:
        dn_distance = nq_now - data_0dte["dn_nq"]
        gf_distance = nq_now - data_0dte["g_flip_nq"]
        above_gf = gf_distance > 0

        if above_gf:
            regime = "🔴 NEGATIVE GAMMA"
            regime_desc = "Unstable / Whipsaw Risk"
        else:
            regime = "🟢 POSITIVE GAMMA"
            regime_desc = "Stable / Range-Bound"

        if abs(dn_distance) > 200:
            if dn_distance > 0:
                bias = "⬇️ SHORT BIAS"
                bias_desc = f"Price extended {dn_distance:.0f}pts above Delta Neutral"
            else:
                bias = "⬆️ LONG BIAS"
                bias_desc = f"Price {abs(dn_distance):.0f}pts below Delta Neutral"
        else:
            bias = "⚖️ NEUTRAL"
            bias_desc = "Price near Delta Neutral equilibrium"

        key_level_price = data_0dte["g_flip_nq"] if above_gf else data_0dte["dn_nq"]
        key_level_name = "Gamma Flip" if above_gf else "Delta Neutral"

        st.markdown(
            f"""
    <div class="quick-glance">
        <h2 style="margin-top: 0;">🎯 QUICK GLANCE</h2>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 20px;">
            <div>
                <p style="color: #888; margin: 0; font-size: 14px;">CURRENT PRICE</p>
                <p style="font-size: 32px; margin: 5px 0; color: {accent_color}; font-weight: bold;">{nq_now:.2f}</p>
                <p style="color: #888; margin: 0; font-size: 12px;">{nq_source}</p>
            </div>
            <div>
                <p style="color: #888; margin: 0; font-size: 14px;">REGIME</p>
                <p style="font-size: 24px; margin: 5px 0; font-weight: bold;">{regime}</p>
                <p style="color: #888; margin: 0; font-size: 12px;">{regime_desc}</p>
            </div>
            <div>
                <p style="color: #888; margin: 0; font-size: 14px;">BIAS</p>
                <p style="font-size: 24px; margin: 5px 0; font-weight: bold;">{bias}</p>
                <p style="color: #888; margin: 0; font-size: 12px;">{bias_desc}</p>
            </div>
            <div>
                <p style="color: #888; margin: 0; font-size: 14px;">KEY LEVEL</p>
                <p style="font-size: 24px; margin: 5px 0; font-weight: bold;">{key_level_price:.2f}</p>
                <p style="color: #888; margin: 0; font-size: 12px;">{key_level_name}</p>
            </div>
        </div>
    </div>
    """,
            unsafe_allow_html=True,
        )

        st.markdown("### 📊 Market Sentiment Score")
        col1, col2 = st.columns([3, 1])

        with col1:
            if sentiment_score < 30:
                sentiment_text = "BEARISH"
            elif sentiment_score < 45:
                sentiment_text = "CAUTIOUS BEARISH"
            elif sentiment_score < 55:
                sentiment_text = "NEUTRAL"
            elif sentiment_score < 70:
                sentiment_text = "CAUTIOUS BULLISH"
            else:
                sentiment_text = "BULLISH"

            st.markdown(
                f"""
        <div style="position: relative;">
            <div class="sentiment-meter">
                <div class="sentiment-marker" style="left: {sentiment_score}%;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 12px; color: #888;">
                <span>0 (Bearish)</span>
                <span>50 (Neutral)</span>
                <span>100 (Bullish)</span>
            </div>
        </div>
        """,
                unsafe_allow_html=True,
            )

        with col2:
            st.metric("Score", f"{sentiment_score}/100", sentiment_text)

    st.markdown("---")

    level_interactions_df = None
    if data_0dte:
        st.subheader("📈 NQ Price Action with Key Levels")
        nq_data = get_nq_intraday_data()

        if nq_data is not None and not nq_data.empty:
            fig = go.Figure()

            fig.add_trace(
                go.Candlestick(
                    x=nq_data.index,
                    open=nq_data["Open"],
                    high=nq_data["High"],
                    low=nq_data["Low"],
                    close=nq_data["Close"],
                    name="NQ",
                    increasing_line_color="#44FF44",
                    decreasing_line_color="#FF4444",
                )
            )

            levels_to_plot = [
                (data_0dte["dn_nq"], "Delta Neutral", "#FFD700", "dot"),
                (data_0dte["g_flip_nq"], "Gamma Flip", "#FF00FF", "dash"),
                (data_0dte["p_wall"], "Primary Wall", "#FF4444", "solid"),
                (data_0dte["p_floor"], "Primary Floor", "#44FF44", "solid"),
            ]

            for level_price, level_name, color, dash in levels_to_plot:
                fig.add_hline(
                    y=level_price,
                    line_dash=dash,
                    line_color=color,
                    annotation_text=f"{level_name}: {level_price:.2f}",
                    annotation_position="right",
                )

            if data_0dte["g_flip_nq"] < nq_data["High"].max():
                fig.add_hrect(
                    y0=data_0dte["g_flip_nq"],
                    y1=nq_data["High"].max(),
                    fillcolor="red",
                    opacity=0.1,
                    annotation_text="Negative Gamma Zone",
                    annotation_position="top right",
                )

            if data_0dte["g_flip_nq"] > nq_data["Low"].min():
                fig.add_hrect(
                    y0=nq_data["Low"].min(),
                    y1=data_0dte["g_flip_nq"],
                    fillcolor="green",
                    opacity=0.1,
                    annotation_text="Positive Gamma Zone",
                    annotation_position="bottom right",
                )

            fig.update_layout(
                template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white",
                height=500,
                xaxis_title="Time (5-min candles)",
                yaxis_title="NQ Price",
                showlegend=False,
                hovermode="x unified",
            )

            fig.update_xaxes(rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            level_interactions_df = _build_level_interactions(nq_data, data_0dte)
        else:
            st.info("📊 Intraday chart data unavailable - check back during market hours")

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    col1.metric("NQ Price", f"{nq_now:.2f}", f"↑ {nq_source}")
    col2.metric("QQQ Price", f"${qqq_price:.2f}")
    col3.metric("Ratio", f"{ratio:.4f}")

    if data_0dte and data_weekly:
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("⚖️ Delta Neutral (0DTE)", f"{data_0dte['dn_nq']:.2f}")
        col2.metric("⚖️ Delta Neutral (Weekly)", f"{data_weekly['dn_nq']:.2f}")
        col3.metric("⚡ Gamma Flip (0DTE)", f"{data_0dte['g_flip_nq']:.2f}")
        col4.metric("⚡ Gamma Flip (Weekly)", f"{data_weekly['g_flip_nq']:.2f}")
        delta_0 = "🟢 Bullish" if data_0dte["net_delta"] > 0 else "🔴 Bearish"
        delta_w = "🟢 Bullish" if data_weekly["net_delta"] > 0 else "🔴 Bearish"
        col5.metric("📊 Net Delta (0DTE)", f"{data_0dte['net_delta']:,.0f}", delta_0)
        col6.metric("📊 Net Delta (Weekly)", f"{data_weekly['net_delta']:,.0f}", delta_w)
    elif data_0dte:
        col1, col2, col3 = st.columns(3)
        col1.metric("⚖️ Delta Neutral", f"{data_0dte['dn_nq']:.2f}")
        col2.metric("⚡ Gamma Flip", f"{data_0dte['g_flip_nq']:.2f}")
        delta_sentiment = "🟢 Bullish" if data_0dte["net_delta"] > 0 else "🔴 Bearish"
        col3.metric("📊 Net Delta", f"{data_0dte['net_delta']:,.0f}", delta_sentiment)

    st.markdown("---")
    st.subheader("🎯 Multi-Timeframe Key Levels")

    overview_data = []

    if data_0dte:
        days = (exp_0dte.date() - datetime.now().date()).days
        label = "0DTE" if days == 0 else f"{days}DTE"
        overview_data.append(
            {
                "Timeframe": label,
                "Expiration": exp_0dte.strftime("%Y-%m-%d"),
                "Delta Neutral": data_0dte["dn_nq"],
                "Gamma Flip": data_0dte["g_flip_nq"],
                "Primary Wall": data_0dte["p_wall"],
                "Primary Floor": data_0dte["p_floor"],
                "Net Delta": data_0dte["net_delta"],
            }
        )

    if data_weekly:
        days = (exp_weekly.date() - datetime.now().date()).days
        label = f"Weekly ({days}D)"
        overview_data.append(
            {
                "Timeframe": label,
                "Expiration": exp_weekly.strftime("%Y-%m-%d"),
                "Delta Neutral": data_weekly["dn_nq"],
                "Gamma Flip": data_weekly["g_flip_nq"],
                "Primary Wall": data_weekly["p_wall"],
                "Primary Floor": data_weekly["p_floor"],
                "Net Delta": data_weekly["net_delta"],
            }
        )

    if data_monthly:
        days = (exp_monthly.date() - datetime.now().date()).days
        label = f"Monthly ({days}D)"
        overview_data.append(
            {
                "Timeframe": label,
                "Expiration": exp_monthly.strftime("%Y-%m-%d"),
                "Delta Neutral": data_monthly["dn_nq"],
                "Gamma Flip": data_monthly["g_flip_nq"],
                "Primary Wall": data_monthly["p_wall"],
                "Primary Floor": data_monthly["p_floor"],
                "Net Delta": data_monthly["net_delta"],
            }
        )

    if overview_data:
        overview_df = pd.DataFrame(overview_data)
        st.dataframe(
            overview_df.style.format(
                {
                    "Delta Neutral": "{:.2f}",
                    "Gamma Flip": "{:.2f}",
                    "Primary Wall": "{:.2f}",
                    "Primary Floor": "{:.2f}",
                    "Net Delta": "{:,.0f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    st.markdown("---")

    tab_names = ["📈 Market Overview"]
    if data_0dte:
        tab_names.append("📊 0DTE Levels")
    if data_weekly:
        tab_names.append("📊 Weekly Levels")
    if data_monthly:
        tab_names.append("📊 Monthly Levels")
    tab_names.extend(["🍞 Daily Bread", "📈 GEX Charts", "⚖️ Delta Charts"])
    tab_names.insert(1, "🌐 Multi-Asset")

    if tab_names:
        tabs = st.tabs(tab_names)
        tab_idx = 0

        with tabs[tab_idx]:
            st.subheader("📈 Market Overview")
            with st.spinner("Loading market data..."):
                if market_data:
                    st.markdown("### Futures & Indices")
                    col1, col2, col3, col4, col5 = st.columns(5)

                    if "es" in market_data and market_data["es"]["price"]:
                        es = market_data["es"]
                        col1.metric(
                            "S&P 500 (ES)",
                            f"{es['price']:.2f}",
                            f"{es.get('change', 0):+.2f} ({es.get('change_pct', 0):+.2f}%)",
                        )
                        col1.caption(
                            f"Source: {es.get('source', 'unknown')} | Age: {get_quote_age_label('ES=F')}"
                        )
                    else:
                        col1.metric("S&P 500 (ES)", "N/A")

                    nq_change = nq_now * (nq_day_change_pct / 100)
                    col2.metric(
                        "Nasdaq (NQ)",
                        f"{nq_now:.2f}",
                        f"{nq_change:+.2f} ({nq_day_change_pct:+.2f}%)",
                    )
                    col2.caption(f"Source: {nq_source} | Age: {get_quote_age_label('NQ=F')}")

                    if "ym" in market_data and market_data["ym"]["price"]:
                        ym = market_data["ym"]
                        col3.metric(
                            "Dow (YM)",
                            f"{ym['price']:.2f}",
                            f"{ym.get('change', 0):+.2f} ({ym.get('change_pct', 0):+.2f}%)",
                        )
                        col3.caption(
                            f"Source: {ym.get('source', 'unknown')} | Age: {get_quote_age_label('YM=F')}"
                        )
                    else:
                        col3.metric("Dow (YM)", "N/A")

                    if "rty" in market_data and market_data["rty"]["price"]:
                        rty = market_data["rty"]
                        col4.metric(
                            "Russell (RTY)",
                            f"{rty['price']:.2f}",
                            f"{rty.get('change', 0):+.2f} ({rty.get('change_pct', 0):+.2f}%)",
                        )
                        col4.caption(
                            f"Source: {rty.get('source', 'unknown')} | Age: {get_quote_age_label('RTY=F')}"
                        )
                    else:
                        col4.metric("Russell (RTY)", "N/A")

                    if "gc" in market_data and market_data["gc"]["price"]:
                        gc = market_data["gc"]
                        col5.metric(
                            "Gold (GC)",
                            f"{gc['price']:.2f}",
                            f"{gc.get('change', 0):+.2f} ({gc.get('change_pct', 0):+.2f}%)",
                        )
                        col5.caption(
                            f"Source: {gc.get('source', 'unknown')} | Age: {get_quote_age_label('GC=F')}"
                        )
                    else:
                        col5.metric("Gold (GC)", "N/A")

                    st.markdown("---")
                    st.markdown("### Market Indicators")
                    col1, col2, col3 = st.columns(3)

                    if "vix" in market_data and market_data["vix"]["price"]:
                        vix = market_data["vix"]
                        col1.metric(
                            "VIX (Volatility)",
                            f"{vix['price']:.2f}",
                            f"{vix.get('change', 0):+.2f} ({vix.get('change_pct', 0):+.2f}%)",
                        )
                    else:
                        col1.metric("VIX (Volatility)", "N/A")

                    if "10y" in market_data and market_data["10y"]["price"]:
                        tnx = market_data["10y"]
                        col2.metric(
                            "10Y Treasury",
                            f"{tnx['price']:.2f}%",
                            f"{tnx.get('change', 0):+.2f}",
                        )
                    else:
                        col2.metric("10Y Treasury", "N/A")

                    if "dxy" in market_data and market_data["dxy"]["price"]:
                        dxy = market_data["dxy"]
                        col3.metric(
                            "Dollar Index",
                            f"{dxy['price']:.2f}",
                            f"{dxy.get('change', 0):+.2f} ({dxy.get('change_pct', 0):+.2f}%)",
                        )
                        col3.caption(
                            f"Source: {dxy.get('source', 'unknown')} | Age: {get_quote_age_label('DX=F')}"
                        )
                    else:
                        col3.metric("Dollar Index", "N/A")
                else:
                    st.warning("Market data temporarily unavailable")

            st.markdown("---")
            st.markdown("### Market Sentiment")

            col1, col2 = st.columns([1, 3])
            with col1:
                st.metric("Fear & Greed Index", f"{fg['score']:.0f}", fg["rating"])

            with col2:
                if data_0dte:
                    gf_distance = nq_now - data_0dte["g_flip_nq"]
                    dn_distance = nq_now - data_0dte["dn_nq"]
                    gamma_state = "Negative Gamma" if gf_distance > 0 else "Positive Gamma"
                    regime_text = (
                        f"Regime: **{gamma_state}** | "
                        f"NQ vs Gamma Flip: {gf_distance:+.0f} pts | "
                        f"NQ vs Delta Neutral: {dn_distance:+.0f} pts"
                    )
                    if gf_distance > 0:
                        st.warning(regime_text)
                    else:
                        st.success(regime_text)
                else:
                    st.info("Regime: unavailable (no 0DTE data)")

                vix = market_data.get("vix", {}).get("price", 0)
                dxy_chg = market_data.get("dxy", {}).get("change_pct", 0)
                tnx_chg = market_data.get("10y", {}).get("change", 0)
                risk_score = 0
                if vix >= 20:
                    risk_score += 2
                elif vix >= 16:
                    risk_score += 1
                if dxy_chg > 0.3:
                    risk_score += 1
                if tnx_chg > 0.05:
                    risk_score += 1
                risk_label = "High Risk" if risk_score >= 3 else "Moderate Risk" if risk_score >= 2 else "Low Risk"
                risk_text = (
                    f"Risk Meter: **{risk_label}** | "
                    f"VIX {vix:.2f} | DXY {dxy_chg:+.2f}% | 10Y {tnx_chg:+.2f}"
                )
                if risk_score >= 3:
                    st.error(risk_text)
                elif risk_score >= 2:
                    st.warning(risk_text)
                else:
                    st.info(risk_text)

                es_chg = market_data.get("es", {}).get("change_pct", 0)
                ym_chg = market_data.get("ym", {}).get("change_pct", 0)
                rty_chg = market_data.get("rty", {}).get("change_pct", 0)
                divergence_score = (
                    abs(nq_day_change_pct - es_chg)
                    + abs(nq_day_change_pct - ym_chg)
                    + abs(nq_day_change_pct - rty_chg)
                ) / 3
                divergence_text = (
                    f"Cross-Asset Divergence: **{divergence_score:.2f}%** | "
                    f"NQ {nq_day_change_pct:+.2f}% vs ES {es_chg:+.2f}% / YM {ym_chg:+.2f}% / RTY {rty_chg:+.2f}%"
                )
                if divergence_score >= 1.0:
                    st.warning(divergence_text)
                else:
                    st.info(divergence_text)

                if data_0dte:
                    long_trigger = data_0dte["p_floor"]
                    short_trigger = data_0dte["p_wall"]
                    trigger_text = (
                        f"Action Triggers: Long reaction zone near **{long_trigger:.2f}** | "
                        f"Short reaction zone near **{short_trigger:.2f}** | "
                        f"Regime pivot at **{data_0dte['g_flip_nq']:.2f}**"
                    )
                    st.info(trigger_text)
                else:
                    st.info("Action Triggers: unavailable (waiting for options levels)")

            st.markdown("---")
            st.markdown("### 🧭 Level Interaction Panel")
            if level_interactions_df is not None and not level_interactions_df.empty:
                st.dataframe(level_interactions_df, width="stretch", hide_index=True)
            else:
                st.info("Level interaction data unavailable (requires intraday candles).")

            st.markdown("---")
            st.markdown("### Top Movers")
            movers = get_top_movers(finnhub_key)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🟢 Top Gainers**")
                if movers["gainers"]:
                    gainers_df = pd.DataFrame(movers["gainers"])
                    st.dataframe(
                        gainers_df[["symbol", "price", "change_pct"]].style.format(
                            {"price": "${:.2f}", "change_pct": "{:+.2f}%"}
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("No data available")

            with col2:
                st.markdown("**🔴 Top Losers**")
                if movers["losers"]:
                    losers_df = pd.DataFrame(movers["losers"])
                    st.dataframe(
                        losers_df[["symbol", "price", "change_pct"]].style.format(
                            {"price": "${:.2f}", "change_pct": "{:+.2f}%"}
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("No data available")

            st.markdown("---")
            st.markdown("### 📅 Today's Economic Events")
            events = get_economic_calendar(finnhub_key)

            if events:
                events_data = []
                for event in events:
                    time_str = event.get("time", "")[:10] if event.get("time") else "N/A"
                    events_data.append(
                        {
                            "Time": time_str,
                            "Event": event.get("event", "Unknown"),
                            "Impact": event.get("impact", "N/A"),
                            "Country": event.get("country", "US"),
                        }
                    )

                events_df = pd.DataFrame(events_data)
                st.dataframe(events_df, width="stretch", hide_index=True)
            else:
                st.info("No major economic events today")

            st.markdown("---")
            st.markdown("### 📰 Latest Market News (Live RSS)")
            rss_news = get_rss_news()

            if rss_news:
                for article in rss_news[:8]:
                    with st.expander(f"**{article['headline']}** - {article['source']}"):
                        if article.get("summary"):
                            st.markdown(f"*{article['summary']}...*")
                        st.markdown(f"[Read full article]({article['link']})")
                        if article.get("published"):
                            st.caption(f"Published: {article['published']}")
            else:
                st.info("News feed temporarily unavailable")

        tab_idx += 1

        with tabs[tab_idx]:
            st.subheader("🌐 Multi-Asset Comparison Dashboard")
            st.caption("Compare GEX levels across all major indices")

            with st.spinner("Loading multi-asset data..."):
                multi_asset_data = process_multi_asset()

            if multi_asset_data:
                st.markdown("### 📊 Cross-Asset Key Levels Comparison")
                comparison_data = []

                for asset_name in ["SPY", "QQQ", "IWM", "DIA"]:
                    if asset_name not in multi_asset_data:
                        continue

                    asset = multi_asset_data[asset_name]
                    data_0 = asset.get("data_0dte")

                    if data_0:
                        futures_price = asset["futures_price"]
                        dn_distance = futures_price - data_0["dn_nq"]
                        gf_distance = futures_price - data_0["g_flip_nq"]

                        regime = "🔴 Negative" if gf_distance > 0 else "🟢 Positive"

                        if abs(dn_distance) > (futures_price * 0.008):
                            bias = "⬇️ Short" if dn_distance > 0 else "⬆️ Long"
                        else:
                            bias = "⚖️ Neutral"

                        comparison_data.append(
                            {
                                "Index": f"{asset['name']} ({asset_name})",
                                "Futures Price": f"{futures_price:,.2f}",
                                "Delta Neutral": f"{data_0['dn_nq']:,.2f}",
                                "DN Distance": f"{dn_distance:+.0f}",
                                "Gamma Flip": f"{data_0['g_flip_nq']:,.2f}",
                                "Regime": regime,
                                "Bias": bias,
                                "Net Delta": f"{data_0['net_delta']:,.0f}",
                            }
                        )

                if comparison_data:
                    st.dataframe(
                        pd.DataFrame(comparison_data), width="stretch", hide_index=True
                    )

                st.markdown("---")
                st.markdown("### 📈 Individual Asset Details")
                cols = st.columns(2)

                for idx, asset_name in enumerate(["SPY", "QQQ", "IWM", "DIA"]):
                    if asset_name not in multi_asset_data:
                        continue

                    asset = multi_asset_data[asset_name]
                    data_0 = asset.get("data_0dte")

                    with cols[idx % 2]:
                        st.markdown(f"#### {asset['name']} ({asset_name})")

                        if data_0:
                            c1, c2, c3 = st.columns(3)

                            c1.metric(
                                "Futures Price",
                                f"{asset['futures_price']:,.2f}",
                                f"Ratio: {asset['ratio']:.4f}",
                            )
                            c2.metric(
                                "Delta Neutral",
                                f"{data_0['dn_nq']:,.2f}",
                                f"{asset['futures_price'] - data_0['dn_nq']:+.0f} pts",
                            )
                            c3.metric(
                                "Gamma Flip",
                                f"{data_0['g_flip_nq']:,.2f}",
                                "🟢 Pos"
                                if asset["futures_price"] < data_0["g_flip_nq"]
                                else "🔴 Neg",
                            )

                            levels_data = {
                                "Level": [
                                    "Primary Wall",
                                    "Primary Floor",
                                    "Expected Move",
                                ],
                                "Price": [
                                    f"{data_0['p_wall']:,.2f}",
                                    f"{data_0['p_floor']:,.2f}",
                                    f"±{data_0['nq_em_full']:,.0f}",
                                ],
                            }

                            st.dataframe(
                                pd.DataFrame(levels_data), hide_index=True, width="stretch"
                            )
                        else:
                            st.info(f"No 0DTE data available for {asset_name}")

            else:
                st.error("Could not load multi-asset data")

        tab_idx += 1

        if data_0dte:
            with tabs[tab_idx]:
                st.subheader(f"0DTE Analysis - {exp_0dte.strftime('%Y-%m-%d')}")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Delta Neutral", f"{data_0dte['dn_nq']:.2f}")
                col2.metric("Gamma Flip", f"{data_0dte['g_flip_nq']:.2f}")
                col3.metric(
                    "Net Delta",
                    f"{data_0dte['net_delta']:,.0f}",
                    "🟢 Bull" if data_0dte["net_delta"] > 0 else "🔴 Bear",
                )
                col4.metric("Expected Move", f"±{data_0dte['nq_em_full']:.0f}")

                results_df = pd.DataFrame(
                    data_0dte["results"], columns=["Level", "Price", "Width", "Icon"]
                )
                results_df["Price"] = results_df["Price"].round(2)
                st.dataframe(
                    results_df[["Icon", "Level", "Price", "Width"]].style.format(
                        {"Price": "{:.2f}", "Width": "{:.1f}"}
                    ),
                    width="stretch",
                    height=500,
                    hide_index=True,
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**🔴 Top Call Strikes**")
                    st.dataframe(
                        data_0dte["calls"][
                            ["strike", "GEX", "delta", "open_interest", "volume"]
                        ].head(5),
                        width="stretch",
                        hide_index=True,
                    )
                with col2:
                    st.markdown("**🟢 Top Put Strikes**")
                    st.dataframe(
                        data_0dte["puts"][
                            ["strike", "GEX", "delta", "open_interest", "volume"]
                        ].head(5),
                        width="stretch",
                        hide_index=True,
                    )
            tab_idx += 1

        if data_weekly:
            with tabs[tab_idx]:
                st.subheader(f"Weekly Analysis - {exp_weekly.strftime('%Y-%m-%d')}")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Delta Neutral", f"{data_weekly['dn_nq']:.2f}")
                col2.metric("Gamma Flip", f"{data_weekly['g_flip_nq']:.2f}")
                col3.metric(
                    "Net Delta",
                    f"{data_weekly['net_delta']:,.0f}",
                    "🟢 Bull" if data_weekly["net_delta"] > 0 else "🔴 Bear",
                )
                col4.metric("Expected Move", f"±{data_weekly['nq_em_full']:.0f}")

                results_df = pd.DataFrame(
                    data_weekly["results"], columns=["Level", "Price", "Width", "Icon"]
                )
                results_df["Price"] = results_df["Price"].round(2)
                st.dataframe(
                    results_df[["Icon", "Level", "Price", "Width"]].style.format(
                        {"Price": "{:.2f}", "Width": "{:.1f}"}
                    ),
                    width="stretch",
                    height=500,
                    hide_index=True,
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**🔴 Top Call Strikes**")
                    st.dataframe(
                        data_weekly["calls"][
                            ["strike", "GEX", "delta", "open_interest", "volume"]
                        ].head(5),
                        width="stretch",
                        hide_index=True,
                    )
                with col2:
                    st.markdown("**🟢 Top Put Strikes**")
                    st.dataframe(
                        data_weekly["puts"][
                            ["strike", "GEX", "delta", "open_interest", "volume"]
                        ].head(5),
                        width="stretch",
                        hide_index=True,
                    )
            tab_idx += 1

        if data_monthly:
            with tabs[tab_idx]:
                st.subheader(f"Monthly Analysis - {exp_monthly.strftime('%Y-%m-%d')}")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Delta Neutral", f"{data_monthly['dn_nq']:.2f}")
                col2.metric("Gamma Flip", f"{data_monthly['g_flip_nq']:.2f}")
                col3.metric(
                    "Net Delta",
                    f"{data_monthly['net_delta']:,.0f}",
                    "🟢 Bull" if data_monthly["net_delta"] > 0 else "🔴 Bear",
                )
                col4.metric("Expected Move", f"±{data_monthly['nq_em_full']:.0f}")

                results_df = pd.DataFrame(
                    data_monthly["results"], columns=["Level", "Price", "Width", "Icon"]
                )
                results_df["Price"] = results_df["Price"].round(2)
                st.dataframe(
                    results_df[["Icon", "Level", "Price", "Width"]].style.format(
                        {"Price": "{:.2f}", "Width": "{:.1f}"}
                    ),
                    width="stretch",
                    height=500,
                    hide_index=True,
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**🔴 Top Call Strikes**")
                    st.dataframe(
                        data_monthly["calls"][
                            ["strike", "GEX", "delta", "open_interest", "volume"]
                        ].head(5),
                        width="stretch",
                        hide_index=True,
                    )
                with col2:
                    st.markdown("**🟢 Top Put Strikes**")
                    st.dataframe(
                        data_monthly["puts"][
                            ["strike", "GEX", "delta", "open_interest", "volume"]
                        ].head(5),
                        width="stretch",
                        hide_index=True,
                    )
            tab_idx += 1

        with tabs[tab_idx]:
            st.markdown("# 🍞 DAILY BREAD")
            st.markdown(
                f"**Your NQ Market Intelligence Report** • {datetime.now().strftime('%A, %B %d, %Y')}"
            )

            if data_0dte:
                events = get_economic_calendar(finnhub_key)
                news = get_rss_news()
                daily_bread = generate_daily_bread(
                    data_0dte,
                    data_weekly,
                    nq_now,
                    market_data,
                    fg,
                    events,
                    news,
                )

                st.markdown(f"**{daily_bread.get('session', '')}**")
                st.caption(daily_bread.get("timestamp", ""))
                st.markdown("---")

                tone = daily_bread.get("tone", "NEUTRAL")
                if tone == "BEARISH":
                    st.error(daily_bread.get("summary", ""))
                elif tone == "RANGE-BOUND":
                    st.success(daily_bread.get("summary", ""))
                else:
                    st.info(daily_bread.get("summary", ""))

                with st.expander("📊 Key Levels", expanded=False):
                    st.markdown(daily_bread.get("levels", ""))

                with st.expander("📈 Market Drivers", expanded=False):
                    st.markdown(daily_bread.get("drivers", ""))

                with st.expander("💼 Trading Strategy", expanded=False):
                    st.markdown(daily_bread.get("strategy", ""))

                with st.expander("🔮 Tomorrow's Watch List", expanded=False):
                    st.markdown(daily_bread.get("watch_list", ""))
            else:
                st.info("No 0DTE data available for Daily Bread analysis")

            st.markdown("---")
            st.caption(
                "⚠️ Daily Bread is generated from live options market data and should not be considered financial advice. Always manage risk appropriately."
            )

        tab_idx += 1

        with tabs[tab_idx]:
            st.subheader("📈 GEX by Strike - All Timeframes")

            if data_0dte:
                st.markdown("**0DTE**")
                gex_by_strike = data_0dte["df"].groupby("strike")["GEX"].sum().reset_index()
                fig = go.Figure()
                pos_gex = gex_by_strike[gex_by_strike["GEX"] > 0]
                neg_gex = gex_by_strike[gex_by_strike["GEX"] < 0]
                fig.add_trace(
                    go.Bar(
                        x=pos_gex["strike"],
                        y=pos_gex["GEX"],
                        name="Calls",
                        marker_color="#FF4444",
                    )
                )
                fig.add_trace(
                    go.Bar(
                        x=neg_gex["strike"],
                        y=neg_gex["GEX"],
                        name="Puts",
                        marker_color="#44FF44",
                    )
                )
                fig.add_vline(
                    x=qqq_price,
                    line_dash="dash",
                    line_color="#00D9FF",
                    annotation_text="Current",
                )
                fig.update_layout(
                    template="plotly_dark"
                    if st.session_state.theme == "dark"
                    else "plotly_white",
                    plot_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    paper_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    height=400,
                    showlegend=True,
                )
                st.plotly_chart(fig, use_container_width=True)

            if data_weekly:
                st.markdown("**Weekly**")
                gex_by_strike = data_weekly["df"].groupby("strike")["GEX"].sum().reset_index()
                fig = go.Figure()
                pos_gex = gex_by_strike[gex_by_strike["GEX"] > 0]
                neg_gex = gex_by_strike[gex_by_strike["GEX"] < 0]
                fig.add_trace(
                    go.Bar(
                        x=pos_gex["strike"],
                        y=pos_gex["GEX"],
                        name="Calls",
                        marker_color="#FF4444",
                    )
                )
                fig.add_trace(
                    go.Bar(
                        x=neg_gex["strike"],
                        y=neg_gex["GEX"],
                        name="Puts",
                        marker_color="#44FF44",
                    )
                )
                fig.add_vline(
                    x=qqq_price,
                    line_dash="dash",
                    line_color="#00D9FF",
                    annotation_text="Current",
                )
                fig.update_layout(
                    template="plotly_dark"
                    if st.session_state.theme == "dark"
                    else "plotly_white",
                    plot_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    paper_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    height=400,
                    showlegend=True,
                )
                st.plotly_chart(fig, use_container_width=True)

            if data_monthly:
                st.markdown("**Monthly**")
                gex_by_strike = (
                    data_monthly["df"].groupby("strike")["GEX"].sum().reset_index()
                )
                fig = go.Figure()
                pos_gex = gex_by_strike[gex_by_strike["GEX"] > 0]
                neg_gex = gex_by_strike[gex_by_strike["GEX"] < 0]
                fig.add_trace(
                    go.Bar(
                        x=pos_gex["strike"],
                        y=pos_gex["GEX"],
                        name="Calls",
                        marker_color="#FF4444",
                    )
                )
                fig.add_trace(
                    go.Bar(
                        x=neg_gex["strike"],
                        y=neg_gex["GEX"],
                        name="Puts",
                        marker_color="#44FF44",
                    )
                )
                fig.add_vline(
                    x=qqq_price,
                    line_dash="dash",
                    line_color="#00D9FF",
                    annotation_text="Current",
                )
                fig.update_layout(
                    template="plotly_dark"
                    if st.session_state.theme == "dark"
                    else "plotly_white",
                    plot_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    paper_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    height=400,
                    showlegend=True,
                )
                st.plotly_chart(fig, use_container_width=True)

        tab_idx += 1

        with tabs[tab_idx]:
            st.subheader("⚖️ Cumulative Delta - All Timeframes")

            if data_0dte:
                st.markdown("**0DTE**")
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=data_0dte["strike_delta"]["strike"],
                        y=data_0dte["strike_delta"]["cumulative_delta"],
                        mode="lines",
                        name="Cumulative Delta",
                        line=dict(color="#00D9FF", width=3),
                        fill="tozeroy",
                    )
                )
                fig.add_hline(y=0, line_dash="dash", line_color="white")
                fig.add_vline(
                    x=data_0dte["dn_strike"],
                    line_dash="dot",
                    line_color="#FFD700",
                    annotation_text="Delta Neutral",
                )
                fig.add_vline(
                    x=qqq_price,
                    line_dash="dash",
                    line_color="#FF4444",
                    annotation_text="Current",
                )
                fig.update_layout(
                    template="plotly_dark"
                    if st.session_state.theme == "dark"
                    else "plotly_white",
                    plot_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    paper_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    height=400,
                )
                st.plotly_chart(fig, use_container_width=True)

            if data_weekly:
                st.markdown("**Weekly**")
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=data_weekly["strike_delta"]["strike"],
                        y=data_weekly["strike_delta"]["cumulative_delta"],
                        mode="lines",
                        name="Cumulative Delta",
                        line=dict(color="#00D9FF", width=3),
                        fill="tozeroy",
                    )
                )
                fig.add_hline(y=0, line_dash="dash", line_color="white")
                fig.add_vline(
                    x=data_weekly["dn_strike"],
                    line_dash="dot",
                    line_color="#FFD700",
                    annotation_text="Delta Neutral",
                )
                fig.add_vline(
                    x=qqq_price,
                    line_dash="dash",
                    line_color="#FF4444",
                    annotation_text="Current",
                )
                fig.update_layout(
                    template="plotly_dark"
                    if st.session_state.theme == "dark"
                    else "plotly_white",
                    plot_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    paper_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    height=400,
                )
                st.plotly_chart(fig, use_container_width=True)

            if data_monthly:
                st.markdown("**Monthly**")
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=data_monthly["strike_delta"]["strike"],
                        y=data_monthly["strike_delta"]["cumulative_delta"],
                        mode="lines",
                        name="Cumulative Delta",
                        line=dict(color="#00D9FF", width=3),
                        fill="tozeroy",
                    )
                )
                fig.add_hline(y=0, line_dash="dash", line_color="white")
                fig.add_vline(
                    x=data_monthly["dn_strike"],
                    line_dash="dot",
                    line_color="#FFD700",
                    annotation_text="Delta Neutral",
                )
                fig.add_vline(
                    x=qqq_price,
                    line_dash="dash",
                    line_color="#FF4444",
                    annotation_text="Current",
                )
                fig.update_layout(
                    template="plotly_dark"
                    if st.session_state.theme == "dark"
                    else "plotly_white",
                    plot_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    paper_bgcolor="#0E1117"
                    if st.session_state.theme == "dark"
                    else "#FFFFFF",
                    height=400,
                )
                st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')} | CBOE • {nq_source}")

    if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
        st.session_state.last_refresh = time.time()
        st.cache_data.clear()
        st.rerun()
