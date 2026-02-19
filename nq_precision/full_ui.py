import time
from datetime import datetime
import html

import pandas as pd
import plotly.express as px
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
    get_nasdaq_heatmap_data,
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
    .stApp {{
        background: radial-gradient(circle at 20% -20%, #171b22 0%, {bg_color} 38%, #090d14 100%);
        color: {text_color};
    }}
    section.main > div {{
        padding-top: 0.5rem;
    }}
    h1 {{
        color: #f2f5fb;
        font-weight: 800;
        letter-spacing: 0.2px;
        margin-bottom: 0.2rem;
    }}
    h2, h3 {{
        color: #e9edf5;
    }}
    [data-testid="stHorizontalBlock"] {{
        gap: 0.55rem !important;
    }}
    .terminal-shell {{
        background: linear-gradient(180deg, #151a23 0%, #10151d 100%);
        border: 1px solid #2f3540;
        border-radius: 8px;
        box-shadow: 0 8px 26px rgba(0, 0, 0, 0.35);
        overflow: hidden;
        margin-bottom: 10px;
    }}
    .terminal-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        padding: 7px 10px;
        background: linear-gradient(180deg, #222933 0%, #1a2029 100%);
        border-bottom: 1px solid #313946;
        color: #d6dbe4;
        font-size: 12px;
        letter-spacing: 0.25px;
        text-transform: uppercase;
        font-weight: 700;
    }}
    .terminal-title {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .toolbar-dots {{
        color: #aeb8c6;
        letter-spacing: 0.5px;
        font-size: 11px;
        opacity: 0.9;
    }}
    .terminal-body {{
        padding: 10px;
    }}
    .futures-strip {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 10px;
        margin-bottom: 10px;
    }}
    .future-card {{
        border: 1px solid #2f3d53;
        border-radius: 12px;
        padding: 12px 14px;
        background: linear-gradient(100deg, #1a212d 0%, #121a24 100%);
        min-height: 112px;
    }}
    .future-title {{
        color: #9aa8bc;
        font-size: 13px;
        line-height: 1.1;
        margin: 0;
        font-weight: 700;
    }}
    .future-value {{
        color: #3ad7ff;
        font-size: 40px;
        line-height: 1.15;
        margin: 7px 0 9px 0;
        font-weight: 800;
        letter-spacing: 0.2px;
    }}
    .future-badge {{
        display: inline-block;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 14px;
        font-weight: 700;
    }}
    .future-badge.pos {{
        background: rgba(33, 166, 95, 0.25);
        color: #54f09b;
        border: 1px solid #2b8b5b;
    }}
    .future-badge.neg {{
        background: rgba(191, 61, 61, 0.25);
        color: #ff7676;
        border: 1px solid #8b3e3e;
    }}
    .left-nav-shell {{
        background: linear-gradient(180deg, #161c25 0%, #10161f 100%);
        border: 1px solid #2d3641;
        border-radius: 8px;
        padding: 10px 8px;
    }}
    .left-nav-title {{
        font-size: 11px;
        color: #97a3b5;
        letter-spacing: 0.35px;
        text-transform: uppercase;
        font-weight: 700;
        margin-bottom: 10px;
    }}
    .left-nav-section {{
        font-size: 10px;
        color: #7f8ba0;
        letter-spacing: 0.25px;
        text-transform: uppercase;
        font-weight: 700;
        margin: 10px 4px 5px 4px;
    }}
    .left-nav-shell .stButton > button {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        color: #b8c2d2;
        text-align: left;
        justify-content: flex-start;
        font-weight: 600;
        font-size: 15px;
        padding: 8px 10px;
        min-height: 40px;
    }}
    .left-nav-shell .stButton > button:hover {{
        border-color: #2f3946;
        background: #18202c;
        color: #f1f5fb;
    }}
    .nav-item {{
        border: 1px solid transparent;
        border-radius: 10px;
        color: #b8c2d2;
        font-weight: 600;
        font-size: 15px;
        padding: 8px 10px;
        min-height: 40px;
        display: flex;
        align-items: center;
    }}
    .nav-item.active {{
        border-color: #2f3946;
        background: linear-gradient(180deg, #2a3240 0%, #1f2733 100%);
        color: #f1f5fb;
        box-shadow: inset 0 0 0 1px #394657;
    }}
    .stMetric {{
        background: linear-gradient(180deg, #1a1f26 0%, #141920 100%);
        border: 1px solid #2f3643;
        border-radius: 8px;
        padding: 6px 9px;
        min-height: 88px;
    }}
    .stMetric label {{
        color: #8a96a8;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.2px;
    }}
    .stMetric [data-testid="stMetricValue"] {{
        color: #29dbff;
        font-size: 25px;
        line-height: 1.1;
    }}
    .metric-chip {{
        display: inline-block;
        padding: 1px 8px;
        border-radius: 999px;
        border: 1px solid #2d6940;
        background: #1a4d2f;
        color: #57f59b;
        font-size: 11px;
        margin-top: 6px;
        font-weight: 600;
    }}
    .quick-glance {{
        background: linear-gradient(180deg, #1a1f28 0%, #131821 100%);
        padding: 14px;
        border-radius: 8px;
        border: 1px solid #2f3744;
        margin-bottom: 10px;
    }}
    .quick-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin-top: 10px;
    }}
    .quick-grid-compact {{
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 8px;
        margin-top: 10px;
    }}
    .quick-stat {{
        border: 1px solid #2d3642;
        background: #131923;
        border-radius: 6px;
        padding: 8px;
    }}
    .quick-stat .label {{
        color: #7d8ba0;
        font-size: 10px;
        margin: 0;
        letter-spacing: 0.3px;
    }}
    .quick-stat .value {{
        font-size: 15px;
        margin: 2px 0 0 0;
        font-weight: 700;
        color: #dce5f2;
    }}
    .quick-stat .sub {{
        color: #8b96a6;
        font-size: 10px;
        margin: 2px 0 0 0;
    }}
    .sentiment-meter {{
        height: 22px;
        background: linear-gradient(90deg, #FF4444 0%, #FFAA00 50%, #44FF44 100%);
        border-radius: 6px;
        position: relative;
        border: 1px solid #313946;
    }}
    .sentiment-marker {{
        position: absolute;
        width: 3px;
        height: 30px;
        background: #101419;
        top: -4px;
        border-radius: 2px;
    }}
    .keyboard-hint {{
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #1a212b;
        padding: 10px;
        border-radius: 8px;
        font-size: 12px;
        color: #888;
        border: 1px solid #2f3845;
        z-index: 5;
    }}
    .news-rail {{
        position: sticky;
        top: 6px;
        max-height: calc(100vh - 96px);
        overflow-y: auto;
        padding-right: 4px;
    }}
    .news-rail-title {{
        font-size: 11px;
        color: #93a0b4;
        letter-spacing: 0.25px;
        text-transform: uppercase;
        margin-bottom: 8px;
        font-weight: 700;
    }}
    .news-item {{
        border: 1px solid #2d3641;
        border-radius: 6px;
        padding: 8px;
        margin-bottom: 7px;
        background: #111722;
    }}
    .news-item p, .news-item div {{
        margin: 0;
    }}
    .panel-split {{
        display: grid;
        grid-template-columns: 2.2fr 1fr;
        gap: 8px;
    }}
    .mini-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
        margin-top: 8px;
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


def _render_left_nav(nav_sections):
    if "main_left_nav" not in st.session_state:
        first_section = next(iter(nav_sections.values()))
        st.session_state.main_left_nav = first_section[0][1]

    st.markdown('<div class="left-nav-shell">', unsafe_allow_html=True)
    st.markdown('<div class="left-nav-title">Workspace</div>', unsafe_allow_html=True)

    for section_name, items in nav_sections.items():
        st.markdown(f'<div class="left-nav-section">{section_name}</div>', unsafe_allow_html=True)
        for label, value in items:
            if st.session_state.main_left_nav == value:
                st.markdown(f'<div class="nav-item active">{label}</div>', unsafe_allow_html=True)
            else:
                if st.button(label, key=f"nav_{value}", use_container_width=True):
                    st.session_state.main_left_nav = value
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    return st.session_state.main_left_nav


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

    level_interactions_df = None
    nq_data = None
    if data_0dte:
        nq_data = get_nq_intraday_data()
        if nq_data is not None and not nq_data.empty:
            level_interactions_df = _build_level_interactions(nq_data, data_0dte)

    nav_sections = {
        "Workspace": [
            ("🏠 Overview", "📈 Market Overview"),
            ("🌐 Multi-Asset", "🌐 Multi-Asset"),
        ],
        "Resources": [],
        "Analytics": [
            ("🍞 Daily Bread", "🍞 Daily Bread"),
            ("📈 GEX Charts", "📈 GEX Charts"),
            ("⚖️ Delta Charts", "⚖️ Delta Charts"),
        ],
    }
    if data_0dte:
        nav_sections["Resources"].append(("📊 0DTE Levels", "📊 0DTE Levels"))
    if data_weekly:
        nav_sections["Resources"].append(("📊 Weekly Levels", "📊 Weekly Levels"))
    if data_monthly:
        nav_sections["Resources"].append(("📊 Monthly Levels", "📊 Monthly Levels"))

    nav_col, center_col, right_col = st.columns([0.95, 5.35, 0.9], gap="small")

    with nav_col:
        active_view = _render_left_nav(nav_sections)

    with center_col:
        es = market_data.get("es", {})
        ym = market_data.get("ym", {})
        rty = market_data.get("rty", {})
        gc = market_data.get("gc", {})

        futures_cards = [
            ("S&P 500 (ES)", es.get("price", 0), es.get("change", 0), es.get("change_pct", 0)),
            ("NASDAQ (NQ)", nq_now, nq_now * (nq_day_change_pct / 100), nq_day_change_pct),
            ("DOW (YM)", ym.get("price", 0), ym.get("change", 0), ym.get("change_pct", 0)),
            ("RUSSELL (RTY)", rty.get("price", 0), rty.get("change", 0), rty.get("change_pct", 0)),
            ("GOLD (GC)", gc.get("price", 0), gc.get("change", 0), gc.get("change_pct", 0)),
        ]
        strip_html = ['<div class="futures-strip">']
        for name, price, chg, pct in futures_cards:
            is_pos = (chg or 0) >= 0
            badge_cls = "pos" if is_pos else "neg"
            arrow = "↑" if is_pos else "↓"
            strip_html.append(
                f'<div class="future-card"><p class="future-title">{name}</p>'
                f'<p class="future-value">{price:,.2f}</p>'
                f'<span class="future-badge {badge_cls}">{arrow} {chg:+.2f} ({pct:+.2f}%)</span></div>'
            )
        strip_html.append("</div>")
        st.markdown("".join(strip_html), unsafe_allow_html=True)

        if active_view == "📈 Market Overview":
            if data_0dte:
                dn_distance = nq_now - data_0dte["dn_nq"]
                gf_distance = nq_now - data_0dte["g_flip_nq"]
                above_gf = gf_distance > 0
                regime = "🔴 NEGATIVE GAMMA" if above_gf else "🟢 POSITIVE GAMMA"
                regime_desc = "Unstable / Whipsaw Risk" if above_gf else "Stable / Range-Bound"
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
                em_points = data_0dte.get("nq_em_full", 0)
                level_gap = abs(data_0dte["p_wall"] - data_0dte["p_floor"])
                source_age = get_quote_age_label("NQ=F")

                st.markdown(
                    f"""
                <div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🎯 Session Quick Glance</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body"><div class="quick-glance">
                    <div class="quick-grid">
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
                    <div class="quick-grid-compact">
                        <div class="quick-stat"><p class="label">GAMMA FLIP DISTANCE</p><p class="value">{gf_distance:+.0f} pts</p><p class="sub">vs {data_0dte['g_flip_nq']:.2f}</p></div>
                        <div class="quick-stat"><p class="label">DELTA NEUTRAL DISTANCE</p><p class="value">{dn_distance:+.0f} pts</p><p class="sub">vs {data_0dte['dn_nq']:.2f}</p></div>
                        <div class="quick-stat"><p class="label">EXPECTED MOVE</p><p class="value">±{em_points:.0f}</p><p class="sub">0DTE implied range</p></div>
                        <div class="quick-stat"><p class="label">WALL-FLOOR SPAN</p><p class="value">{level_gap:.0f} pts</p><p class="sub">{data_0dte['p_floor']:.0f} → {data_0dte['p_wall']:.0f}</p></div>
                        <div class="quick-stat"><p class="label">DATA HEALTH</p><p class="value">{source_age}</p><p class="sub">{nq_source}</p></div>
                    </div>
                </div></div></div>
                """,
                    unsafe_allow_html=True,
                )

                st.markdown(
                    '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📊 Market Sentiment</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
                    unsafe_allow_html=True,
                )
                sc1, sc2 = st.columns([3, 1])
                with sc1:
                    st.markdown(
                        f"""
                    <div style="position: relative;">
                        <div class="sentiment-meter"><div class="sentiment-marker" style="left: {sentiment_score}%;"></div></div>
                        <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 12px; color: #888;">
                            <span>0 (Bearish)</span><span>50 (Neutral)</span><span>100 (Bullish)</span>
                        </div>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                with sc2:
                    sentiment_text = (
                        "BEARISH"
                        if sentiment_score < 30
                        else "CAUTIOUS BEARISH"
                        if sentiment_score < 45
                        else "NEUTRAL"
                        if sentiment_score < 55
                        else "CAUTIOUS BULLISH"
                        if sentiment_score < 70
                        else "BULLISH"
                    )
                    st.metric("Score", f"{sentiment_score}/100", sentiment_text)
                    if sentiment_score >= 55:
                        st.markdown('<span class="metric-chip">↑ Bullish</span>', unsafe_allow_html=True)
                    elif sentiment_score <= 45:
                        st.markdown('<span class="metric-chip">↓ Bearish</span>', unsafe_allow_html=True)
                st.markdown("</div></div>", unsafe_allow_html=True)

                st.markdown(
                    '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧩 Nasdaq Stocks Heat Map</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
                    unsafe_allow_html=True,
                )
                heatmap_df = get_nasdaq_heatmap_data()
                if heatmap_df is not None and not heatmap_df.empty:
                    heatmap_df = heatmap_df.copy()
                    heatmap_df["pct_label"] = heatmap_df["change_pct"].map(lambda x: f"{x:+.2f}%")
                    fig = px.treemap(
                        heatmap_df,
                        path=["sector", "symbol"],
                        values="size",
                        color="change_pct",
                        color_continuous_scale=[
                            [0.0, "#7a1f2b"],
                            [0.25, "#b33d4b"],
                            [0.5, "#2b3038"],
                            [0.75, "#2f7d4f"],
                            [1.0, "#2dc46c"],
                        ],
                        color_continuous_midpoint=0,
                        custom_data=["price", "change_pct", "pct_label"],
                    )
                    fig.update_traces(
                        texttemplate="<b>%{label}</b><br>%{customdata[2]}",
                        hovertemplate="<b>%{label}</b><br>Price: %{customdata[0]:,.2f}<br>Change: %{customdata[1]:+.2f}%<extra></extra>",
                        marker_line=dict(width=1, color="#1f2630"),
                        textfont=dict(size=18, color="#e8eef8"),
                        insidetextfont=dict(size=18, color="#e8eef8"),
                        textposition="middle center",
                    )
                    fig.update_layout(
                        template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white",
                        height=390,
                        margin=dict(l=8, r=8, t=8, b=8),
                        coloraxis_showscale=False,
                        uniformtext=dict(minsize=12, mode="hide"),
                        coloraxis=dict(cmin=-4, cmax=4),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption("Tile color scale clipped to +/-4% for readability.")
                else:
                    st.info("Heat map data is temporarily unavailable.")
                st.markdown("</div></div>", unsafe_allow_html=True)

                hd1, hd2, hd3 = st.columns(3)
                hd1.metric("NQ Price", f"{nq_now:.2f}", f"↑ {nq_source}")
                hd2.metric("QQQ Price", f"${qqq_price:.2f}")
                hd3.metric("Ratio", f"{ratio:.4f}")

                st.markdown(
                    '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🎯 Multi-Timeframe Key Levels</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
                    unsafe_allow_html=True,
                )
                overview_data = []
                if data_0dte:
                    days = (exp_0dte.date() - datetime.now().date()).days
                    overview_data.append(
                        {
                            "Timeframe": "0DTE" if days == 0 else f"{days}DTE",
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
                    overview_data.append(
                        {
                            "Timeframe": f"Weekly ({days}D)",
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
                    overview_data.append(
                        {
                            "Timeframe": f"Monthly ({days}D)",
                            "Expiration": exp_monthly.strftime("%Y-%m-%d"),
                            "Delta Neutral": data_monthly["dn_nq"],
                            "Gamma Flip": data_monthly["g_flip_nq"],
                            "Primary Wall": data_monthly["p_wall"],
                            "Primary Floor": data_monthly["p_floor"],
                            "Net Delta": data_monthly["net_delta"],
                        }
                    )
                if overview_data:
                    st.dataframe(pd.DataFrame(overview_data), width="stretch", hide_index=True)
                st.markdown("</div></div>", unsafe_allow_html=True)
            if market_data:
                st.markdown(
                    '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧭 Futures & Indices</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
                    unsafe_allow_html=True,
                )
                c1, c2, c3, c4, c5 = st.columns(5)
                es = market_data.get("es", {})
                ym = market_data.get("ym", {})
                rty = market_data.get("rty", {})
                gc = market_data.get("gc", {})
                c1.metric("S&P 500 (ES)", f"{es.get('price', 0):.2f}" if es.get("price") else "N/A", f"{es.get('change', 0):+.2f} ({es.get('change_pct', 0):+.2f}%)")
                c1.caption(f"Source: {es.get('source', 'unknown')} | Age: {get_quote_age_label('ES=F')}")
                nq_change = nq_now * (nq_day_change_pct / 100)
                c2.metric("Nasdaq (NQ)", f"{nq_now:.2f}", f"{nq_change:+.2f} ({nq_day_change_pct:+.2f}%)")
                c2.caption(f"Source: {nq_source} | Age: {get_quote_age_label('NQ=F')}")
                c3.metric("Dow (YM)", f"{ym.get('price', 0):.2f}" if ym.get("price") else "N/A", f"{ym.get('change', 0):+.2f} ({ym.get('change_pct', 0):+.2f}%)")
                c3.caption(f"Source: {ym.get('source', 'unknown')} | Age: {get_quote_age_label('YM=F')}")
                c4.metric("Russell (RTY)", f"{rty.get('price', 0):.2f}" if rty.get("price") else "N/A", f"{rty.get('change', 0):+.2f} ({rty.get('change_pct', 0):+.2f}%)")
                c4.caption(f"Source: {rty.get('source', 'unknown')} | Age: {get_quote_age_label('RTY=F')}")
                c5.metric("Gold (GC)", f"{gc.get('price', 0):.2f}" if gc.get("price") else "N/A", f"{gc.get('change', 0):+.2f} ({gc.get('change_pct', 0):+.2f}%)")
                c5.caption(f"Source: {gc.get('source', 'unknown')} | Age: {get_quote_age_label('GC=F')}")
                st.markdown("### Market Signals")
                if data_0dte:
                    st.info(
                        f"NQ vs Gamma Flip: {nq_now - data_0dte['g_flip_nq']:+.0f} pts | "
                        f"NQ vs Delta Neutral: {nq_now - data_0dte['dn_nq']:+.0f} pts | "
                        f"Net Delta: {data_0dte['net_delta']:,.0f}"
                    )
                if level_interactions_df is not None and not level_interactions_df.empty:
                    st.dataframe(level_interactions_df, width="stretch", hide_index=True)
                st.markdown("</div></div>", unsafe_allow_html=True)

        elif active_view == "🌐 Multi-Asset":
            st.subheader("🌐 Multi-Asset Comparison Dashboard")
            multi_asset_data = process_multi_asset()
            if multi_asset_data:
                comparison_data = []
                for asset_name in ["SPY", "QQQ", "IWM", "DIA"]:
                    if asset_name not in multi_asset_data:
                        continue
                    asset = multi_asset_data[asset_name]
                    data_0 = asset.get("data_0dte")
                    if not data_0:
                        continue
                    futures_price = asset["futures_price"]
                    comparison_data.append(
                        {
                            "Index": f"{asset['name']} ({asset_name})",
                            "Futures Price": f"{futures_price:,.2f}",
                            "Delta Neutral": f"{data_0['dn_nq']:,.2f}",
                            "Gamma Flip": f"{data_0['g_flip_nq']:,.2f}",
                            "Net Delta": f"{data_0['net_delta']:,.0f}",
                        }
                    )
                if comparison_data:
                    st.dataframe(pd.DataFrame(comparison_data), width="stretch", hide_index=True)
            else:
                st.error("Could not load multi-asset data")

        elif active_view in {"📊 0DTE Levels", "📊 Weekly Levels", "📊 Monthly Levels"}:
            view_map = {
                "📊 0DTE Levels": ("0DTE", data_0dte, exp_0dte),
                "📊 Weekly Levels": ("Weekly", data_weekly, exp_weekly),
                "📊 Monthly Levels": ("Monthly", data_monthly, exp_monthly),
            }
            label, selected_data, selected_exp = view_map[active_view]
            if selected_data and selected_exp:
                st.subheader(f"{label} Analysis - {selected_exp.strftime('%Y-%m-%d')}")
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Delta Neutral", f"{selected_data['dn_nq']:.2f}")
                d2.metric("Gamma Flip", f"{selected_data['g_flip_nq']:.2f}")
                d3.metric("Net Delta", f"{selected_data['net_delta']:,.0f}")
                d4.metric("Expected Move", f"±{selected_data['nq_em_full']:.0f}")
                results_df = pd.DataFrame(selected_data["results"], columns=["Level", "Price", "Width", "Icon"])
                st.dataframe(results_df[["Icon", "Level", "Price", "Width"]], width="stretch", hide_index=True)
            else:
                st.info("No data available for this timeframe.")

        elif active_view == "🍞 Daily Bread":
            st.subheader("🍞 Daily Bread")
            if data_0dte:
                events = get_economic_calendar(finnhub_key)
                news = get_rss_news()
                daily_bread = generate_daily_bread(data_0dte, data_weekly, nq_now, market_data, fg, events, news)
                st.markdown(f"**{daily_bread.get('session', '')}**")
                st.caption(daily_bread.get("timestamp", ""))
                st.markdown(daily_bread.get("summary", ""))
                with st.expander("Key Levels"):
                    st.markdown(daily_bread.get("levels", ""))
                with st.expander("Market Drivers"):
                    st.markdown(daily_bread.get("drivers", ""))
                with st.expander("Trading Strategy"):
                    st.markdown(daily_bread.get("strategy", ""))
                with st.expander("Tomorrow Watch List"):
                    st.markdown(daily_bread.get("watch_list", ""))
            else:
                st.info("No 0DTE data available for Daily Bread analysis")

        elif active_view == "📈 GEX Charts":
            st.subheader("📈 GEX by Strike")
            for name, selected_data in [("0DTE", data_0dte), ("Weekly", data_weekly), ("Monthly", data_monthly)]:
                if not selected_data:
                    continue
                st.markdown(f"**{name}**")
                gex_by_strike = selected_data["df"].groupby("strike")["GEX"].sum().reset_index()
                fig = go.Figure()
                pos_gex = gex_by_strike[gex_by_strike["GEX"] > 0]
                neg_gex = gex_by_strike[gex_by_strike["GEX"] < 0]
                fig.add_trace(go.Bar(x=pos_gex["strike"], y=pos_gex["GEX"], name="Calls", marker_color="#FF4444"))
                fig.add_trace(go.Bar(x=neg_gex["strike"], y=neg_gex["GEX"], name="Puts", marker_color="#44FF44"))
                fig.add_vline(x=qqq_price, line_dash="dash", line_color="#00D9FF", annotation_text="Current")
                fig.update_layout(template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white", height=360)
                st.plotly_chart(fig, use_container_width=True)

        elif active_view == "⚖️ Delta Charts":
            st.subheader("⚖️ Cumulative Delta")
            for name, selected_data in [("0DTE", data_0dte), ("Weekly", data_weekly), ("Monthly", data_monthly)]:
                if not selected_data:
                    continue
                st.markdown(f"**{name}**")
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=selected_data["strike_delta"]["strike"],
                        y=selected_data["strike_delta"]["cumulative_delta"],
                        mode="lines",
                        line=dict(color="#00D9FF", width=3),
                        fill="tozeroy",
                    )
                )
                fig.add_hline(y=0, line_dash="dash", line_color="white")
                fig.add_vline(x=selected_data["dn_strike"], line_dash="dot", line_color="#FFD700", annotation_text="Delta Neutral")
                fig.update_layout(template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white", height=360)
                st.plotly_chart(fig, use_container_width=True)

    with right_col:
        st.markdown(
            '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📰 Live News Feed</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
            unsafe_allow_html=True,
        )
        rss_news = get_rss_news()
        st.markdown('<div class="news-rail-title">Headlines</div>', unsafe_allow_html=True)
        st.markdown('<div class="news-rail">', unsafe_allow_html=True)
        if rss_news:
            for article in rss_news[:18]:
                headline = html.escape(article.get("headline", "No title"))
                source = html.escape(article.get("source", "Unknown"))
                link = article.get("link", "#")
                published = html.escape(article.get("published", ""))
                st.markdown(
                    f"""
                    <div class="news-item">
                        <div style="font-weight:700;color:#e9eef7;font-size:15px;line-height:1.35;">{headline}</div>
                        <div style="color:#9da8ba;font-size:12px;margin-top:6px;">{source} • {published}</div>
                        <div style="margin-top:8px;"><a href="{link}" target="_blank">Open</a></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("News feed temporarily unavailable")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')} | CBOE • {nq_source}")

    if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
        st.session_state.last_refresh = time.time()
        st.cache_data.clear()
        st.rerun()
