import time
from datetime import datetime, timedelta
import html
import math
import re
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

from nq_precision.full_data import (
    calculate_sentiment_score,
    exchange_schwab_auth_code,
    generate_daily_bread,
    get_cboe_options,
    get_cboe_options_live,
    get_dataset_freshness,
    get_earnings_calendar_multi,
    get_earnings_detail,
    get_economic_calendar,
    get_economic_calendar_window,
    get_event_risk_snapshot,
    get_expirations_by_type,
    get_fear_greed_index,
    get_futures_breadth_internals,
    get_cot_dealer_positioning,
    get_initial_balance_backtest,
    get_futures_reference_levels,
    get_futures_opening_structure,
    get_market_overview_yahoo,
    get_nasdaq_heatmap_data,
    get_nq_intraday_data,
    get_nq_price_auto,
    get_quote_age_label,
    get_qqq_price_with_source,
    get_runtime_health,
    get_rss_news,
    get_top_movers,
    process_expiration,
    process_multi_asset,
    schwab_is_configured,
)


def _theme_css(bg_color, card_bg, text_color, accent_color, border_color, compact_mode=False):
    compact_css = ""
    if compact_mode:
        compact_css = """
    .terminal-body { padding: 8px !important; }
    .future-card { min-height: 92px !important; padding: 10px 12px !important; }
    .future-value { font-size: 33px !important; margin: 5px 0 7px 0 !important; }
    .score-panel { min-height: 104px !important; padding: 10px !important; }
    .quick-glance { padding: 10px !important; margin-bottom: 8px !important; }
    .stMetric { min-height: 74px !important; }
    .news-item { padding: 7px !important; margin-bottom: 6px !important; }
        """
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
        background: linear-gradient(180deg, #141922 0%, #0f141c 100%);
        border: 1px solid #2a313d;
        border-radius: 5px;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
        overflow: hidden;
        margin-bottom: 8px;
    }}
    .terminal-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        padding: 6px 9px;
        background: linear-gradient(180deg, #1f2631 0%, #181f28 100%);
        border-bottom: 1px solid #2c3441;
        color: #cfd7e5;
        font-size: 11px;
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
        display: none;
    }}
    .terminal-body {{
        padding: 8px;
    }}
    .terminal-command-shell {{
        border: 1px solid #2a323f;
        border-radius: 5px;
        background: linear-gradient(180deg, #191f29 0%, #101722 100%);
        margin-bottom: 8px;
        overflow: hidden;
    }}
    .terminal-command-top {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        padding: 7px 9px;
        border-bottom: 1px solid #2b3442;
        background: #171d27;
    }}
    .terminal-brand {{
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        font-weight: 700;
        color: #e4ebf7;
        letter-spacing: 0.3px;
        text-transform: uppercase;
    }}
    .status-dot {{
        width: 8px;
        height: 8px;
        border-radius: 999px;
        display: inline-block;
        background: #39d67a;
        box-shadow: 0 0 8px rgba(57, 214, 122, 0.8);
    }}
    .terminal-right-meta {{
        display: flex;
        align-items: center;
        gap: 10px;
        color: #9aa7bb;
        font-size: 11px;
        font-weight: 600;
    }}
    .terminal-command-grid {{
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 6px;
        padding: 7px 8px;
    }}
    .cmd-chip {{
        border: 1px solid #2f3948;
        border-radius: 4px;
        background: #111823;
        padding: 5px 7px;
        min-height: 48px;
    }}
    .cmd-chip .k {{
        margin: 0;
        color: #8a99af;
        font-size: 10px;
        letter-spacing: 0.25px;
        text-transform: uppercase;
        font-weight: 700;
    }}
    .cmd-chip .v {{
        margin: 4px 0 0 0;
        color: #dbe5f3;
        font-size: 14px;
        font-weight: 700;
    }}
    .cmd-chip .v.good {{ color: #66f4a9; }}
    .cmd-chip .v.warn {{ color: #ffd27d; }}
    .cmd-chip .v.bad {{ color: #ff8f8f; }}
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
    .health-strip {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 8px;
        margin-bottom: 10px;
    }}
    .health-card {{
        border: 1px solid #2d3641;
        border-radius: 8px;
        padding: 8px 9px;
        background: linear-gradient(180deg, #181f2a 0%, #111823 100%);
    }}
    .health-card .title {{
        margin: 0;
        color: #90a0b5;
        font-size: 10px;
        letter-spacing: 0.25px;
        text-transform: uppercase;
        font-weight: 700;
    }}
    .health-card .value {{
        margin: 3px 0 0 0;
        color: #e9eef8;
        font-size: 14px;
        font-weight: 700;
    }}
    .health-card .sub {{
        margin: 2px 0 0 0;
        color: #8694a8;
        font-size: 10px;
    }}
    .status-pill {{
        display: inline-block;
        margin-top: 4px;
        border-radius: 999px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: 700;
        border: 1px solid transparent;
    }}
    .status-pill.ok {{
        background: rgba(39, 133, 83, 0.24);
        color: #67f7ad;
        border-color: #2f7d56;
    }}
    .status-pill.warn {{
        background: rgba(166, 123, 32, 0.24);
        color: #ffd47a;
        border-color: #7d6430;
    }}
    .status-pill.bad {{
        background: rgba(176, 56, 56, 0.22);
        color: #ff8d8d;
        border-color: #7e3434;
    }}
    .trade-plan-grid {{
        display: grid;
        grid-template-columns: 1.25fr 1fr 1fr 1fr;
        gap: 8px;
        margin-bottom: 9px;
    }}
    .trade-plan-stat {{
        border: 1px solid #2d3642;
        background: #131923;
        border-radius: 6px;
        padding: 8px;
    }}
    .trade-plan-stat .k {{
        margin: 0;
        color: #8d9db3;
        font-size: 10px;
        letter-spacing: 0.25px;
        text-transform: uppercase;
        font-weight: 700;
    }}
    .trade-plan-stat .v {{
        margin: 3px 0 0 0;
        color: #dce5f2;
        font-size: 16px;
        font-weight: 800;
    }}
    .trade-plan-note {{
        border: 1px solid #2d3642;
        background: #121823;
        border-radius: 6px;
        padding: 8px;
        font-size: 13px;
        color: #dbe4f2;
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
    .score-panel {{
        background: linear-gradient(180deg, #1a1f28 0%, #121924 100%);
        border: 1px solid #2f3947;
        border-radius: 10px;
        padding: 12px;
        min-height: 122px;
    }}
    .score-kicker {{
        color: #9ca8bb;
        font-size: 11px;
        letter-spacing: 0.3px;
        text-transform: uppercase;
        font-weight: 700;
        margin: 0 0 6px 0;
    }}
    .score-value {{
        color: #39d8ff;
        font-size: 42px;
        line-height: 1.05;
        margin: 0;
        font-weight: 800;
    }}
    .score-badge {{
        display: inline-block;
        margin-top: 10px;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        border: 1px solid transparent;
    }}
    .score-badge.bear {{
        color: #ff8d8d;
        background: rgba(176, 56, 56, 0.22);
        border-color: #7e3434;
    }}
    .score-badge.neutral {{
        color: #ffd47a;
        background: rgba(166, 123, 32, 0.22);
        border-color: #7d6430;
    }}
    .score-badge.bull {{
        color: #63f6a8;
        background: rgba(42, 136, 86, 0.25);
        border-color: #2f7d56;
    }}
    .sentiment-wrap {{
        min-height: 122px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}
    .sentiment-axis {{
        display: flex;
        justify-content: space-between;
        margin-top: 6px;
        font-size: 12px;
        color: #8d98a9;
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
    .earn-day-title {{
        font-size: 14px;
        color: #dbe4f2;
        font-weight: 700;
        margin-bottom: 6px;
    }}
    .earn-time-title {{
        font-size: 11px;
        color: #9ea9bc;
        text-transform: uppercase;
        font-weight: 700;
        margin: 8px 0 6px 0;
    }}
    .earn-card {{
        border: 1px solid #2f3947;
        background: linear-gradient(180deg, #171f2b 0%, #131a24 100%);
        border-radius: 8px;
        padding: 8px;
        margin-bottom: 8px;
    }}
    .earn-card .sym {{
        color: #f0f4fb;
        font-weight: 800;
        font-size: 14px;
    }}
    .earn-card .meta {{
        color: #9ba8ba;
        font-size: 11px;
        margin-top: 2px;
    }}
    .econ-header, .econ-row {{
        display: grid;
        grid-template-columns: 90px 1.9fr 90px 110px 110px 100px 100px 70px;
        gap: 8px;
        align-items: center;
        padding: 6px 8px;
    }}
    .econ-header {{
        font-size: 11px;
        color: #9aa8bc;
        text-transform: uppercase;
        border-bottom: 1px solid #2f3947;
        font-weight: 700;
    }}
    .econ-row {{
        border-bottom: 1px solid #222a36;
        font-size: 13px;
        color: #dce6f3;
    }}
    .econ-row.high {{
        background: rgba(150, 45, 45, 0.22);
    }}
    .econ-row.medium {{
        background: rgba(141, 103, 29, 0.18);
    }}
    .econ-row.low {{
        background: rgba(44, 63, 87, 0.12);
    }}
    .impact-chip {{
        border-radius: 999px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 700;
        display: inline-block;
        text-align: center;
    }}
    .impact-chip.high {{ background: #7b2d2d; color: #ffd8d8; }}
    .impact-chip.medium {{ background: #7a5d2a; color: #ffe7b3; }}
    .impact-chip.low {{ background: #27405f; color: #cde4ff; }}
    .count-chip {{
        border-radius: 999px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 700;
        background: #2f7d56;
        color: #b6ffd8;
    }}
    @media (max-width: 1400px) {{
        .terminal-command-grid {{
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }}
        .futures-strip {{
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }}
    }}
    @media (max-width: 900px) {{
        .terminal-command-grid {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .futures-strip {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
    }}
    {compact_css}
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


def _render_terminal_command_bar(active_view, nq_source, qqq_source, auto_refresh, refresh_interval, ratio_meta, event_risk, market_data):
    ratio_meta = ratio_meta or {}
    event_risk = event_risk or {}
    market_data = market_data or {}
    vix_px = _safe_float((market_data.get("vix", {}) or {}).get("price"), 0.0) or 0.0
    vix_chg = _safe_float((market_data.get("vix", {}) or {}).get("change_pct"), 0.0) or 0.0
    ratio_conf = int(ratio_meta.get("confidence_score", 0) or 0)
    ratio_lbl = str(ratio_meta.get("confidence_label", "Low"))
    next_event = (event_risk.get("next_events") or [None])[0]
    next_event_label = "-"
    if next_event:
        next_event_label = f"{next_event.get('time_et', '-')}: {str(next_event.get('event', 'Event'))[:22]}"
    refresh_txt = f"{refresh_interval}s" if auto_refresh else "manual"
    ratio_cls = "good" if ratio_lbl.lower() == "high" else "warn" if ratio_lbl.lower() == "medium" else "bad"
    vix_cls = "warn" if vix_px >= 18 else "good"
    lock_cls = "bad" if event_risk.get("lockout_active") else "good"
    lock_text = "LOCKOUT" if event_risk.get("lockout_active") else "CLEAR"

    st.markdown(
        f"""
        <div class="terminal-command-shell">
            <div class="terminal-command-top">
                <div class="terminal-brand"><span class="status-dot"></span> NQ Futures Terminal • {html.escape(str(active_view))}</div>
                <div class="terminal-right-meta">
                    <span>AUTO: {html.escape(refresh_txt)}</span>
                    <span>NQ: {html.escape(str(nq_source))}</span>
                    <span>QQQ: {html.escape(str(qqq_source))}</span>
                    <span>{datetime.now().strftime("%I:%M:%S %p ET")}</span>
                </div>
            </div>
            <div class="terminal-command-grid">
                <div class="cmd-chip"><p class="k">VIX</p><p class="v {vix_cls}">{vix_px:.2f} ({vix_chg:+.2f}%)</p></div>
                <div class="cmd-chip"><p class="k">Ratio Quality</p><p class="v {ratio_cls}">{ratio_lbl.upper()} {ratio_conf}%</p></div>
                <div class="cmd-chip"><p class="k">Event Lock</p><p class="v {lock_cls}">{lock_text}</p></div>
                <div class="cmd-chip"><p class="k">High Impact Today</p><p class="v">{int(event_risk.get("today_high_count", 0) or 0)}</p></div>
                <div class="cmd-chip"><p class="k">Med Impact Today</p><p class="v">{int(event_risk.get("today_medium_count", 0) or 0)}</p></div>
                <div class="cmd-chip"><p class="k">Next Event</p><p class="v">{html.escape(next_event_label)}</p></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _track_level_changes(tracker_key, current_levels):
    now_ts = datetime.now().strftime("%H:%M:%S")
    previous = st.session_state.get(tracker_key)
    changes_df = None
    prev_ts = None

    if previous and isinstance(previous, dict) and previous.get("levels"):
        prev_ts = previous.get("ts")
        rows = []
        prev_levels = previous["levels"]
        for name, current_value in current_levels.items():
            prev_value = prev_levels.get(name)
            if prev_value is None:
                continue
            delta = float(current_value) - float(prev_value)
            rows.append(
                {
                    "Level": name,
                    "Current": float(current_value),
                    "Prev": float(prev_value),
                    "Change (pts)": float(delta),
                }
            )
        if rows:
            changes_df = pd.DataFrame(rows)

    st.session_state[tracker_key] = {"ts": now_ts, "levels": dict(current_levels)}
    return changes_df, prev_ts


def _fmt_econ_value(v):
    if v is None:
        return "-"
    if isinstance(v, float) and pd.isna(v):
        return "-"
    s = str(v).strip()
    if s.lower() in {"", "none", "nan", "null"}:
        return "-"
    return s


def _latency_from_asof_utc(asof_utc):
    if not asof_utc:
        return None
    try:
        dt = datetime.fromisoformat(str(asof_utc).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        now_utc = datetime.now(ZoneInfo("UTC"))
        return max(0, int((now_utc - dt).total_seconds()))
    except Exception:
        return None


def _latency_label(age_sec):
    if age_sec is None:
        return "n/a"
    if age_sec < 60:
        return f"{age_sec}s"
    mins = age_sec // 60
    secs = age_sec % 60
    return f"{mins}m {secs:02d}s"


def _render_external_econ_widget():
    widget_html = """
    <div style="border:1px solid #2f3540;border-radius:8px;overflow:hidden;background:#111722;">
      <div style="padding:8px 10px;border-bottom:1px solid #313946;color:#d6dbe4;font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:.2px;">
        🌐 Live Economic Calendar (Fallback Feed)
      </div>
      <div class="tradingview-widget-container">
        <div id="tradingview-widget-container__widget"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
        {
          "colorTheme": "dark",
          "isTransparent": true,
          "width": "100%",
          "height": 700,
          "locale": "en",
          "importanceFilter": "-1,0,1"
        }
        </script>
      </div>
    </div>
    """
    components.html(widget_html, height=760, scrolling=True)


def _countdown_label(seconds_to):
    if seconds_to is None:
        return "-"
    sec = int(seconds_to)
    direction = "T-" if sec >= 0 else "T+"
    sec_abs = abs(sec)
    hh = sec_abs // 3600
    mm = (sec_abs % 3600) // 60
    ss = sec_abs % 60
    if hh > 0:
        return f"{direction}{hh}h {mm:02d}m"
    if mm > 0:
        return f"{direction}{mm}m {ss:02d}s"
    return f"{direction}{ss}s"


def _safe_float(v, default=None):
    try:
        if v is None:
            return default
        if isinstance(v, float) and pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def _ratio_health_status(conf_label):
    lbl = str(conf_label or "").lower()
    if lbl == "high":
        return "fresh"
    if lbl == "medium":
        return "stale_soft"
    return "stale_hard"


def _ratio_source_tag(src):
    s = str(src or "").strip()
    if not s:
        return "unknown"
    # Prefer contract-like token inside source suffix, e.g. "Schwab (/NQM26)".
    m = re.search(r"\(([^)]+)\)", s)
    if m:
        token = m.group(1)
    else:
        token = s
    token = token.strip().lower()
    token = re.sub(r"[^a-z0-9/_=.-]+", "_", token)
    return token[:48] or "unknown"


def _compute_tight_ratio(nq_now, qqq_price, nq_source="", qqq_source=""):
    raw_ratio = float(nq_now / qqq_price) if qqq_price and qqq_price > 0 else 0.0
    now_ts = float(time.time())
    nq_tag = _ratio_source_tag(nq_source)
    qqq_tag = _ratio_source_tag(qqq_source)
    hist_key = f"ratio_history::NQ_QQQ::{nq_tag}::{qqq_tag}"
    history = list(st.session_state.get(hist_key, []))

    if raw_ratio > 0 and math.isfinite(raw_ratio):
        history.append(
            {
                "ts": now_ts,
                "ratio": float(raw_ratio),
                "nq": float(nq_now),
                "qqq": float(qqq_price),
                "nq_source": str(nq_source or ""),
                "qqq_source": str(qqq_source or ""),
            }
        )
    cutoff = now_ts - (3 * 3600)
    history = [h for h in history if float(h.get("ts", 0.0)) >= cutoff and float(h.get("ratio", 0.0)) > 0]
    if len(history) > 240:
        history = history[-240:]
    st.session_state[hist_key] = history

    if raw_ratio <= 0:
        return {
            "ratio": 0.0,
            "raw_ratio": 0.0,
            "median_ratio": 0.0,
            "mad_ratio": 0.0,
            "samples": 0,
            "confidence_score": 0,
            "confidence_label": "Low",
            "outlier_clamped": False,
            "deviation_bps": 0.0,
            "uncertainty_pts": 0.0,
            "source_pair": f"{nq_source} / {qqq_source}",
        }

    ratio_series = pd.Series([float(h["ratio"]) for h in history], dtype="float64")
    recent_series = ratio_series.tail(min(30, len(ratio_series)))
    med_ratio = float(recent_series.median()) if len(recent_series) > 0 else raw_ratio
    abs_dev_series = (recent_series - med_ratio).abs()
    mad_ratio = float(abs_dev_series.median()) if len(abs_dev_series) > 0 else 0.0

    # Prevent overreaction when history is thin or noise is tiny.
    floor_band = max(0.00020, med_ratio * 0.00020)  # 2 bps floor
    dyn_band = max(floor_band, 4.0 * mad_ratio)
    low_band = med_ratio - dyn_band
    high_band = med_ratio + dyn_band
    clamped_ratio = min(max(raw_ratio, low_band), high_band)
    outlier_clamped = abs(raw_ratio - clamped_ratio) > 1e-12

    if len(recent_series) >= 8:
        tight_ratio = (0.72 * clamped_ratio) + (0.28 * med_ratio)
    elif len(recent_series) >= 3:
        tight_ratio = (0.84 * raw_ratio) + (0.16 * med_ratio)
    else:
        tight_ratio = raw_ratio

    dev_bps = abs(raw_ratio - tight_ratio) / max(1e-9, tight_ratio) * 10000.0
    uncertainty_ratio = max((mad_ratio * 2.0), (floor_band * 1.25))
    uncertainty_pts = float(qqq_price) * uncertainty_ratio

    conf = 92.0
    nq_src_l = str(nq_source or "").lower()
    qqq_src_l = str(qqq_source or "").lower()
    conf += 4.0 if "schwab" in nq_src_l else -6.0
    if "schwab" in qqq_src_l:
        conf += 4.0
    elif "finnhub" in qqq_src_l:
        conf += 1.0
    else:
        conf -= 4.0
    if len(recent_series) < 10:
        conf -= 12.0
    if outlier_clamped:
        conf -= 14.0
    if dev_bps > 4.0:
        conf -= min(30.0, (dev_bps - 4.0) * 2.2)
    conf = max(20.0, min(99.0, conf))
    conf_i = int(round(conf))
    conf_label = "High" if conf_i >= 78 else "Medium" if conf_i >= 55 else "Low"

    return {
        "ratio": float(tight_ratio),
        "raw_ratio": float(raw_ratio),
        "median_ratio": float(med_ratio),
        "mad_ratio": float(mad_ratio),
        "samples": int(len(recent_series)),
        "confidence_score": conf_i,
        "confidence_label": conf_label,
        "outlier_clamped": bool(outlier_clamped),
        "deviation_bps": float(dev_bps),
        "uncertainty_pts": float(uncertainty_pts),
        "source_pair": f"{nq_source} / {qqq_source}",
    }


def _parse_macro_number(raw):
    if raw is None:
        return None
    s = str(raw).strip().upper().replace(",", "")
    if s in {"", "-", "N/A", "NONE", "NAN", "NULL"}:
        return None
    neg_paren = s.startswith("(") and s.endswith(")")
    if neg_paren:
        s = s[1:-1].strip()
    if s.endswith("%"):
        s = s[:-1]
    mult = 1.0
    if s.endswith("K"):
        mult = 1_000.0
        s = s[:-1]
    elif s.endswith("M"):
        mult = 1_000_000.0
        s = s[:-1]
    elif s.endswith("B"):
        mult = 1_000_000_000.0
        s = s[:-1]
    elif s.endswith("T"):
        mult = 1_000_000_000_000.0
        s = s[:-1]
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        return None
    v = float(m.group(0)) * mult
    if neg_paren:
        v = -abs(v)
    return v


def _build_regime_engine(data_0dte, data_weekly, nq_now, market_data, opening_structure, event_risk, nq_data):
    if not data_0dte:
        return {}

    dn_distance = float(nq_now - data_0dte["dn_nq"])
    gf_distance = float(nq_now - data_0dte["g_flip_nq"])

    gamma_score = -24 if gf_distance > 0 else 16
    if abs(dn_distance) > 280:
        stretch_score = -12 if dn_distance > 0 else 9
    elif abs(dn_distance) > 150:
        stretch_score = -6 if dn_distance > 0 else 5
    else:
        stretch_score = 3

    macro_score = 0
    vix = _safe_float((market_data.get("vix", {}) or {}).get("price"), 0.0)
    vvix = _safe_float((market_data.get("vvix", {}) or {}).get("price"), 0.0)
    dxy_chg = _safe_float((market_data.get("dxy", {}) or {}).get("change_pct"), 0.0)
    tnx_chg = _safe_float((market_data.get("10y", {}) or {}).get("change"), 0.0)
    macro_score += 6 if vix < 16 else -10 if vix > 22 else 0
    macro_score += 4 if vvix < 95 else -6 if vvix > 110 else 0
    macro_score += 2 if dxy_chg <= 0 else -2
    macro_score += 2 if tnx_chg <= 0 else -2

    opening_score = 0
    op_type = str((opening_structure or {}).get("opening_type", "")).lower()
    vwap_rel = str((opening_structure or {}).get("vwap_relation", "")).lower()
    if "trend up" in op_type:
        opening_score += 6
    elif "trend down" in op_type:
        opening_score -= 6
    elif "reversal up" in op_type:
        opening_score += 4
    elif "reversal down" in op_type:
        opening_score -= 4
    if "above" in vwap_rel:
        opening_score += 2
    elif "below" in vwap_rel:
        opening_score -= 2

    event_score = 2
    if event_risk and event_risk.get("lockout_active"):
        event_score = -14
    else:
        nh = (event_risk or {}).get("next_high")
        if nh and int(nh.get("seconds_to", 999999)) <= 3600:
            event_score = -8

    trend_score = 0
    rv_score = 0
    if nq_data is not None and not nq_data.empty and len(nq_data) >= 14:
        close = nq_data["Close"].astype(float)
        rets = close.pct_change().dropna()
        if not rets.empty:
            rv_5m_pct = float(rets.tail(min(24, len(rets))).std() * 100.0)
            rv_score = -6 if rv_5m_pct > 0.24 else 2 if rv_5m_pct < 0.12 else 0
        ret_12 = float((close.iloc[-1] / close.iloc[-13] - 1.0) * 100.0) if len(close) >= 13 else 0.0
        trend_score = 7 if ret_12 > 0.25 else -7 if ret_12 < -0.25 else 0

    weekly_score = 0
    if data_weekly:
        weekly_dn = float(data_weekly.get("dn_nq", nq_now))
        weekly_gf = float(data_weekly.get("g_flip_nq", nq_now))
        weekly_bias = 1 if nq_now > weekly_gf else -1
        intraday_bias = 1 if gf_distance > 0 else -1
        weekly_score = 5 if weekly_bias == intraday_bias else -5
        if abs(nq_now - weekly_dn) < 70:
            weekly_score += 2

    total = int(max(-100, min(100, gamma_score + stretch_score + macro_score + opening_score + event_score + trend_score + rv_score + weekly_score)))
    if total >= 22:
        regime = "Trend / Risk-On"
        execution = "Favor momentum and buy pullbacks into validated support."
    elif total <= -22:
        regime = "Defensive / Volatile"
        execution = "Use smaller size; fade extensions or scalp around hard levels."
    else:
        regime = "Balanced / Two-Way"
        execution = "Lean mean-reversion until range breaks with acceptance."

    comp_rows = [
        {"Factor": "Gamma Regime", "Score": gamma_score},
        {"Factor": "Stretch vs Delta Neutral", "Score": stretch_score},
        {"Factor": "Macro (VIX/VVIX/DXY/US10Y)", "Score": macro_score},
        {"Factor": "Opening Auction", "Score": opening_score},
        {"Factor": "Event Risk", "Score": event_score},
        {"Factor": "Intraday Trend/Vol", "Score": trend_score + rv_score},
        {"Factor": "Weekly Alignment", "Score": weekly_score},
    ]
    return {
        "score": total,
        "regime": regime,
        "execution": execution,
        "dn_distance": dn_distance,
        "gf_distance": gf_distance,
        "components": comp_rows,
    }


def _build_dealer_forward_pressure(data_0dte, qqq_price, ratio):
    if not data_0dte:
        return {}
    df = data_0dte.get("df")
    if df is None or df.empty:
        return {}

    use = df.copy()
    use["open_interest"] = use["open_interest"].fillna(0.0)
    use["gamma"] = use["gamma"].fillna(0.0)
    use["gamma_unit"] = use.apply(
        lambda r: float(r["open_interest"]) * float(r["gamma"]) * 100.0 * (1.0 if r["type"] == "call" else -1.0),
        axis=1,
    )
    ratio_safe = max(1e-6, float(ratio or 0.0))
    qqq_safe = max(1e-6, float(qqq_price or 0.0))

    scenarios = []
    for move_pts in [25, 50, 100]:
        d_qqq = float(move_pts / ratio_safe)
        raw_delta_notional = float((use["gamma_unit"] * d_qqq * qqq_safe).sum())
        # Hedge flow approximation: dealers hedge opposite the option delta change.
        flow_up = -raw_delta_notional
        flow_down = raw_delta_notional
        scenarios.append(
            {
                "Move": f"+{move_pts} pts",
                "Dealer Hedge Flow": flow_up,
                "Action": "Buy" if flow_up > 0 else "Sell",
            }
        )
        scenarios.append(
            {
                "Move": f"-{move_pts} pts",
                "Dealer Hedge Flow": flow_down,
                "Action": "Buy" if flow_down > 0 else "Sell",
            }
        )

    strike_map = (
        use.groupby("strike", as_index=False)
        .agg(gamma_unit=("gamma_unit", "sum"), gex=("GEX", "sum"), oi=("open_interest", "sum"))
        .sort_values("strike")
    )
    strike_map["nq_strike"] = strike_map["strike"] * ratio_safe
    strike_map["abs_gamma"] = strike_map["gamma_unit"].abs()
    strike_nodes = (
        strike_map.sort_values("abs_gamma", ascending=False)
        .head(8)
        .sort_values("nq_strike")[["nq_strike", "gamma_unit", "gex", "oi"]]
    )
    lead_flow = float(scenarios[0]["Dealer Hedge Flow"]) if scenarios else 0.0
    regime = "Short Gamma (chase moves)" if lead_flow > 0 else "Long Gamma (dampen moves)"
    return {
        "regime": regime,
        "scenarios": scenarios,
        "nodes": strike_nodes,
    }


def _build_microstructure_snapshot(nq_data, opening_structure):
    if nq_data is None or nq_data.empty or len(nq_data) < 12:
        return {}

    use = nq_data.copy()
    use = use.rename(columns=str.title)
    close = use["Close"].astype(float)
    high = use["High"].astype(float)
    low = use["Low"].astype(float)
    open_ = use["Open"].astype(float)
    volume = use["Volume"].fillna(0.0).astype(float)

    bar_range = high - low
    avg_range_20 = float(bar_range.tail(min(20, len(bar_range))).mean())
    cur_range = float(bar_range.iloc[-1])
    range_ratio = float(cur_range / avg_range_20) if avg_range_20 > 0 else 1.0

    rets = close.pct_change().dropna()
    rv_5m_pct = float(rets.tail(min(24, len(rets))).std() * 100.0) if not rets.empty else 0.0
    trend_12 = float((close.iloc[-1] / close.iloc[-13] - 1.0) * 100.0) if len(close) >= 13 else 0.0

    vwap = float((close * volume).sum() / volume.sum()) if float(volume.sum()) > 0 else float(close.mean())
    vwap_dev_pts = float(close.iloc[-1] - vwap)

    up_vol = float(volume[(close >= open_)].sum())
    down_vol = float(volume[(close < open_)].sum())
    total_vol = up_vol + down_vol
    vol_imb = float(((up_vol - down_vol) / total_vol) * 100.0) if total_vol > 0 else 0.0

    vol_mean = float(volume.tail(min(20, len(volume))).mean())
    vol_std = float(volume.tail(min(20, len(volume))).std()) if len(volume) > 2 else 0.0
    vol_z = float((volume.iloc[-1] - vol_mean) / vol_std) if vol_std > 0 else 0.0

    if range_ratio < 0.82 and abs(vol_imb) < 8:
        state = "Compression"
    elif trend_12 > 0.25 and vol_imb > 8:
        state = "Up Impulse"
    elif trend_12 < -0.25 and vol_imb < -8:
        state = "Down Impulse"
    else:
        state = "Rotation"

    drive = str((opening_structure or {}).get("open_drive_signal", "Balanced"))
    return {
        "state": state,
        "rv_5m_pct": rv_5m_pct,
        "range_ratio": range_ratio,
        "trend_12_pct": trend_12,
        "vwap_dev_pts": vwap_dev_pts,
        "vol_imb_pct": vol_imb,
        "vol_z": vol_z,
        "open_drive": drive,
    }


def _build_cross_asset_driver_matrix(market_data, nq_day_change_pct):
    cfg = [
        ("ES", "es", 1.00, +1, "Risk Beta"),
        ("RTY", "rty", 0.85, +1, "Risk Beta"),
        ("YM", "ym", 0.70, +1, "Risk Beta"),
        ("GC", "gc", 0.30, +1, "Commodity"),
        ("DXY", "dxy", 0.75, -1, "USD"),
        ("US10Y", "10y", 0.65, -1, "Rates"),
        ("VIX", "vix", 1.10, -1, "Vol"),
        ("VVIX", "vvix", 0.75, -1, "Vol"),
    ]
    rows = []
    composite = 0.0
    for label, key, weight, direction, bucket in cfg:
        md = market_data.get(key, {}) or {}
        if key == "10y":
            raw_change = _safe_float(md.get("change"), 0.0) * 10.0
        else:
            raw_change = _safe_float(md.get("change_pct"), 0.0)
        impact = float(direction * weight * raw_change)
        composite += impact
        rows.append(
            {
                "Driver": label,
                "Bucket": bucket,
                "Change": raw_change,
                "Signed Impact": impact,
                "Weight": weight,
            }
        )

    rows.append(
        {
            "Driver": "NQ",
            "Bucket": "Core",
            "Change": float(nq_day_change_pct),
            "Signed Impact": float(nq_day_change_pct),
            "Weight": 1.0,
        }
    )
    df = pd.DataFrame(rows).sort_values("Signed Impact", ascending=False)
    regime = "Risk-On" if composite >= 0.8 else "Risk-Off" if composite <= -0.8 else "Mixed"
    dominant = df.iloc[df["Signed Impact"].abs().idxmax()]["Driver"] if not df.empty else "N/A"
    return {
        "composite": composite,
        "regime": regime,
        "dominant": dominant,
        "rows": df,
    }


def _build_event_surprise_engine(econ_df):
    if econ_df is None or econ_df.empty:
        return {}
    now_et = datetime.now(ZoneInfo("America/New_York"))
    past_cut = now_et - timedelta(hours=36)
    future_cut = now_et + timedelta(hours=8)
    impact_w = {"high": 3.0, "medium": 2.0, "low": 1.0}

    releases = []
    upcoming = []
    for _, row in econ_df.iterrows():
        try:
            dt_raw = row.get("event_dt_iso")
            evt_dt = datetime.fromisoformat(str(dt_raw).replace("Z", "+00:00"))
            if evt_dt.tzinfo is None:
                evt_dt = evt_dt.replace(tzinfo=ZoneInfo("America/New_York"))
            evt_dt = evt_dt.astimezone(ZoneInfo("America/New_York"))
        except Exception:
            continue

        impact = str(row.get("impact", "low")).lower()
        w = float(impact_w.get(impact, 1.0))
        if now_et < evt_dt <= future_cut and impact in {"high", "medium"}:
            upcoming.append(
                {
                    "time_et": evt_dt.strftime("%I:%M %p").lstrip("0"),
                    "event": str(row.get("event", "")),
                    "impact": impact.upper(),
                    "countdown": _countdown_label(int((evt_dt - now_et).total_seconds())),
                }
            )

        if not (past_cut <= evt_dt <= now_et):
            continue
        actual = _parse_macro_number(row.get("actual"))
        expected = _parse_macro_number(row.get("expected"))
        prior = _parse_macro_number(row.get("prior"))
        if actual is None or expected is None:
            continue
        surprise = float(actual - expected)
        denom = abs(expected) if abs(expected) > 1e-9 else max(abs(actual), 1.0)
        surprise_pct = float((surprise / denom) * 100.0)
        shock = float(abs(surprise_pct) * w)
        releases.append(
            {
                "When": evt_dt.strftime("%a %I:%M %p"),
                "Event": str(row.get("event", "")),
                "Impact": impact.upper(),
                "Actual": _fmt_econ_value(row.get("actual")),
                "Expected": _fmt_econ_value(row.get("expected")),
                "Prior": _fmt_econ_value(row.get("prior")),
                "Surprise %": surprise_pct,
                "Shock": shock,
                "Signed": surprise_pct * w,
            }
        )

    if releases:
        rel_df = pd.DataFrame(releases).sort_values("Shock", ascending=False)
        net_signed = float(rel_df["Signed"].sum())
        shock_avg = float(rel_df["Shock"].head(8).mean())
        recent = rel_df.head(10).copy()
    else:
        rel_df = pd.DataFrame(columns=["When", "Event", "Impact", "Actual", "Expected", "Prior", "Surprise %", "Shock", "Signed"])
        net_signed = 0.0
        shock_avg = 0.0
        recent = rel_df

    shock_regime = "High Shock" if shock_avg >= 35 else "Moderate Shock" if shock_avg >= 15 else "Calm"
    bias = "Upside Surprise" if net_signed >= 8 else "Downside Surprise" if net_signed <= -8 else "Balanced Surprise"
    return {
        "shock_regime": shock_regime,
        "bias": bias,
        "net_signed": net_signed,
        "recent": recent,
        "upcoming": upcoming[:6],
    }


def _render_regime_engine_panel(regime):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧠 Regime Engine</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not regime:
        st.info("Regime engine unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    score = int(regime.get("score", 0))
    r1, r2, r3 = st.columns([1, 1, 2])
    r1.metric("Regime Score", f"{score:+d}")
    r2.metric("State", regime.get("regime", "N/A"))
    r3.markdown(f"**Execution:** {regime.get('execution', 'N/A')}")
    st.progress(max(0.0, min(1.0, (score + 100) / 200)))

    comp = pd.DataFrame(regime.get("components", []))
    if not comp.empty:
        st.dataframe(comp, width="stretch", hide_index=True)
    st.caption(
        f"NQ vs DN: {regime.get('dn_distance', 0):+.0f} pts | "
        f"NQ vs GF: {regime.get('gf_distance', 0):+.0f} pts"
    )
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_dealer_forward_pressure_panel(payload):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧮 Dealer Forward Pressure</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not payload:
        st.info("Forward pressure unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    def _fmt_mm(v):
        av = abs(float(v))
        sign = "-" if float(v) < 0 else "+"
        return f"{sign}${av/1_000_000:.2f}M"

    scenarios = pd.DataFrame(payload.get("scenarios", []))
    if not scenarios.empty:
        show = scenarios.copy()
        show["Dealer Hedge Flow"] = show["Dealer Hedge Flow"].map(_fmt_mm)
        st.markdown(f"**Flow Regime:** `{payload.get('regime', 'N/A')}`")
        st.dataframe(show, width="stretch", hide_index=True)

    nodes = payload.get("nodes")
    if nodes is not None and not nodes.empty:
        nd = nodes.copy()
        nd["nq_strike"] = nd["nq_strike"].map(lambda v: round(float(v), 2))
        nd["gamma_unit"] = nd["gamma_unit"].map(lambda v: round(float(v), 2))
        nd["gex"] = nd["gex"].map(lambda v: round(float(v), 2))
        nd["oi"] = nd["oi"].map(lambda v: int(float(v)))
        nd = nd.rename(
            columns={
                "nq_strike": "NQ Strike",
                "gamma_unit": "Gamma Unit",
                "gex": "Net GEX",
                "oi": "Open Interest",
            }
        )
        st.markdown("**Highest-impact strike nodes**")
        st.dataframe(nd, width="stretch", hide_index=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_microstructure_panel(payload):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🔬 Microstructure Panel</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not payload:
        st.info("Microstructure unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("State", payload.get("state", "N/A"))
    m2.metric("5m RV", f"{payload.get('rv_5m_pct', 0):.3f}%")
    m3.metric("Range Ratio", f"{payload.get('range_ratio', 0):.2f}x")
    m4.metric("Vol Imbalance", f"{payload.get('vol_imb_pct', 0):+.1f}%")

    n1, n2, n3 = st.columns(3)
    n1.metric("12-bar Trend", f"{payload.get('trend_12_pct', 0):+.2f}%")
    n2.metric("VWAP Dev", f"{payload.get('vwap_dev_pts', 0):+.2f} pts")
    n3.metric("Volume z-score", f"{payload.get('vol_z', 0):+.2f}")
    st.caption(f"Open drive: {payload.get('open_drive', 'N/A')}")
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_cross_asset_driver_matrix_panel(payload):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🌐 Cross-Asset Driver Matrix</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not payload:
        st.info("Driver matrix unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    d1, d2, d3 = st.columns(3)
    d1.metric("Composite Pressure", f"{payload.get('composite', 0):+.2f}")
    d2.metric("Regime", payload.get("regime", "N/A"))
    d3.metric("Dominant Driver", payload.get("dominant", "N/A"))

    df = payload.get("rows")
    if df is not None and not df.empty:
        show = df.copy()
        show["Change"] = show["Change"].map(lambda v: f"{float(v):+.2f}")
        show["Signed Impact"] = show["Signed Impact"].map(lambda v: f"{float(v):+.2f}")
        show["Weight"] = show["Weight"].map(lambda v: f"{float(v):.2f}")
        st.dataframe(show[["Driver", "Bucket", "Change", "Weight", "Signed Impact"]], width="stretch", hide_index=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_event_surprise_panel(payload):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">⚡ Event Surprise Engine</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not payload:
        st.info("Event surprise data unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    e1, e2, e3 = st.columns(3)
    e1.metric("Shock Regime", payload.get("shock_regime", "N/A"))
    e2.metric("Surprise Bias", payload.get("bias", "N/A"))
    e3.metric("Net Signed Surprise", f"{payload.get('net_signed', 0):+.1f}")

    recent = payload.get("recent")
    if recent is not None and not recent.empty:
        show = recent.copy()
        show["Surprise %"] = show["Surprise %"].map(lambda v: f"{float(v):+.2f}%")
        show["Shock"] = show["Shock"].map(lambda v: f"{float(v):.1f}")
        st.markdown("**Recent releases (last ~36h)**")
        st.dataframe(show[["When", "Event", "Impact", "Actual", "Expected", "Prior", "Surprise %", "Shock"]], width="stretch", hide_index=True)
    else:
        st.caption("No releases with both Actual and Expected in the recent window.")

    upcoming = payload.get("upcoming", [])
    if upcoming:
        st.markdown("**Upcoming high/medium releases (next ~8h)**")
        st.dataframe(pd.DataFrame(upcoming), width="stretch", hide_index=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _freshness_class(status):
    s = str(status or "").lower()
    if s == "fresh":
        return "ok"
    if s in {"stale_soft", "unknown"}:
        return "warn"
    return "bad"


def _render_data_health_strip(nq_source, qqq_source, ratio_meta, data_0dte, market_data, finnhub_key):
    try:
        get_rss_news(finnhub_key)
    except Exception:
        pass
    options_health = get_dataset_freshness("options:QQQ", max_age_sec=180)
    econ_health = get_dataset_freshness("econ_calendar", max_age_sec=180)
    breadth_health = get_dataset_freshness("breadth_internals", max_age_sec=120)
    opening_health = get_dataset_freshness("opening_structure:NQ=F", max_age_sec=90)
    news_health = get_dataset_freshness("rss_news", max_age_sec=90)

    conf_mult = 1.0
    if data_0dte:
        conf_mult = float((data_0dte.get("data_meta", {}) or {}).get("confidence_multiplier", 1.0))
    ratio_meta = ratio_meta or {}
    ratio_val = float(ratio_meta.get("ratio", 0.0) or 0.0)
    ratio_raw = float(ratio_meta.get("raw_ratio", ratio_val) or ratio_val)
    ratio_unc = float(ratio_meta.get("uncertainty_pts", 0.0) or 0.0)
    ratio_conf = int(ratio_meta.get("confidence_score", 0) or 0)
    ratio_label = str(ratio_meta.get("confidence_label", "Low"))
    ratio_status = _ratio_health_status(ratio_label)

    items = [
        {
            "title": "NQ Feed",
            "value": nq_source,
            "sub": f"age {get_quote_age_label('NQ=F')}",
            "status": "fresh" if "schwab" in str(nq_source).lower() else "stale_soft",
        },
        {
            "title": "Options Chain",
            "value": str(options_health.get("status", "unknown")).replace("_", " ").title(),
            "sub": f"{options_health.get('source', 'unknown')} • age {options_health.get('latency_s', 'n/a')}s • x{conf_mult:.2f}",
            "status": options_health.get("status", "unknown"),
        },
        {
            "title": "QQQ Feed",
            "value": qqq_source,
            "sub": f"age {get_quote_age_label('QQQ')}",
            "status": "fresh" if "schwab" in str(qqq_source).lower() else "stale_soft",
        },
        {
            "title": "NQ↔QQQ Ratio",
            "value": f"{ratio_val:.4f}",
            "sub": f"raw {ratio_raw:.4f} • ±{ratio_unc:.0f} pts • {ratio_conf}%",
            "status": ratio_status,
        },
        {
            "title": "Economic Feed",
            "value": str(econ_health.get("status", "unknown")).replace("_", " ").title(),
            "sub": f"age {econ_health.get('latency_s', 'n/a')}s",
            "status": econ_health.get("status", "unknown"),
        },
        {
            "title": "Breadth/Internals",
            "value": str(breadth_health.get("status", "unknown")).replace("_", " ").title(),
            "sub": f"age {breadth_health.get('latency_s', 'n/a')}s",
            "status": breadth_health.get("status", "unknown"),
        },
        {
            "title": "News Feed",
            "value": str(news_health.get("status", "unknown")).replace("_", " ").title(),
            "sub": f"age {news_health.get('latency_s', 'n/a')}s • VIX {float((market_data.get('vix', {}) or {}).get('price', 0) or 0):.2f}",
            "status": news_health.get("status", "unknown"),
        },
        {
            "title": "Opening Model",
            "value": str(opening_health.get("status", "unknown")).replace("_", " ").title(),
            "sub": f"age {opening_health.get('latency_s', 'n/a')}s",
            "status": opening_health.get("status", "unknown"),
        },
    ]

    for i in range(0, len(items), 4):
        row = items[i : i + 4]
        cols = st.columns(4)
        for c_idx, col in enumerate(cols):
            if c_idx >= len(row):
                continue
            item = row[c_idx]
            status_text = html.escape(str(item.get("status", "unknown")).upper())
            value_text = html.escape(str(item.get("value", "")))
            sub_text = html.escape(str(item.get("sub", "")))
            title_text = html.escape(str(item.get("title", "")))
            s_class = _freshness_class(item.get("status"))
            with col:
                st.markdown(
                    f"""
                    <div class="health-card">
                        <p class="title">{title_text}</p>
                        <p class="value">{value_text}</p>
                        <span class="status-pill {s_class}">{status_text}</span>
                        <p class="sub">{sub_text}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def _render_trade_plan_panel(playbook, data_0dte, nq_now, event_risk):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧭 Trade Plan (Session)</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not playbook or not data_0dte:
        st.info("Trade plan unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    regime = playbook.get("regime", "N/A")
    bias = playbook.get("bias", "N/A")
    em = float(data_0dte.get("nq_em_full", 0))
    p_wall = float(data_0dte.get("p_wall", 0))
    p_floor = float(data_0dte.get("p_floor", 0))
    dn = float(data_0dte.get("dn_nq", 0))
    gf = float(data_0dte.get("g_flip_nq", 0))
    s_wall = float(data_0dte.get("s_wall", p_wall))
    s_floor = float(data_0dte.get("s_floor", p_floor))

    if "Short" in bias:
        entry = f"{p_wall - 10:.0f}–{p_wall + 15:.0f}"
        target = f"{dn:.0f} then {p_floor:.0f}"
        invalidation = f">{s_wall + 15:.0f}"
        plan_line = f"Fade strength into call wall while above GF ({gf:.0f}) risk remains elevated."
    elif "Long" in bias:
        entry = f"{p_floor - 15:.0f}–{p_floor + 10:.0f}"
        target = f"{dn:.0f} then {p_wall:.0f}"
        invalidation = f"<{s_floor - 15:.0f}"
        plan_line = f"Buy responsive dips into put floor; target DN reclaim before wall test."
    else:
        entry = f"Break {gf:.0f} / {dn:.0f}"
        target = f"±{em * 0.5:.0f} around spot"
        invalidation = "No follow-through after break"
        plan_line = "Neutral regime. Wait for break-confirm-retest around GF/DN before sizing."

    next_event = None
    if event_risk:
        for ev in event_risk.get("next_events", []):
            if str(ev.get("impact", "")).lower() in {"high", "medium"}:
                next_event = ev
                break
    catalyst = "No high/medium events soon"
    if next_event:
        catalyst = (
            f"{next_event.get('time_et', '')} {next_event.get('event', '')} "
            f"({_countdown_label(next_event.get('seconds_to', 0))})"
        )

    lockout_txt = "Active" if event_risk and event_risk.get("lockout_active") else "Inactive"
    lockout_cls = "bad" if lockout_txt == "Active" else "ok"

    st.markdown(
        f"""
        <div class="trade-plan-grid">
            <div class="trade-plan-stat"><p class="k">Regime / Bias</p><p class="v">{html.escape(regime)} • {html.escape(bias)}</p></div>
            <div class="trade-plan-stat"><p class="k">Entry Zone</p><p class="v">{entry}</p></div>
            <div class="trade-plan-stat"><p class="k">Targets</p><p class="v">{target}</p></div>
            <div class="trade-plan-stat"><p class="k">Invalidation</p><p class="v">{invalidation}</p></div>
        </div>
        <div class="trade-plan-grid" style="grid-template-columns: 1.1fr 1.3fr 0.9fr 0.7fr;">
            <div class="trade-plan-stat"><p class="k">Expected Move</p><p class="v">±{em:.0f} pts</p></div>
            <div class="trade-plan-stat"><p class="k">Next Catalyst</p><p class="v">{html.escape(catalyst)}</p></div>
            <div class="trade-plan-stat"><p class="k">Lockout</p><p class="v"><span class="status-pill {lockout_cls}">{lockout_txt}</span></p></div>
            <div class="trade-plan-stat"><p class="k">Spot</p><p class="v">{nq_now:.2f}</p></div>
        </div>
        <div class="trade-plan-note"><b>Plan:</b> {html.escape(plan_line)}</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_live_countdown_table(rows, height=360):
    if not rows:
        st.info("No upcoming events in this horizon.")
        return

    table_rows = []
    for r in rows:
        when_txt = html.escape(str(r.get("when_et", "")))
        impact_txt = html.escape(str(r.get("impact", "")))
        type_txt = html.escape(str(r.get("kind", "")))
        event_txt = html.escape(str(r.get("event", "")))
        source_txt = html.escape(str(r.get("source", "")))
        sec = int(r.get("seconds_to", 0))
        table_rows.append(
            f"""
            <tr>
              <td>{when_txt}</td>
              <td class="live-countdown" data-seconds="{sec}"></td>
              <td>{impact_txt}</td>
              <td>{type_txt}</td>
              <td>{event_txt}</td>
              <td>{source_txt}</td>
            </tr>
            """
        )

    table_html = "".join(table_rows)
    widget_id = f"countdown_{int(time.time() * 1000)}"
    html_block = f"""
    <div id="{widget_id}">
      <style>
        #{widget_id} table {{
          width: 100%;
          border-collapse: collapse;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          font-size: 13px;
          color: #dce6f3;
        }}
        #{widget_id} thead th {{
          text-align: left;
          background: #131923;
          border: 1px solid #2c3646;
          padding: 7px 8px;
          color: #9fb0c7;
          font-weight: 700;
        }}
        #{widget_id} tbody td {{
          border: 1px solid #243043;
          padding: 7px 8px;
          background: #111722;
          vertical-align: top;
        }}
        #{widget_id} tbody tr:nth-child(odd) td {{
          background: #0f1520;
        }}
        #{widget_id} .live-countdown {{
          font-weight: 700;
          color: #8ff3c3;
          white-space: nowrap;
        }}
      </style>
      <table>
        <thead>
          <tr>
            <th>When (ET)</th>
            <th>Countdown</th>
            <th>Impact</th>
            <th>Type</th>
            <th>Event</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {table_html}
        </tbody>
      </table>
      <script>
        (function() {{
          const root = document.getElementById("{widget_id}");
          if (!root) return;

          function fmt(sec) {{
            const dir = sec >= 0 ? "T-" : "T+";
            let s = Math.abs(sec);
            const h = Math.floor(s / 3600);
            s -= h * 3600;
            const m = Math.floor(s / 60);
            const ss = s - m * 60;
            if (h > 0) return `${{dir}}${{h}}h ${{String(m).padStart(2, "0")}}m`;
            if (m > 0) return `${{dir}}${{m}}m ${{String(ss).padStart(2, "0")}}s`;
            return `${{dir}}${{ss}}s`;
          }}

          function tick() {{
            const nodes = root.querySelectorAll(".live-countdown[data-seconds]");
            nodes.forEach((el) => {{
              const sec = parseInt(el.dataset.seconds || "0", 10);
              if (Number.isNaN(sec)) {{
                el.textContent = "-";
                return;
              }}
              el.textContent = fmt(sec);
              el.dataset.seconds = String(sec - 1);
            }});
          }}

          tick();
          if (root._timer) clearInterval(root._timer);
          root._timer = setInterval(tick, 1000);
        }})();
      </script>
    </div>
    """
    components.html(html_block, height=height, scrolling=True)


def _build_morning_playbook(data_0dte, data_weekly, nq_now, event_risk):
    if not data_0dte:
        return {}

    dn_distance = float(nq_now - data_0dte["dn_nq"])
    gf_distance = float(nq_now - data_0dte["g_flip_nq"])
    regime = "Negative Gamma" if gf_distance > 0 else "Positive Gamma"
    if abs(dn_distance) > 200:
        bias = "Short Bias" if dn_distance > 0 else "Long Bias"
    else:
        bias = "Neutral"

    level_conf = data_0dte.get("level_confidence", {})
    base_candidates = [
        ("Primary Wall", float(data_0dte["p_wall"])),
        ("Secondary Wall", float(data_0dte["s_wall"])),
        ("Target Resistance", float(data_0dte["p_wall"] + 35)),
        ("Gamma Flip", float(data_0dte["g_flip_nq"])),
        ("Delta Neutral", float(data_0dte["dn_nq"])),
        ("Primary Floor", float(data_0dte["p_floor"])),
        ("Secondary Floor", float(data_0dte["s_floor"])),
        ("Target Support", float(data_0dte["p_floor"] - 35)),
        ("Lower 0.25σ", float(nq_now - data_0dte.get("nq_em_full", 0) * 0.25)),
        ("Lower 0.50σ", float(nq_now - data_0dte.get("nq_em_full", 0) * 0.50)),
        ("Upper 0.25σ", float(nq_now + data_0dte.get("nq_em_full", 0) * 0.25)),
        ("Upper 0.50σ", float(nq_now + data_0dte.get("nq_em_full", 0) * 0.50)),
    ]

    rows = []
    for lvl, px in base_candidates:
        c = level_conf.get(lvl, {})
        score = int(c.get("score", 40))
        dist = float(px - nq_now)
        rows.append(
            {
                "level": lvl,
                "price": float(px),
                "distance": dist,
                "score": score,
            }
        )

    longs = sorted(
        [r for r in rows if r["distance"] <= 0],
        key=lambda r: (-r["score"], abs(r["distance"])),
    )[:3]
    shorts = sorted(
        [r for r in rows if r["distance"] >= 0],
        key=lambda r: (-r["score"], abs(r["distance"])),
    )[:3]

    no_trade = []
    if event_risk and event_risk.get("lockout_active"):
        ev = event_risk.get("lockout_event", {}) or {}
        no_trade.append(f"Event lockout: {ev.get('event', 'High-impact release')} ({_countdown_label(ev.get('seconds_to', 0))})")
    if abs(gf_distance) <= 15:
        no_trade.append("Price is within 15 pts of Gamma Flip (high whipsaw risk).")
    freshness = str((data_0dte.get("data_meta", {}) or {}).get("options_freshness", "unknown"))
    if freshness != "fresh":
        no_trade.append(f"Options chain freshness is {freshness}; reduce trust/size.")
    if data_weekly:
        dn_spread = abs(float(data_0dte["dn_nq"] - data_weekly["dn_nq"]))
        if dn_spread > 150:
            no_trade.append(f"0DTE/Weekly DN spread is {dn_spread:.0f} pts (chop regime risk).")
    if not no_trade:
        no_trade.append("No hard lockout right now. Follow event risk timer and opening structure.")

    catalysts = []
    for ev in (event_risk or {}).get("next_events", [])[:6]:
        if ev.get("impact") not in {"high", "medium"}:
            continue
        catalysts.append(
            {
                "time_et": ev.get("time_et", ""),
                "event": ev.get("event", ""),
                "impact": str(ev.get("impact", "")).upper(),
                "countdown": _countdown_label(ev.get("seconds_to", 0)),
            }
        )

    return {
        "regime": regime,
        "bias": bias,
        "dn_distance": dn_distance,
        "gf_distance": gf_distance,
        "long_setups": longs,
        "short_setups": shorts,
        "no_trade": no_trade,
        "catalysts": catalysts,
    }


def _render_morning_playbook(playbook, nq_source, options_freshness, econ_freshness, breadth_freshness):
    if not playbook:
        st.info("Morning playbook unavailable.")
        return
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">☀️ Morning Playbook</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1.05, 1.2, 1.2])
    with c1:
        st.markdown(f"**Regime:** `{playbook['regime']}`")
        st.markdown(f"**Bias:** `{playbook['bias']}`")
        st.markdown(f"**NQ vs DN:** `{playbook['dn_distance']:+.0f} pts`")
        st.markdown(f"**NQ vs GF:** `{playbook['gf_distance']:+.0f} pts`")
        st.markdown("**Data Freshness**")
        st.markdown(
            f"- Price: `{nq_source}`\n"
            f"- Options: `{options_freshness}`\n"
            f"- Econ: `{econ_freshness}`\n"
            f"- Breadth: `{breadth_freshness}`"
        )
    with c2:
        st.markdown("**Top Long Levels**")
        for r in playbook.get("long_setups", []):
            st.markdown(
                f"- `{r['level']}` {r['price']:.2f} "
                f"({r['distance']:+.0f} pts, score {r['score']})"
            )
        st.markdown("**Top Short Levels**")
        for r in playbook.get("short_setups", []):
            st.markdown(
                f"- `{r['level']}` {r['price']:.2f} "
                f"({r['distance']:+.0f} pts, score {r['score']})"
            )
    with c3:
        st.markdown("**No-Trade Conditions**")
        for item in playbook.get("no_trade", [])[:4]:
            st.markdown(f"- {item}")
        st.markdown("**Today's Catalysts**")
        cats = playbook.get("catalysts", [])
        if cats:
            for ev in cats[:5]:
                st.markdown(
                    f"- `{ev['time_et']}` {ev['event']} ({ev['impact']}, {ev['countdown']})"
                )
        else:
            st.markdown("- No high/medium events in the near window.")
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_level_quality_panel(data_0dte, data_weekly, nq_now, level_interactions_df=None):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🎯 Level Quality Engine</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not data_0dte:
        st.info("Level quality unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    level_conf = data_0dte.get("level_confidence", {})
    rows = [
        ("Delta Neutral", float(data_0dte["dn_nq"])),
        ("Gamma Flip", float(data_0dte["g_flip_nq"])),
        ("Primary Wall", float(data_0dte["p_wall"])),
        ("Primary Floor", float(data_0dte["p_floor"])),
        ("Secondary Wall", float(data_0dte["s_wall"])),
        ("Secondary Floor", float(data_0dte["s_floor"])),
    ]
    weekly_refs = []
    if data_weekly:
        weekly_refs = [
            float(data_weekly["dn_nq"]),
            float(data_weekly["g_flip_nq"]),
            float(data_weekly["p_wall"]),
            float(data_weekly["p_floor"]),
            float(data_weekly["s_wall"]),
            float(data_weekly["s_floor"]),
        ]

    interaction_map = {}
    if level_interactions_df is not None and not level_interactions_df.empty:
        for _, row in level_interactions_df.iterrows():
            interaction_map[str(row.get("Level", ""))] = {
                "touches": int(row.get("Touches", 0)),
                "rejections": int(row.get("Rejections", 0)),
                "breaks_up": int(row.get("Breaks Up", 0)),
                "breaks_down": int(row.get("Breaks Down", 0)),
            }

    quality_rows = []
    for name, px in rows:
        lc = (level_conf.get(name, {}) or {})
        base = int(lc.get("score", 40))
        parts = lc.get("components", {}) or {}
        liq_part = float(parts.get("liq_strength", 0.0))
        gex_part = float(parts.get("gex_strength", 0.0))
        oi_part = float(parts.get("oi_strength", 0.0))
        struct_part = float(parts.get("structure_strength", 0.0))
        dist = abs(float(px - nq_now))
        if dist <= 60:
            dist_score = 92
        elif dist <= 140:
            dist_score = 78
        elif dist <= 240:
            dist_score = 58
        else:
            dist_score = 36

        confl_score = 35
        nearest_weekly = None
        if weekly_refs:
            nearest_weekly = min(abs(px - w) for w in weekly_refs)
            if nearest_weekly <= 8:
                confl_score = 95
            elif nearest_weekly <= 20:
                confl_score = 82
            elif nearest_weekly <= 40:
                confl_score = 64
            elif nearest_weekly <= 80:
                confl_score = 50

        interaction = interaction_map.get(name, {})
        touches = int(interaction.get("touches", 0))
        rejections = int(interaction.get("rejections", 0))
        breaks = int(interaction.get("breaks_up", 0)) + int(interaction.get("breaks_down", 0))
        reaction_score = 30
        if touches > 0:
            reaction_score = min(98, 35 + (touches * 8) + (rejections * 6) - (breaks * 3))

        options_score = int(max(0, min(100, round((base * 0.80) + (dist_score * 0.20)))))
        final_score = int(
            max(
                0,
                min(
                    100,
                    round((options_score * 0.55) + (confl_score * 0.28) + (reaction_score * 0.17)),
                ),
            )
        )
        label = "High" if final_score >= 70 else "Medium" if final_score >= 45 else "Low"
        component_txt = f"Liq {liq_part:.0%} • GEX {gex_part:.0%} • OI {oi_part:.0%} • Struct {struct_part:.0%}"
        quality_rows.append(
            {
                "Level": name,
                "Price": round(px, 2),
                "Dist (pts)": round(px - nq_now, 1),
                "Options": options_score,
                "Confluence": confl_score,
                "Reaction": reaction_score,
                "Weekly Δ": "-" if nearest_weekly is None else round(nearest_weekly, 1),
                "Inputs": component_txt,
                "Final Score": final_score,
                "Quality": label,
            }
        )

    qdf = pd.DataFrame(quality_rows).sort_values(["Final Score", "Dist (pts)"], ascending=[False, True])
    st.dataframe(qdf, width="stretch", hide_index=True)
    top_rows = qdf.head(3)
    top_txt = ", ".join(f"{r['Level']} ({int(r['Final Score'])})" for _, r in top_rows.iterrows())
    st.caption(
        "Final Score = 55% options confidence + 28% multi-timeframe confluence + 17% reaction profile. "
        f"Highest confidence now: {top_txt}"
    )
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_reference_levels_panel(data_0dte, reference_levels, opening_structure, nq_now, event_risk):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧷 Day-Trader Reference Levels</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not data_0dte:
        st.info("Reference levels unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    level_conf = data_0dte.get("level_confidence", {}) or {}
    em_full = float(data_0dte.get("nq_em_full", 0) or 0)
    inval_pad = max(8.0, em_full * 0.08)

    rows = []

    def add_level(name, price, group, base):
        if price is None:
            return
        try:
            px = float(price)
        except Exception:
            return
        rows.append(
            {
                "Level": name,
                "Type": group,
                "Price": px,
                "Base": int(max(0, min(100, base))),
            }
        )

    # Options-derived levels.
    add_level("Primary Wall", data_0dte.get("p_wall"), "Options", int((level_conf.get("Primary Wall", {}) or {}).get("score", 65)))
    add_level("Secondary Wall", data_0dte.get("s_wall"), "Options", int((level_conf.get("Secondary Wall", {}) or {}).get("score", 55)))
    add_level("Gamma Flip", data_0dte.get("g_flip_nq"), "Options", int((level_conf.get("Gamma Flip", {}) or {}).get("score", 58)))
    add_level("Delta Neutral", data_0dte.get("dn_nq"), "Options", int((level_conf.get("Delta Neutral", {}) or {}).get("score", 60)))
    add_level("Primary Floor", data_0dte.get("p_floor"), "Options", int((level_conf.get("Primary Floor", {}) or {}).get("score", 65)))
    add_level("Secondary Floor", data_0dte.get("s_floor"), "Options", int((level_conf.get("Secondary Floor", {}) or {}).get("score", 55)))

    # Profile + VWAP stack.
    ref = reference_levels or {}
    profile = ref.get("profile", {}) or {}
    vwap = ref.get("vwap", {}) or {}
    pools = ref.get("pools", {}) or {}
    add_level("POC", profile.get("poc"), "Profile", 76)
    add_level("VAH", profile.get("vah"), "Profile", 72)
    add_level("VAL", profile.get("val"), "Profile", 72)
    add_level("Session VWAP", vwap.get("session"), "VWAP", 74)
    add_level("VWAP +1σ", vwap.get("session_upper_1"), "VWAP", 64)
    add_level("VWAP -1σ", vwap.get("session_lower_1"), "VWAP", 64)
    add_level("Weekly VWAP", vwap.get("week"), "VWAP", 68)
    add_level("Event VWAP", vwap.get("event"), "VWAP", 66)

    # Liquidity pools.
    add_level("Prior Day High", pools.get("prior_day_high"), "Liquidity", 68)
    add_level("Prior Day Low", pools.get("prior_day_low"), "Liquidity", 68)
    add_level("Overnight High", pools.get("overnight_high"), "Liquidity", 62)
    add_level("Overnight Low", pools.get("overnight_low"), "Liquidity", 62)

    # Open-context levels.
    op = opening_structure or {}
    add_level("OR15 High", op.get("opening_range_15m_high"), "Opening", 66)
    add_level("OR15 Low", op.get("opening_range_15m_low"), "Opening", 66)
    add_level("IB High", op.get("initial_balance_high"), "Opening", 63)
    add_level("IB Low", op.get("initial_balance_low"), "Opening", 63)

    if not rows:
        st.info("Reference levels unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    df = pd.DataFrame(rows).drop_duplicates(subset=["Level", "Price"]).reset_index(drop=True)
    cluster_threshold = max(8.0, nq_now * 0.00035)
    final_rows = []
    lockout_penalty = 6 if event_risk and event_risk.get("lockout_active") else 0
    for i, row in df.iterrows():
        px = float(row["Price"])
        base = int(row["Base"])
        dist = abs(px - nq_now)
        if dist <= 35:
            prox = 95
        elif dist <= 90:
            prox = 82
        elif dist <= 180:
            prox = 64
        else:
            prox = 42

        near = df[(df.index != i) & ((df["Price"] - px).abs() <= cluster_threshold)]
        cluster_score = min(96, 50 + (len(near) * 9))
        final = int(round((0.58 * base) + (0.27 * prox) + (0.15 * cluster_score) - lockout_penalty))
        final = int(max(0, min(100, final)))

        if px > nq_now + 2:
            side = "Resistance"
            invalidation = px + inval_pad
        elif px < nq_now - 2:
            side = "Support"
            invalidation = px - inval_pad
        else:
            side = "Pivot"
            invalidation = px + inval_pad

        final_rows.append(
            {
                "Level": row["Level"],
                "Type": row["Type"],
                "Side": side,
                "Price": round(px, 2),
                "Dist (pts)": round(px - nq_now, 1),
                "Base": base,
                "Confluence": int(cluster_score),
                "Score": final,
                "Invalidation": round(float(invalidation), 2),
            }
        )

    out = pd.DataFrame(final_rows).sort_values(["Score", "Dist (pts)"], ascending=[False, True]).reset_index(drop=True)
    top3 = out.head(3)
    m1, m2, m3 = st.columns(3)
    if not top3.empty:
        m1.metric("Top 1", f"{top3.iloc[0]['Level']}", f"{int(top3.iloc[0]['Score'])} pts")
    if len(top3) > 1:
        m2.metric("Top 2", f"{top3.iloc[1]['Level']}", f"{int(top3.iloc[1]['Score'])} pts")
    if len(top3) > 2:
        m3.metric("Top 3", f"{top3.iloc[2]['Level']}", f"{int(top3.iloc[2]['Score'])} pts")

    st.dataframe(out.head(12), width="stretch", hide_index=True)
    anchor = (reference_levels or {}).get("vwap", {}).get("event_anchor")
    anchor_txt = "None"
    if anchor and anchor.get("event"):
        anchor_txt = f"{anchor.get('event')} @ {anchor.get('time_et')}"
    st.caption(
        f"Score = 58% base + 27% usability (distance) + 15% nearby confluence. "
        f"Cluster threshold: {cluster_threshold:.1f} pts. Event VWAP anchor: {anchor_txt}."
    )
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_opening_structure_panel(opening):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">⏱ Opening Auction Context</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not opening:
        st.info("Opening structure data unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Overnight High", f"{opening.get('overnight_high', 0):.2f}" if opening.get("overnight_high") else "N/A")
    o2.metric("Overnight Low", f"{opening.get('overnight_low', 0):.2f}" if opening.get("overnight_low") else "N/A")
    o3.metric("Globex VWAP", f"{opening.get('globex_vwap', 0):.2f}" if opening.get("globex_vwap") else "N/A")
    o4.metric("RTH Open", f"{opening.get('rth_open', 0):.2f}" if opening.get("rth_open") else "N/A")

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("15m OR High", f"{opening.get('opening_range_15m_high', 0):.2f}" if opening.get("opening_range_15m_high") else "N/A")
    p2.metric("15m OR Low", f"{opening.get('opening_range_15m_low', 0):.2f}" if opening.get("opening_range_15m_low") else "N/A")
    p3.metric("Gap", f"{opening.get('gap_points', 0):+.2f}" if opening.get("gap_points") is not None else "N/A", f"{opening.get('gap_pct', 0):+.2f}%" if opening.get("gap_pct") is not None else None)
    p4.metric("Minutes Since Open", f"{int(opening.get('minutes_since_open', 0))}m")

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Open Type", str(opening.get("opening_type", "N/A")))
    q2.metric("VWAP Relation", str(opening.get("vwap_relation", "N/A")))
    q3.metric("OR15 State", str(opening.get("opening_range_15m_state", "N/A")))
    q4.metric("Drive", str(opening.get("open_drive_signal", "N/A")))

    ib_complete = opening.get("initial_balance_complete", False)
    ib_status = "Complete" if ib_complete else "Building"
    ib_txt = (
        f"`{opening.get('initial_balance_high', 0):.2f}` / `{opening.get('initial_balance_low', 0):.2f}`"
        if opening.get("initial_balance_high") and opening.get("initial_balance_low")
        else "N/A"
    )
    setup_hint = opening.get("setup_hint", "Wait")
    auction_score = 50
    if str(opening.get("opening_type", "")).lower().startswith("trend"):
        auction_score += 16
    elif str(opening.get("opening_type", "")).lower().startswith("reversal"):
        auction_score += 8
    if str(opening.get("vwap_relation", "")).lower().startswith("above"):
        auction_score += 8
    elif str(opening.get("vwap_relation", "")).lower().startswith("below"):
        auction_score -= 8
    if str(opening.get("opening_range_15m_state", "")).lower().startswith("breakout"):
        auction_score += 8
    auction_score = int(max(0, min(100, auction_score)))
    st.markdown(
        f"**Gap Type:** `{opening.get('gap_type', 'N/A')}` • "
        f"**IB:** `{ib_status}` ({ib_txt}) • "
        f"**Setup Hint:** `{setup_hint}` • "
        f"**Auction Quality:** `{auction_score}/100`"
    )
    st.caption(f"{opening.get('opening_note', '')} • asof {opening.get('asof_et', 'n/a')}")
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_event_risk_panel(event_risk):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🚨 Event-Risk Engine</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not event_risk:
        st.info("Event-risk data unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    if event_risk.get("lockout_active"):
        lock = event_risk.get("lockout_event", {}) or {}
        st.error(
            f"Risk lockout active: {lock.get('event', 'High-impact event')} "
            f"({lock.get('time_et', '')}, {_countdown_label(lock.get('seconds_to', 0))})."
        )
    else:
        nh = event_risk.get("next_high")
        if nh:
            st.warning(
                f"Next high-impact event: {nh.get('event', 'N/A')} at {nh.get('time_et', 'N/A')} "
                f"({_countdown_label(nh.get('seconds_to', 0))})."
            )
        else:
            st.success("No high-impact releases in the active horizon.")

    st.caption(
        f"Today: {event_risk.get('today_high_count', 0)} high-impact, "
        f"{event_risk.get('today_medium_count', 0)} medium-impact events. "
        f"Total monitored: {event_risk.get('total_events', 0)}."
    )

    upcoming = event_risk.get("next_events", [])
    if upcoming:
        rows = []
        for e in upcoming[:10]:
            rows.append(
                {
                    "when_et": f"{e.get('date_et', '')} {e.get('time_et', '')}",
                    "seconds_to": int(e.get("seconds_to", 0)),
                    "impact": str(e.get("impact", "")).upper(),
                    "kind": e.get("kind", ""),
                    "event": e.get("event", ""),
                    "source": e.get("source", ""),
                }
            )
        _render_live_countdown_table(rows, height=360)
    else:
        st.info("No upcoming events in this horizon.")
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_breadth_internals_panel(breadth_data, nq_day_change_pct, es_change_pct, market_data):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📡 Breadth & Internals (Futures Context)</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not breadth_data:
        st.info("Breadth/internals unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    macro_cols = st.columns(5)
    vix = (market_data.get("vix", {}) or {})
    vvix = (market_data.get("vvix", {}) or {})
    dxy = (market_data.get("dxy", {}) or {})
    tnx = (market_data.get("10y", {}) or {})
    risk_score = 0
    try:
        risk_score += 1 if float(vix.get("price", 0) or 0) < 18 else -1
        risk_score += 1 if float(vvix.get("price", 0) or 0) < 95 else -1
        risk_score += 1 if float(dxy.get("change_pct", 0) or 0) <= 0 else -1
        risk_score += 1 if float(tnx.get("change", 0) or 0) <= 0 else -1
    except Exception:
        risk_score = 0
    risk_regime = "Risk-On" if risk_score >= 2 else "Risk-Off" if risk_score <= -1 else "Mixed"

    macro_cols[0].metric(
        "VIX",
        f"{float(vix.get('price', 0) or 0):.2f}" if vix.get("price") else "N/A",
        f"{float(vix.get('change_pct', 0) or 0):+.2f}%",
    )
    macro_cols[1].metric(
        "VVIX",
        f"{float(vvix.get('price', 0) or 0):.2f}" if vvix.get("price") else "N/A",
        f"{float(vvix.get('change_pct', 0) or 0):+.2f}%",
    )
    macro_cols[2].metric(
        "DXY",
        f"{float(dxy.get('price', 0) or 0):.2f}" if dxy.get("price") else "N/A",
        f"{float(dxy.get('change_pct', 0) or 0):+.2f}%",
    )
    macro_cols[3].metric(
        "US10Y",
        f"{float(tnx.get('price', 0) or 0):.2f}%" if tnx.get("price") else "N/A",
        f"{float(tnx.get('change', 0) or 0):+.2f}",
    )
    macro_cols[4].metric("Macro Regime", risk_regime, f"score {risk_score:+d}")

    nq_snap = breadth_data.get("NQ", {}) or {}
    es_snap = breadth_data.get("ES", {}) or {}
    p1, p2 = st.columns(2)
    nq_part = float(nq_snap.get("participation_score", 0.0) or 0.0)
    es_part = float(es_snap.get("participation_score", 0.0) or 0.0)
    p1.metric(
        "NQ Participation (-2..+2)",
        f"{nq_part:+.2f}",
        f"{float(nq_snap.get('up_pct', 0.0) or 0.0):.0f}% up / {float(nq_snap.get('down_pct', 0.0) or 0.0):.0f}% down",
    )
    p1.caption(str(nq_snap.get("participation_label", "Balanced Participation")))
    p2.metric(
        "ES Participation (-2..+2)",
        f"{es_part:+.2f}",
        f"{float(es_snap.get('up_pct', 0.0) or 0.0):.0f}% up / {float(es_snap.get('down_pct', 0.0) or 0.0):.0f}% down",
    )
    p2.caption(str(es_snap.get("participation_label", "Balanced Participation")))

    def _render_snapshot_card(name, snap, future_change):
        if not snap:
            st.info(f"{name}: unavailable")
            return
        adv = int(snap.get("advancers", 0))
        dec = int(snap.get("decliners", 0))
        breadth_pct = float(snap.get("breadth_pct", 0.0))
        ad_line = int(snap.get("ad_line", 0))
        vold_ratio = snap.get("vold_ratio")
        trin_proxy = snap.get("trin_proxy")
        tick_proxy = snap.get("tick_proxy")

        st.markdown(f"**{name}**")
        a1, a2, a3 = st.columns(3)
        a1.metric("Adv / Dec", f"{adv} / {dec}")
        a2.metric("Breadth %", f"{breadth_pct:.1f}%")
        a3.metric("A/D Line", f"{ad_line:+d}")

        b1, b2, b3 = st.columns(3)
        b1.metric("Up/Down Vol", f"{vold_ratio:.2f}" if vold_ratio is not None else "N/A")
        b2.metric("TRIN Proxy", f"{trin_proxy:.2f}" if trin_proxy is not None else "N/A")
        b3.metric("TICK Proxy", f"{tick_proxy:+.0f}" if tick_proxy is not None else "N/A")

        divergence = "Aligned"
        if future_change > 0 and breadth_pct < 50:
            divergence = "Bearish divergence"
        elif future_change < 0 and breadth_pct > 50:
            divergence = "Bullish divergence"
        st.caption(f"{snap.get('label', name)} • Futures move {future_change:+.2f}% • {divergence}")

    c1, c2 = st.columns(2)
    with c1:
        _render_snapshot_card("NQ Internals", breadth_data.get("NQ", {}), nq_day_change_pct)
    with c2:
        _render_snapshot_card("ES Internals", breadth_data.get("ES", {}), es_change_pct)

    sectors = breadth_data.get("sectors", [])
    if sectors:
        sec_df = pd.DataFrame(sectors).head(8)
        fig = go.Figure(
            data=[
                go.Bar(
                    x=sec_df["avg_change_pct"],
                    y=sec_df["sector"],
                    orientation="h",
                    marker_color=[
                        "#34d399" if v > 0 else "#f87171" if v < 0 else "#94a3b8"
                        for v in sec_df["avg_change_pct"]
                    ],
                    text=[f"{v:+.2f}%" for v in sec_df["avg_change_pct"]],
                    textposition="outside",
                )
            ]
        )
        fig.update_layout(
            template="plotly_dark",
            height=260,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis_title="Avg % Change",
            yaxis_title="Sector",
        )
        st.markdown("**Nasdaq Sector Pulse (equal-weight)**")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_cot_dealer_panel(cot_payload):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🏦 COT Dealer/Intermediary Positioning (Weekly)</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not cot_payload or not cot_payload.get("markets"):
        st.info("COT dealer data unavailable.")
        st.caption("Source: CFTC weekly financial futures (TFF).")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    age_days = cot_payload.get("age_days")
    asof = cot_payload.get("asof_date", "n/a")
    status = cot_payload.get("status", "unknown")
    st.caption(
        f"As-of (report date): {asof} | age: {age_days if age_days is not None else 'n/a'} days | "
        f"status: {status} | source: {cot_payload.get('source', 'CFTC')}"
    )

    rows = []
    for code in ["NQ", "ES", "YM", "RTY"]:
        m = (cot_payload.get("markets", {}) or {}).get(code)
        if not m:
            continue
        rows.append(
            {
                "Market": f"{m.get('label', code)} ({code})",
                "Dealer Net": f"{int(m.get('net', 0)):+,}",
                "Net % OI": f"{float(m.get('net_pct_oi', 0.0)):+.2f}%" if m.get("net_pct_oi") is not None else "n/a",
                "WoW Δ": f"{int(m.get('wow_change', 0)):+,}" if m.get("wow_change") is not None else "n/a",
                "Bias": str(m.get("bias", "n/a")),
                "Score (-2..+2)": f"{float(m.get('score', 0.0)):+.2f}",
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    nqs = (cot_payload.get("markets", {}) or {}).get("NQ", {}).get("score")
    ess = (cot_payload.get("markets", {}) or {}).get("ES", {}).get("score")
    c1, c2, c3 = st.columns(3)
    c1.metric("NQ Dealer Score", f"{float(nqs):+.2f}" if nqs is not None else "n/a")
    c2.metric("ES Dealer Score", f"{float(ess):+.2f}" if ess is not None else "n/a")
    if nqs is not None and ess is not None:
        blend = (float(nqs) + float(ess)) / 2.0
        regime = "Supportive" if blend > 0.35 else "Defensive" if blend < -0.35 else "Neutral"
        c3.metric("Dealer Risk Regime", regime, f"{blend:+.2f}")
    else:
        c3.metric("Dealer Risk Regime", "n/a")

    st.caption("Interpretation: positive score = dealers net long, negative = net short. Weekly, not intraday.")
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_overview_reference_snapshot(data_0dte, nq_now):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📍 Key References (Compact)</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not data_0dte:
        st.info("Reference levels unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return
    rows = [
        ("Primary Wall", float(data_0dte.get("p_wall", nq_now))),
        ("Gamma Flip", float(data_0dte.get("g_flip_nq", nq_now))),
        ("Delta Neutral", float(data_0dte.get("dn_nq", nq_now))),
        ("Primary Floor", float(data_0dte.get("p_floor", nq_now))),
        ("Secondary Wall", float(data_0dte.get("s_wall", nq_now))),
        ("Secondary Floor", float(data_0dte.get("s_floor", nq_now))),
    ]
    out = []
    for name, px in rows:
        dist = float(px - nq_now)
        side = "Resistance" if dist > 0 else "Support" if dist < 0 else "Pivot"
        out.append(
            {
                "Level": name,
                "Price": round(px, 2),
                "Dist (pts)": round(dist, 1),
                "Side": side,
            }
        )
    st.dataframe(pd.DataFrame(out), width="stretch", hide_index=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_overview_event_strip(event_risk):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">⏰ Event Risk (Next)</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not event_risk:
        st.info("Event risk unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    if event_risk.get("lockout_active"):
        lock = event_risk.get("lockout_event", {}) or {}
        st.error(
            f"Lockout active: {lock.get('event', 'High-impact event')} "
            f"({lock.get('time_et', '')}, {_countdown_label(lock.get('seconds_to', 0))})"
        )
    else:
        nh = event_risk.get("next_high")
        if nh:
            st.warning(
                f"Next high-impact: {nh.get('event', 'N/A')} @ {nh.get('time_et', 'N/A')} "
                f"({_countdown_label(nh.get('seconds_to', 0))})"
            )
        else:
            st.success("No high-impact releases in near horizon.")

    next_events = event_risk.get("next_events", [])[:3]
    rows = []
    for ev in next_events:
        sec_to = ev.get("seconds_to")
        rows.append(
            {
                "Time": ev.get("time_et") or ev.get("date_et") or "N/A",
                "Impact": str(ev.get("impact", "unknown")).upper(),
                "Event": ev.get("event", "Unknown"),
                "Countdown": ev.get("countdown") or _countdown_label(sec_to if sec_to is not None else 0),
            }
        )
    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
        )
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_futures_indices_panel(market_data, nq_now, nq_day_change_pct, nq_source, data_0dte, level_interactions_df):
    if not market_data:
        return
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧭 Futures & Indices</div></div><div class="terminal-body">',
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


def _render_heatmap_panel():
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧩 Nasdaq Stocks Heat Map</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    st.markdown("**Heatmap Controls**")
    hc1, hc2, hc3 = st.columns([1.2, 1, 1])
    with hc1:
        st.selectbox(
            "Universe",
            ["Nasdaq 100", "Magnificent 7", "Custom Watchlist"],
            key="heatmap_universe",
        )
    with hc2:
        st.selectbox(
            "Sizing",
            ["Market Cap", "Volume", "Equal Weight"],
            key="heatmap_size_mode",
        )
    with hc3:
        st.selectbox(
            "Timeframe",
            ["1D", "5D", "1M"],
            key="heatmap_timeframe",
        )

    if st.session_state.heatmap_universe == "Custom Watchlist":
        st.text_input(
            "Custom Symbols (comma-separated)",
            key="heatmap_custom_symbols",
            help="Example: AAPL,MSFT,NVDA,AMZN",
        )

    heatmap_df = get_nasdaq_heatmap_data(
        universe=st.session_state.heatmap_universe,
        size_mode=st.session_state.heatmap_size_mode,
        timeframe=st.session_state.heatmap_timeframe,
        custom_symbols=st.session_state.heatmap_custom_symbols,
    )
    if heatmap_df is not None and not heatmap_df.empty:
        heatmap_df = heatmap_df.copy()
        size_cut = heatmap_df["size"].quantile(0.18)
        small_mask = heatmap_df["size"] < size_cut
        if small_mask.any():
            small = heatmap_df[small_mask]
            rolled = (
                small.groupby("sector", as_index=False)
                .apply(
                    lambda g: pd.Series(
                        {
                            "symbol": "Basket",
                            "price": 0.0,
                            "change_pct": (
                                (g["change_pct"] * g["size"]).sum() / g["size"].sum()
                                if g["size"].sum() > 0
                                else 0.0
                            ),
                            "size": g["size"].sum(),
                        }
                    )
                )
                .reset_index(drop=True)
            )
            heatmap_df = pd.concat([heatmap_df[~small_mask], rolled], ignore_index=True)

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
            hovertemplate="<b>%{label}</b><br>Price: $%{customdata[0]:,.2f}<br>Change: %{customdata[1]:+.2f}%<extra></extra>",
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
            uniformtext=dict(minsize=9, mode="hide"),
            coloraxis=dict(cmin=-4, cmax=4),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Mode: {st.session_state.heatmap_universe} • "
            f"Sizing: {st.session_state.heatmap_size_mode} • "
            f"Timeframe: {st.session_state.heatmap_timeframe}"
        )
    else:
        st.info("Heat map data is temporarily unavailable.")
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_initial_balance_report_panel(finnhub_key):
    st.subheader("📈 Initial Balance Report")
    st.caption(
        "Full report mode with historical IB probabilities, directional filters, and breakout extension stats."
    )

    symbol_options = {
        "NQ Futures": "NQ=F",
        "ES Futures": "ES=F",
        "YM Futures": "YM=F",
    }

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        symbol_label = st.selectbox(
            "Symbol",
            list(symbol_options.keys()),
            index=0,
            key="ib_symbol_label",
        )
    with c2:
        lookback_days = st.slider("Lookback Days", min_value=10, max_value=90, value=30, step=5, key="ib_days")
    with c3:
        timeframe = st.selectbox("Timeframe", ["1m", "2m", "5m", "15m", "30m"], index=0, key="ib_timeframe")
    with c4:
        ib_start = st.text_input("IB Start (ET, HH:MM)", value="09:30", key="ib_start")
    with c5:
        ib_end = st.text_input("IB End (ET, HH:MM)", value="10:30", key="ib_end")

    run_col, info_col = st.columns([1, 3])
    with run_col:
        run_report = st.button("🔄 Run / Refresh IB Report", use_container_width=True)
    with info_col:
        st.caption("Report updates on button click to avoid constant reruns.")

    current_params = {
        "symbol": symbol_options.get(symbol_label, "NQ=F"),
        "days": int(lookback_days),
        "timeframe": str(timeframe),
        "ib_start": str(ib_start).strip(),
        "ib_end": str(ib_end).strip(),
    }

    if "ib_report_params" not in st.session_state:
        st.session_state.ib_report_params = None
    if "ib_report_payload" not in st.session_state:
        st.session_state.ib_report_payload = None

    if run_report or st.session_state.ib_report_payload is None:
        st.session_state.ib_report_params = current_params
        st.session_state.ib_report_payload = get_initial_balance_backtest(
            symbol=current_params["symbol"],
            days=current_params["days"],
            timeframe=current_params["timeframe"],
            ib_start=current_params["ib_start"],
            ib_end=current_params["ib_end"],
            finnhub_key=finnhub_key,
        )

    if st.session_state.ib_report_params != current_params:
        st.warning("Parameters changed. Click 'Run / Refresh IB Report' to update results.")

    payload = st.session_state.ib_report_payload or {}
    sessions_df = payload.get("sessions")
    summary = payload.get("summary", {})
    meta = payload.get("meta", {})

    if sessions_df is None or sessions_df.empty:
        st.info("No Initial Balance sessions available for these settings.")
        return

    st.caption(
        f"Source: {meta.get('source', 'n/a')} | Symbol: {meta.get('symbol', 'n/a')} | "
        f"Interval used: {meta.get('interval_used', 'n/a')} (requested {meta.get('interval_requested', 'n/a')}) | "
        f"As of: {meta.get('asof_et', 'n/a')}"
    )

    st.markdown("### Condition Filters")
    f1, f2, f3, f4, f5, f6 = st.columns(6)
    with f1:
        gap_filter = st.selectbox("Gap", ["Any", "Up", "Down", "Flat"], index=0, key="ib_f_gap")
    with f2:
        on_filter = st.selectbox("Open vs ON Mid", ["Any", "Above", "Below"], index=0, key="ib_f_on")
    with f3:
        vwap_filter = st.selectbox("IB End vs VWAP", ["Any", "Above", "Below"], index=0, key="ib_f_vwap")
    with f4:
        event_filter = st.selectbox("High-Impact Day", ["Any", "Only High", "Exclude High"], index=0, key="ib_f_event")
    with f5:
        min_ib = st.number_input("Min IB Size (pts)", min_value=0.0, value=0.0, step=1.0, key="ib_f_min")
    with f6:
        max_ib = st.number_input("Max IB Size (pts, 0=Any)", min_value=0.0, value=0.0, step=1.0, key="ib_f_max")

    all_weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    selected_weekdays = st.multiselect(
        "Weekdays",
        options=all_weekdays,
        default=all_weekdays,
        key="ib_f_weekdays",
    )

    filtered = sessions_df.copy()
    if gap_filter != "Any":
        filtered = filtered[filtered["gap_dir"] == gap_filter.lower()]
    if on_filter != "Any":
        filtered = filtered[filtered["open_vs_overnight_mid"] == on_filter.lower()]
    if vwap_filter != "Any":
        filtered = filtered[filtered["ib_end_vs_vwap"] == vwap_filter.lower()]
    if event_filter == "Only High":
        filtered = filtered[filtered["high_impact_day"] == True]  # noqa: E712
    elif event_filter == "Exclude High":
        filtered = filtered[filtered["high_impact_day"] == False]  # noqa: E712
    if min_ib > 0:
        filtered = filtered[filtered["ib_range"] >= float(min_ib)]
    if max_ib > 0:
        filtered = filtered[filtered["ib_range"] <= float(max_ib)]
    if selected_weekdays:
        filtered = filtered[filtered["weekday"].isin(selected_weekdays)]

    if filtered.empty:
        st.warning("No sessions matched current filters.")
        return

    total = len(filtered)
    up_break_pct = float(filtered["break_up"].mean() * 100.0)
    down_break_pct = float(filtered["break_down"].mean() * 100.0)
    both_break_pct = float(filtered["both_break"].mean() * 100.0)
    no_break_pct = float(filtered["no_break"].mean() * 100.0)
    first_up_pct = float((filtered["first_break"] == "up").mean() * 100.0)
    first_down_pct = float((filtered["first_break"] == "down").mean() * 100.0)
    hit_025_pct = float(filtered["hit_025_any"].mean() * 100.0)
    hit_050_pct = float(filtered["hit_050_any"].mean() * 100.0)
    hit_100_pct = float(filtered["hit_100_any"].mean() * 100.0)
    med_ib_range = float(filtered["ib_range"].median())
    med_ib_range_pct = float(filtered["ib_range_pct"].median())

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Sessions", f"{total}")
    m2.metric("Up Break %", f"{up_break_pct:.1f}%")
    m3.metric("Down Break %", f"{down_break_pct:.1f}%")
    m4.metric("Both-Side Break %", f"{both_break_pct:.1f}%")
    m5.metric("No Break %", f"{no_break_pct:.1f}%")
    m6.metric("Median IB Range", f"{med_ib_range:.1f} pts")

    mm1, mm2, mm3, mm4, mm5 = st.columns(5)
    mm1.metric("First Break Up %", f"{first_up_pct:.1f}%")
    mm2.metric("First Break Down %", f"{first_down_pct:.1f}%")
    mm3.metric("Hit 0.25x IB %", f"{hit_025_pct:.1f}%")
    mm4.metric("Hit 0.50x IB %", f"{hit_050_pct:.1f}%")
    mm5.metric("Hit 1.00x IB %", f"{hit_100_pct:.1f}%")

    st.caption(
        f"Median IB Range %: {med_ib_range_pct:.2f}% | "
        f"Avg Up Extension: {float(filtered['ext_mult_up'].mean()):.2f}x | "
        f"Avg Down Extension: {float(filtered['ext_mult_down'].mean()):.2f}x"
    )

    ch1, ch2 = st.columns(2)
    with ch1:
        range_plot = filtered.copy()
        range_plot["date"] = pd.to_datetime(range_plot["date"], errors="coerce")
        range_plot = range_plot.sort_values("date")
        fig_range = px.line(
            range_plot,
            x="date",
            y="ib_range",
            markers=True,
            title="IB Range By Session",
        )
        fig_range.update_layout(
            template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white",
            height=340,
            margin=dict(l=20, r=20, t=50, b=20),
            xaxis_title="Session",
            yaxis_title="IB Range (pts)",
        )
        st.plotly_chart(fig_range, use_container_width=True)

    with ch2:
        fb = (
            filtered["first_break"]
            .replace({"none": "none", "up": "up", "down": "down", "both": "both"})
            .value_counts()
            .reindex(["up", "down", "both", "none"])
            .fillna(0)
            .reset_index()
        )
        fb.columns = ["First Break", "Count"]
        fig_fb = px.bar(
            fb,
            x="First Break",
            y="Count",
            color="First Break",
            title="First Break Distribution",
            color_discrete_map={
                "up": "#27c46b",
                "down": "#df4f4f",
                "both": "#d1a942",
                "none": "#607089",
            },
        )
        fig_fb.update_layout(
            template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white",
            height=340,
            margin=dict(l=20, r=20, t=50, b=20),
            showlegend=False,
        )
        st.plotly_chart(fig_fb, use_container_width=True)

    st.markdown("### Weekday Breakdown (First Break %)")
    pivot = (
        filtered.assign(v=1)
        .pivot_table(
            index="weekday",
            columns="first_break",
            values="v",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex(["Mon", "Tue", "Wed", "Thu", "Fri"])
        .fillna(0)
    )
    for col in ["up", "down", "both", "none"]:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot_pct = pivot.div(pivot.sum(axis=1).replace(0, pd.NA), axis=0).fillna(0) * 100.0
    fig_heat = px.imshow(
        pivot_pct[["up", "down", "both", "none"]],
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale="Blues",
    )
    fig_heat.update_layout(
        template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white",
        height=280,
        margin=dict(l=20, r=20, t=20, b=20),
        coloraxis_showscale=False,
        xaxis_title="First Break Side",
        yaxis_title="Weekday",
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown("### Session Table")
    table_cols = [
        "date",
        "weekday",
        "ib_range",
        "ib_range_pct",
        "gap_dir",
        "open_vs_overnight_mid",
        "ib_end_vs_vwap",
        "first_break",
        "break_up",
        "break_down",
        "both_break",
        "no_break",
        "ext_mult_up",
        "ext_mult_down",
        "high_impact_day",
    ]
    table_df = filtered[table_cols].copy().sort_values("date", ascending=False)
    for col in ["ib_range", "ib_range_pct", "ext_mult_up", "ext_mult_down"]:
        table_df[col] = table_df[col].map(lambda v: round(float(v), 2))
    st.dataframe(table_df, width="stretch", hide_index=True, height=440)

    st.caption(
        "Note: high-impact day tagging depends on available calendar feed coverage and may be partial for historical sessions."
    )


def _level_builder_row(label, key, default):
    if key not in st.session_state:
        st.session_state[key] = float(default)
    return st.number_input(label, format="%.2f", key=key, step=0.25)


def _extract_builder_seed(level_data, prefix):
    if not level_data:
        return {}
    level_map = {}
    for row in level_data.get("results", []):
        try:
            name, price, _width, _icon = row
            level_map[str(name)] = float(price)
        except Exception:
            continue
    mapping = {
        f"builder_{prefix}_res": "Target Resistance",
        f"builder_{prefix}_wall": "Primary Wall",
        f"builder_{prefix}_floor": "Primary Floor",
        f"builder_{prefix}_supp": "Target Support",
        f"builder_{prefix}_swall": "Secondary Wall",
        f"builder_{prefix}_sfloor": "Secondary Floor",
        f"builder_{prefix}_flip": "Gamma Flip",
        f"builder_{prefix}_dn": "Delta Neutral",
        f"builder_{prefix}_u50": "Upper 0.50σ",
        f"builder_{prefix}_u25": "Upper 0.25σ",
        f"builder_{prefix}_l25": "Lower 0.25σ",
        f"builder_{prefix}_l50": "Lower 0.50σ",
    }
    out = {}
    for key, level_name in mapping.items():
        if level_name in level_map:
            out[key] = float(level_map[level_name])
    return out


def _render_nq_level_builder_panel(data_0dte=None, data_weekly=None):
    st.subheader("📊 NQ Precision Map — Level Builder")
    st.caption(
        "Fill in your gamma levels. Copy the output string and paste it into the Pine Script input field."
    )

    manual_defaults = {
        "builder_d_res": 25506.68,
        "builder_d_wall": 25471.68,
        "builder_d_floor": 25141.95,
        "builder_d_supp": 25106.95,
        "builder_d_swall": 25400.00,
        "builder_d_sfloor": 25250.00,
        "builder_d_flip": 25183.16,
        "builder_d_dn": 24308.92,
        "builder_d_u50": 25565.24,
        "builder_d_u25": 25380.00,
        "builder_d_l25": 25280.00,
        "builder_d_l50": 25074.76,
        "builder_w_res": 25500.00,
        "builder_w_wall": 25450.00,
        "builder_w_floor": 25150.00,
        "builder_w_supp": 25100.00,
        "builder_w_swall": 25390.00,
        "builder_w_sfloor": 25240.00,
        "builder_w_flip": 24762.14,
        "builder_w_dn": 24308.92,
        "builder_w_u50": 25570.00,
        "builder_w_u25": 25385.00,
        "builder_w_l25": 25275.00,
        "builder_w_l50": 25070.00,
    }

    auto_seed = {}
    auto_seed.update(_extract_builder_seed(data_0dte, "d"))
    auto_seed.update(_extract_builder_seed(data_weekly, "w"))
    seed_values = {**manual_defaults, **auto_seed}

    for key, val in seed_values.items():
        if key not in st.session_state:
            st.session_state[key] = float(val)

    b1, b2 = st.columns(2)
    with b1:
        if st.button("🔄 Refresh From Generated Levels", use_container_width=True):
            if auto_seed:
                for key, val in seed_values.items():
                    st.session_state[key] = float(val)
                st.rerun()
            else:
                st.warning("Generated levels are unavailable right now. Using manual values.")
    with b2:
        if st.button("↩ Reset To Manual Defaults", use_container_width=True):
            for key, val in manual_defaults.items():
                st.session_state[key] = float(val)
            st.rerun()

    if auto_seed:
        d_meta = (data_0dte or {}).get("data_meta", {})
        w_meta = (data_weekly or {}).get("data_meta", {})
        d_src = d_meta.get("options_source", "model")
        w_src = w_meta.get("options_source", "model")
        st.caption(
            f"Auto-seed source: 0DTE={d_src} | Weekly={w_src}. "
            "Use Refresh button to pull latest generated levels on demand."
        )
    else:
        st.caption("Auto-seed unavailable; currently using manual/default values.")

    col_0dte, col_wkly = st.columns(2)

    with col_0dte:
        st.markdown("### 0DTE (Daily)")

        st.markdown("**Outer Range**")
        d_res = _level_builder_row("Target Resistance", "builder_d_res", manual_defaults["builder_d_res"])
        d_wall = _level_builder_row("Primary Wall", "builder_d_wall", manual_defaults["builder_d_wall"])
        d_floor = _level_builder_row("Primary Floor", "builder_d_floor", manual_defaults["builder_d_floor"])
        d_supp = _level_builder_row("Target Support", "builder_d_supp", manual_defaults["builder_d_supp"])

        st.markdown("**Intra-Range**")
        d_swall = _level_builder_row("Secondary Wall", "builder_d_swall", manual_defaults["builder_d_swall"])
        d_sfloor = _level_builder_row("Secondary Floor", "builder_d_sfloor", manual_defaults["builder_d_sfloor"])
        d_flip = _level_builder_row("Gamma Flip", "builder_d_flip", manual_defaults["builder_d_flip"])
        d_dn = _level_builder_row("Delta Neutral", "builder_d_dn", manual_defaults["builder_d_dn"])

        st.markdown("**Volatility Bands**")
        d_u50 = _level_builder_row("Upper 0.50σ", "builder_d_u50", manual_defaults["builder_d_u50"])
        d_u25 = _level_builder_row("Upper 0.25σ", "builder_d_u25", manual_defaults["builder_d_u25"])
        d_l25 = _level_builder_row("Lower 0.25σ", "builder_d_l25", manual_defaults["builder_d_l25"])
        d_l50 = _level_builder_row("Lower 0.50σ", "builder_d_l50", manual_defaults["builder_d_l50"])

    with col_wkly:
        st.markdown("### Weekly")

        st.markdown("**Outer Range**")
        w_res = _level_builder_row("Target Resistance", "builder_w_res", manual_defaults["builder_w_res"])
        w_wall = _level_builder_row("Primary Wall", "builder_w_wall", manual_defaults["builder_w_wall"])
        w_floor = _level_builder_row("Primary Floor", "builder_w_floor", manual_defaults["builder_w_floor"])
        w_supp = _level_builder_row("Target Support", "builder_w_supp", manual_defaults["builder_w_supp"])

        st.markdown("**Intra-Range**")
        w_swall = _level_builder_row("Secondary Wall", "builder_w_swall", manual_defaults["builder_w_swall"])
        w_sfloor = _level_builder_row("Secondary Floor", "builder_w_sfloor", manual_defaults["builder_w_sfloor"])
        w_flip = _level_builder_row("Gamma Flip", "builder_w_flip", manual_defaults["builder_w_flip"])
        w_dn = _level_builder_row("Delta Neutral", "builder_w_dn", manual_defaults["builder_w_dn"])

        st.markdown("**Volatility Bands**")
        w_u50 = _level_builder_row("Upper 0.50σ", "builder_w_u50", manual_defaults["builder_w_u50"])
        w_u25 = _level_builder_row("Upper 0.25σ", "builder_w_u25", manual_defaults["builder_w_u25"])
        w_l25 = _level_builder_row("Lower 0.25σ", "builder_w_l25", manual_defaults["builder_w_l25"])
        w_l50 = _level_builder_row("Lower 0.50σ", "builder_w_l50", manual_defaults["builder_w_l50"])

    st.divider()
    st.markdown("### Output String")
    st.caption(
        "Order: 0DTE [res, wall, floor, supp, swall, sfloor, flip, dn, u50, u25, l25, l50] "
        "→ Weekly [same order]"
    )

    values = [
        d_res, d_wall, d_floor, d_supp,
        d_swall, d_sfloor, d_flip, d_dn,
        d_u50, d_u25, d_l25, d_l50,
        w_res, w_wall, w_floor, w_supp,
        w_swall, w_sfloor, w_flip, w_dn,
        w_u50, w_u25, w_l25, w_l50,
    ]
    output_string = ",".join(f"{v:.2f}" for v in values)

    st.text_area(
        label="Copy this → paste into Pine Script 'Price Levels' input",
        value=output_string,
        height=80,
    )

    with st.expander("Preview all levels"):
        labels_0dte = [
            "0DTE Target Res", "0DTE Primary Wall", "0DTE Primary Floor", "0DTE Target Supp",
            "0DTE Secondary Wall", "0DTE Secondary Floor", "0DTE Gamma Flip", "0DTE Delta Neutral",
            "0DTE Upper 0.50σ", "0DTE Upper 0.25σ", "0DTE Lower 0.25σ", "0DTE Lower 0.50σ",
        ]
        labels_wkly = [
            "Weekly Target Res", "Weekly Primary Wall", "Weekly Primary Floor", "Weekly Target Supp",
            "Weekly Secondary Wall", "Weekly Secondary Floor", "Weekly Gamma Flip", "Weekly Delta Neutral",
            "Weekly Upper 0.50σ", "Weekly Upper 0.25σ", "Weekly Lower 0.25σ", "Weekly Lower 0.50σ",
        ]

        df = pd.DataFrame({
            "Level": labels_0dte + labels_wkly,
            "Price": [f"{v:.2f}" for v in values],
        })
        st.dataframe(df, use_container_width=True, hide_index=True)


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

    if "compact_mode" not in st.session_state:
        st.session_state.compact_mode = False
    if "heatmap_universe" not in st.session_state:
        st.session_state.heatmap_universe = "Nasdaq 100"
    if "heatmap_size_mode" not in st.session_state:
        st.session_state.heatmap_size_mode = "Market Cap"
    if "heatmap_timeframe" not in st.session_state:
        st.session_state.heatmap_timeframe = "5D"
    if "heatmap_custom_symbols" not in st.session_state:
        st.session_state.heatmap_custom_symbols = "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA"
    if "earnings_major_only" not in st.session_state:
        st.session_state.earnings_major_only = True

    _theme_css(
        bg_color,
        card_bg,
        text_color,
        accent_color,
        border_color,
        compact_mode=st.session_state.compact_mode,
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

    st.sidebar.checkbox("🗜 Compact Mode", key="compact_mode")
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
        qqq_price, qqq_source = get_qqq_price_with_source(finnhub_key)
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

        ratio_meta = _compute_tight_ratio(
            nq_now=nq_now,
            qqq_price=qqq_price,
            nq_source=nq_source,
            qqq_source=qqq_source,
        )
        ratio = float(ratio_meta.get("ratio", 0.0) or 0.0)
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
            qqq_source = "CBOE Spot"
            ratio_meta = _compute_tight_ratio(
                nq_now=nq_now,
                qqq_price=qqq_price,
                nq_source=nq_source,
                qqq_source=qqq_source,
            )
            ratio = float(ratio_meta.get("ratio", 0.0) or 0.0)

        exp_0dte, exp_weekly, exp_monthly = get_expirations_by_type(df_raw)

        data_0dte = None
        data_weekly = None
        data_monthly = None

        if exp_0dte:
            data_0dte = process_expiration(
                df_raw, exp_0dte, qqq_price, ratio, nq_now, options_ticker="QQQ"
            )

        if exp_weekly and exp_weekly != exp_0dte:
            data_weekly = process_expiration(
                df_raw, exp_weekly, qqq_price, ratio, nq_now, options_ticker="QQQ"
            )

        if exp_monthly and exp_monthly not in [exp_0dte, exp_weekly]:
            data_monthly = process_expiration(
                df_raw, exp_monthly, qqq_price, ratio, nq_now, options_ticker="QQQ"
            )

        market_data = get_market_overview_yahoo()
        vix_level = market_data.get("vix", {}).get("price", 15)
        fg = get_fear_greed_index()
        sentiment_score = calculate_sentiment_score(data_0dte, nq_now, vix_level, fg["score"])
        opening_structure = get_futures_opening_structure("NQ=F")
        reference_levels = get_futures_reference_levels("NQ=F", finnhub_key)
        event_risk = get_event_risk_snapshot(finnhub_key, hours_ahead=24)
        breadth_internals = get_futures_breadth_internals()
        cot_dealer = get_cot_dealer_positioning()

    level_interactions_df = None
    nq_data = None
    if data_0dte:
        nq_data = get_nq_intraday_data()
        if nq_data is not None and not nq_data.empty:
            level_interactions_df = _build_level_interactions(nq_data, data_0dte)

    econ_window = get_economic_calendar_window(finnhub_key, days=7)
    regime_engine = _build_regime_engine(
        data_0dte=data_0dte,
        data_weekly=data_weekly,
        nq_now=nq_now,
        market_data=market_data,
        opening_structure=opening_structure,
        event_risk=event_risk,
        nq_data=nq_data,
    )
    dealer_forward_pressure = _build_dealer_forward_pressure(
        data_0dte=data_0dte,
        qqq_price=qqq_price,
        ratio=ratio,
    )
    microstructure_snapshot = _build_microstructure_snapshot(
        nq_data=nq_data,
        opening_structure=opening_structure,
    )
    cross_asset_matrix = _build_cross_asset_driver_matrix(
        market_data=market_data,
        nq_day_change_pct=nq_day_change_pct,
    )
    event_surprise_engine = _build_event_surprise_engine(econ_window)

    nav_sections = {
        "Workspace": [
            ("🏠 Overview", "📈 Market Overview"),
            ("🌐 Multi-Asset", "🌐 Multi-Asset"),
            ("📅 Earnings Calendar", "📅 Earnings Calendar"),
            ("🗓 Economic Calendar", "🗓 Economic Calendar"),
        ],
        "Resources": [
            ("📊 NQ Level Builder", "📊 NQ Level Builder"),
        ],
        "Analytics": [
            ("🧪 Execution Lab", "🧪 Execution Lab"),
            ("📈 Initial Balance", "📈 Initial Balance"),
            ("🌐 Macro & Breadth", "🌐 Macro & Breadth"),
            ("🚨 Event Intel", "🚨 Event Intel"),
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
        _render_terminal_command_bar(
            active_view=active_view,
            nq_source=nq_source,
            qqq_source=qqq_source,
            auto_refresh=auto_refresh,
            refresh_interval=refresh_interval if auto_refresh else 0,
            ratio_meta=ratio_meta,
            event_risk=event_risk,
            market_data=market_data,
        )

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
            _render_data_health_strip(
                nq_source=nq_source,
                qqq_source=qqq_source,
                ratio_meta=ratio_meta,
                data_0dte=data_0dte,
                market_data=market_data,
                finnhub_key=finnhub_key,
            )
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
                ratio_conf = int(ratio_meta.get("confidence_score", 0) or 0)
                ratio_lbl = str(ratio_meta.get("confidence_label", "Low"))
                ratio_unc = float(ratio_meta.get("uncertainty_pts", 0.0) or 0.0)

                st.markdown(
                    f"""
                <div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🎯 Session Quick Glance</div></div><div class="terminal-body"><div class="quick-glance">
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
                        <div class="quick-stat"><p class="label">RATIO QUALITY</p><p class="value">{ratio_conf}%</p><p class="sub">{ratio_lbl} • ±{ratio_unc:.0f} pts map error</p></div>
                    </div>
                </div></div></div>
                """,
                    unsafe_allow_html=True,
                )

                playbook = _build_morning_playbook(
                    data_0dte=data_0dte,
                    data_weekly=data_weekly,
                    nq_now=nq_now,
                    event_risk=event_risk,
                )
                _render_trade_plan_panel(
                    playbook=playbook,
                    data_0dte=data_0dte,
                    nq_now=nq_now,
                    event_risk=event_risk,
                )
                _render_overview_reference_snapshot(data_0dte, nq_now)
                _render_overview_event_strip(event_risk)

                st.markdown(
                    '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📊 Market Sentiment</div></div><div class="terminal-body">',
                    unsafe_allow_html=True,
                )
                sc1, sc2 = st.columns([3, 1])
                with sc1:
                    marker_left = max(1, min(99, sentiment_score))
                    st.markdown(
                        f"""
                    <div class="sentiment-wrap">
                        <div class="sentiment-meter"><div class="sentiment-marker" style="left: {marker_left}%;"></div></div>
                        <div class="sentiment-axis">
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
                    sentiment_badge = (
                        "bear"
                        if sentiment_score < 45
                        else "neutral"
                        if sentiment_score < 55
                        else "bull"
                    )
                    sentiment_arrow = "↓" if sentiment_score < 45 else "→" if sentiment_score < 55 else "↑"
                    st.markdown(
                        f"""
                        <div class="score-panel">
                            <p class="score-kicker">Score</p>
                            <p class="score-value">{sentiment_score}/100</p>
                            <span class="score-badge {sentiment_badge}">{sentiment_arrow} {sentiment_text}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    fg_score = int(_safe_float((fg or {}).get("score"), 50) or 50)
                    fg_rating_raw = str((fg or {}).get("rating", "Neutral"))
                    fg_rating = html.escape(fg_rating_raw.title())
                    fg_lower = fg_rating_raw.lower()
                    if "fear" in fg_lower and "extreme" in fg_lower:
                        fg_badge = "bull"
                        fg_arrow = "↑"
                    elif "fear" in fg_lower:
                        fg_badge = "neutral"
                        fg_arrow = "→"
                    elif "greed" in fg_lower and "extreme" in fg_lower:
                        fg_badge = "bear"
                        fg_arrow = "↓"
                    elif "greed" in fg_lower:
                        fg_badge = "neutral"
                        fg_arrow = "→"
                    else:
                        fg_badge = "neutral"
                        fg_arrow = "→"
                    st.markdown(
                        f"""
                        <div class="score-panel" style="margin-top:10px;">
                            <p class="score-kicker">Fear &amp; Greed</p>
                            <p class="score-value">{fg_score}/100</p>
                            <span class="score-badge {fg_badge}">{fg_arrow} {fg_rating}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                st.markdown("</div></div>", unsafe_allow_html=True)
            else:
                st.info("No 0DTE data available for compact overview.")

        elif active_view == "🧪 Execution Lab":
            if not data_0dte:
                st.info("Execution Lab requires options data.")
            else:
                _render_regime_engine_panel(regime_engine)
                _render_opening_structure_panel(opening_structure)
                _render_dealer_forward_pressure_panel(dealer_forward_pressure)
                _render_microstructure_panel(microstructure_snapshot)
                _render_reference_levels_panel(
                    data_0dte=data_0dte,
                    reference_levels=reference_levels,
                    opening_structure=opening_structure,
                    nq_now=nq_now,
                    event_risk=event_risk,
                )
                _render_level_quality_panel(
                    data_0dte=data_0dte,
                    data_weekly=data_weekly,
                    nq_now=nq_now,
                    level_interactions_df=level_interactions_df,
                )

        elif active_view == "📈 Initial Balance":
            _render_initial_balance_report_panel(finnhub_key=finnhub_key)

        elif active_view == "🌐 Macro & Breadth":
            _render_futures_indices_panel(
                market_data=market_data,
                nq_now=nq_now,
                nq_day_change_pct=nq_day_change_pct,
                nq_source=nq_source,
                data_0dte=data_0dte,
                level_interactions_df=level_interactions_df,
            )
            _render_cross_asset_driver_matrix_panel(cross_asset_matrix)
            _render_cot_dealer_panel(cot_dealer)
            _render_breadth_internals_panel(
                breadth_data=breadth_internals,
                nq_day_change_pct=nq_day_change_pct,
                es_change_pct=float((market_data.get("es", {}) or {}).get("change_pct", 0.0)),
                market_data=market_data,
            )
            _render_heatmap_panel()

        elif active_view == "🚨 Event Intel":
            _render_event_risk_panel(event_risk)
            _render_event_surprise_panel(event_surprise_engine)

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

        elif active_view == "📊 NQ Level Builder":
            _render_nq_level_builder_panel(
                data_0dte=data_0dte,
                data_weekly=data_weekly,
            )

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
                data_meta = selected_data.get("data_meta", {})
                freshness = data_meta.get("options_freshness", "unknown")
                latency = data_meta.get("options_latency_s")
                source = data_meta.get("options_source", "CBOE")
                conf_mult = data_meta.get("confidence_multiplier", 1.0)
                st.caption(
                    f"Options data: {source} | freshness: {freshness} | latency: "
                    f"{latency if latency is not None else 'n/a'}s | confidence x{conf_mult:.2f}"
                )
                if freshness == "stale_hard":
                    st.warning("Options chain is stale (hard). Confidence has been heavily penalized.")
                elif freshness == "stale_soft":
                    st.warning("Options chain is stale (soft). Confidence has been reduced.")
                results_df = pd.DataFrame(selected_data["results"], columns=["Level", "Price", "Width", "Icon"])
                conf_map = selected_data.get("level_confidence", {})
                results_df["Confidence"] = results_df["Level"].map(
                    lambda lvl: conf_map.get(lvl, {}).get("label", "-")
                )
                results_df["Conf Score"] = results_df["Level"].map(
                    lambda lvl: conf_map.get(lvl, {}).get("score", 0)
                )
                table_height = max(300, min(650, 52 + (len(results_df) + 1) * 35))
                st.dataframe(
                    results_df[["Icon", "Level", "Price", "Width", "Confidence", "Conf Score"]],
                    width="stretch",
                    hide_index=True,
                    height=table_height,
                )

                current_levels = {
                    "Delta Neutral": selected_data["dn_nq"],
                    "Gamma Flip": selected_data["g_flip_nq"],
                    "Primary Wall": selected_data["p_wall"],
                    "Primary Floor": selected_data["p_floor"],
                    "Secondary Wall": selected_data["s_wall"],
                    "Secondary Floor": selected_data["s_floor"],
                }
                tracker_key = f"level_tracker::{label}::{selected_exp.strftime('%Y-%m-%d')}"
                changes_df, prev_ts = _track_level_changes(tracker_key, current_levels)
                st.markdown("**Level Change Tracker**")
                if changes_df is not None and not changes_df.empty:
                    changes_df["Current"] = changes_df["Current"].map(lambda v: round(v, 2))
                    changes_df["Prev"] = changes_df["Prev"].map(lambda v: round(v, 2))
                    changes_df["Change (pts)"] = changes_df["Change (pts)"].map(lambda v: round(v, 2))
                    st.caption(f"Compared with previous snapshot at {prev_ts}")
                    st.dataframe(changes_df, width="stretch", hide_index=True)
                else:
                    st.caption("Waiting for next refresh to compute level changes.")
            else:
                st.info("No data available for this timeframe.")

        elif active_view == "🗓 Economic Calendar":
            st.subheader("🗓 Economic Calendar")
            st.caption("Week view (next 7 days, ET). High impact = red, medium = orange/yellow.")

            econ_df = get_economic_calendar_window(finnhub_key, days=7)
            econ_health = get_dataset_freshness("econ_calendar", max_age_sec=120)
            raw_counts = st.session_state.get("econ_source_counts_raw", {})
            final_counts = st.session_state.get("econ_source_counts_final", {})
            if raw_counts:
                st.caption(
                    "Sources (raw -> final): "
                    + ", ".join(
                        f"{k}: {raw_counts.get(k, 0)} -> {final_counts.get(k, 0)}"
                        for k in sorted(raw_counts.keys())
                    )
                )
            else:
                st.caption("Sources (raw -> final): no events returned from provider APIs")
            st.caption(
                f"Calendar health: {econ_health.get('status', 'unknown')} | "
                f"latency {_latency_label(econ_health.get('latency_s'))} | "
                f"asof {econ_health.get('asof_utc') if econ_health.get('asof_utc') else 'n/a'}"
            )
            if econ_df is None or econ_df.empty:
                st.info("No economic events available for this window.")
            else:
                et_now = datetime.now(ZoneInfo("America/New_York"))
                week_dates = [et_now.date() + timedelta(days=i) for i in range(7)]

                for day in week_dates:
                    day_key = day.isoformat()
                    dt = datetime.strptime(day_key, "%Y-%m-%d")
                    st.markdown(f"**{dt.strftime('%a %b %d')} Release**")
                    st.markdown(
                        '<div class="econ-header"><div></div><div>Release</div><div>Impact</div><div>Actual</div><div>Expected</div><div>Prior</div><div></div><div>Alerts</div></div>',
                        unsafe_allow_html=True,
                    )

                    day_df = econ_df[econ_df["date_et"] == day_key].copy()
                    if day_df.empty:
                        st.markdown(
                            '<div class="econ-row low"><div>•</div><div>No major events</div><div><span class="impact-chip low">LOW</span></div><div>-</div><div>-</div><div>-</div><div></div><div>-</div></div>',
                            unsafe_allow_html=True,
                        )
                        continue

                    for _, r in day_df.iterrows():
                        impact = str(r.get("impact", "medium")).lower()
                        impact_label = "HIGH" if impact == "high" else "MED" if impact == "medium" else "LOW"
                        row_source = str(r.get("source", "unknown"))
                        row_conf = int(r.get("confidence_score", 0) or 0)
                        row_conf_label = str(r.get("confidence_label", "Low"))
                        row_latency = _latency_from_asof_utc(r.get("asof_utc"))
                        row_latency_txt = _latency_label(row_latency)
                        event_iso = r.get("event_dt_iso")
                        countdown_html = ""
                        try:
                            event_dt = datetime.fromisoformat(str(event_iso))
                            if event_dt.tzinfo is None:
                                event_dt = event_dt.replace(tzinfo=ZoneInfo("America/New_York"))
                            secs = int((event_dt - et_now).total_seconds())
                            if 0 <= secs <= 60:
                                countdown_html = f'<span class="count-chip">T-{secs}s</span>'
                        except Exception:
                            countdown_html = ""

                        st.markdown(
                            f"""
                            <div class="econ-row {impact}">
                                <div>›</div>
                                <div>
                                    <div>{r.get("time_et", "")}  {html.escape(str(r.get("event", "")))}</div>
                                    <div style="font-size:11px;color:#9fb0c7;">{html.escape(row_source)} • {row_conf_label} {row_conf}% • age {row_latency_txt}</div>
                                </div>
                                <div><span class="impact-chip {impact}">{impact_label}</span></div>
                                <div>{html.escape(_fmt_econ_value(r.get("actual", "-")))}</div>
                                <div>{html.escape(_fmt_econ_value(r.get("expected", "-")))}</div>
                                <div>{html.escape(_fmt_econ_value(r.get("prior", "-")))}</div>
                                <div>{countdown_html}</div>
                                <div>🔔</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    st.markdown("")

        elif active_view == "📅 Earnings Calendar":
            st.subheader("📅 Earnings Calendar")
            ec1, ec2 = st.columns([1, 4])
            with ec1:
                st.toggle("Major Only", key="earnings_major_only")
            with ec2:
                st.caption("Focused list for highest-impact NQ / ES / YM earnings names.")

            earnings_df = get_earnings_calendar_multi(
                finnhub_key,
                days=5,
                major_only=st.session_state.earnings_major_only,
            )
            earnings_health = get_dataset_freshness("earnings_calendar", max_age_sec=900)
            st.caption(
                f"Earnings health: {earnings_health.get('status', 'unknown')} | "
                f"latency {_latency_label(earnings_health.get('latency_s'))} | "
                f"asof {earnings_health.get('asof_utc') if earnings_health.get('asof_utc') else 'n/a'}"
            )
            if earnings_df is None or earnings_df.empty:
                st.info("No earnings found for this window.")
            else:
                et_today = datetime.now().date()
                day_list = [et_today + timedelta(days=i) for i in range(5)]
                cols = st.columns(5)
                for i, day in enumerate(day_list):
                    with cols[i]:
                        st.markdown(
                            f'<div class="earn-day-title">{day.strftime("%a %b %d")}</div>',
                            unsafe_allow_html=True,
                        )
                        day_df = earnings_df[earnings_df["date"] == day].copy()
                        for bucket in ["Before Open", "After Close", "Time TBA"]:
                            bucket_df = day_df[day_df["time"] == bucket].copy()
                            if bucket_df.empty:
                                continue
                            st.markdown(
                                f'<div class="earn-time-title">{bucket}</div>',
                                unsafe_allow_html=True,
                            )
                            for _, row in bucket_df.head(12).iterrows():
                                eps_est = row.get("eps_estimate")
                                rev_est = row.get("revenue_estimate")
                                eps_txt = f"EPS est: {eps_est:.2f}" if pd.notna(eps_est) else "EPS est: n/a"
                                rev_txt = (
                                    f"Rev est: {float(rev_est)/1_000_000:.0f}M"
                                    if pd.notna(rev_est)
                                    else "Rev est: n/a"
                                )
                                row_latency = _latency_from_asof_utc(row.get("asof_utc"))
                                row_latency_txt = _latency_label(row_latency)
                                conf_label = row.get("confidence_label", "Low")
                                conf_score = int(row.get("confidence_score", 0) or 0)
                                st.markdown(
                                    f"""
                                    <div class="earn-card">
                                        <div class="sym">{row['symbol']}</div>
                                        <div class="meta">{eps_txt} • {rev_txt}</div>
                                        <div class="meta">{row.get('source', 'Source n/a')} • {conf_label} {conf_score}% • age {row_latency_txt}</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                                if st.button(
                                    f"View {row['symbol']}",
                                    key=f"earn_view_{row['symbol']}_{row['date']}_{row['time']}",
                                    use_container_width=True,
                                ):
                                    st.session_state.selected_earnings = {
                                        "symbol": row["symbol"],
                                        "date": str(row["date"]),
                                        "time": row["time"],
                                        "source": row.get("source", ""),
                                        "eps_estimate": row.get("eps_estimate"),
                                        "revenue_estimate": row.get("revenue_estimate"),
                                        "confidence_label": row.get("confidence_label", "Low"),
                                        "confidence_score": int(row.get("confidence_score", 0) or 0),
                                        "asof_utc": row.get("asof_utc"),
                                    }
                                    st.rerun()

        elif active_view == "🍞 Daily Bread":
            st.subheader("🍞 Daily Bread")
            if data_0dte:
                events = get_economic_calendar(finnhub_key)
                news = get_rss_news(finnhub_key)
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
            st.subheader("📈 Trinity-Style Dealer Exposure")
            st.caption("Two-panel horizontal GEX map for SPY and QQQ (0DTE). Monthly view removed.")

            g1, g2, g3, g4 = st.columns(4)
            with g1:
                zoom_preset = st.selectbox(
                    "Zoom Preset",
                    options=["Tight (±2.5%)", "Balanced (±5.0%)", "Wide (±8.0%)", "Custom"],
                    index=1,
                    key="gex_zoom_preset",
                )
            with g2:
                max_rows = st.slider(
                    "Ladder Rows",
                    min_value=18,
                    max_value=90,
                    value=48,
                    step=2,
                    key="gex_max_rows",
                )
            with g3:
                row_mode = st.selectbox(
                    "Row Selection",
                    options=["Top |GEX|", "Nearest Spot"],
                    index=0,
                    key="gex_row_mode",
                )
            with g4:
                label_density = st.selectbox(
                    "Value Labels",
                    options=["Auto", "Top 8", "Top 16", "Top 24", "None"],
                    index=1,
                    key="gex_label_density",
                )

            preset_to_window = {
                "Tight (±2.5%)": 2.5,
                "Balanced (±5.0%)": 5.0,
                "Wide (±8.0%)": 8.0,
            }
            if zoom_preset == "Custom":
                strike_window_pct = st.slider(
                    "Custom Spot Window (%)",
                    min_value=1.0,
                    max_value=15.0,
                    value=4.0,
                    step=0.5,
                    key="gex_window_pct_custom",
                )
            else:
                strike_window_pct = float(preset_to_window.get(zoom_preset, 5.0))
                st.caption(f"Current zoom: ±{strike_window_pct:.1f}% around spot.")

            st.caption("GEX panel refreshes with each app cycle. Use mouse wheel/pinch to zoom further.")

            multi_asset_data = process_multi_asset()

            def _render_gex_heatmap(asset_label, asset_payload):
                def _fmt_notional(v):
                    av = abs(float(v))
                    sign = "-" if float(v) < 0 else ""
                    if av >= 1_000_000_000:
                        return f"{sign}${av/1_000_000_000:.1f}B"
                    if av >= 1_000_000:
                        return f"{sign}${av/1_000_000:.1f}M"
                    if av >= 1_000:
                        return f"{sign}${av/1_000:.1f}K"
                    return f"{sign}${av:,.0f}"

                if not asset_payload:
                    st.info(f"{asset_label}: no data")
                    return
                ticker = asset_payload.get("ticker", asset_label)
                df_raw, etf_price = get_cboe_options_live(ticker)
                if df_raw is None or df_raw.empty or not etf_price:
                    st.info(f"{asset_label}: no options chain")
                    return
                health = get_dataset_freshness(
                    f"options:{str(ticker).upper()}",
                    max_age_sec=180,
                )
                health_status = health.get("status", "unknown")
                health_latency = health.get("latency_s")
                health_source = health.get("source", "CBOE")
                health_asof = health.get("asof_utc")
                health_mult = float(health.get("confidence_multiplier", 1.0))
                st.caption(
                    f"{asset_label} chain: {health_source} | {health_status} | "
                    f"latency {health_latency if health_latency is not None else 'n/a'}s | conf x{health_mult:.2f} | "
                    f"asof {health_asof if health_asof else 'n/a'}"
                )
                if health_status == "stale_hard":
                    st.warning(f"{asset_label}: stale_hard options chain; levels may be lagging.")
                elif health_status == "stale_soft":
                    st.info(f"{asset_label}: stale_soft options chain; confidence reduced.")

                spot = float(asset_payload.get("etf_price", 0) or etf_price or 0)
                anchor = float(spot if spot > 0 else etf_price)

                # Build chart from a wider, display-only strike universe.
                df_plot = df_raw.copy()
                df_plot = df_plot[df_plot["open_interest"] > 0].copy()
                df_plot = df_plot[df_plot["iv"] > 0].copy()
                window = float(strike_window_pct) / 100.0
                low = anchor * (1.0 - window)
                high = anchor * (1.0 + window)
                df_plot = df_plot[(df_plot["strike"] >= low) & (df_plot["strike"] <= high)].copy()
                if df_plot.empty:
                    st.info(f"{asset_label}: no strikes in display window")
                    return

                df_plot["GEX"] = df_plot.apply(
                    lambda x: x["open_interest"] * x["gamma"] * (etf_price ** 2) * 0.01 * (1 if x["type"] == "call" else -1),
                    axis=1,
                )
                gex_by_strike = df_plot.groupby("strike", as_index=False)["GEX"].sum().sort_values("strike", ascending=False)
                if gex_by_strike.empty:
                    st.info(f"{asset_label}: empty strike map")
                    return

                # Keep the strongest ladders or rows nearest spot.
                if len(gex_by_strike) > max_rows:
                    if row_mode == "Nearest Spot" and spot > 0:
                        keep_idx = (
                            gex_by_strike.assign(spot_dist=(gex_by_strike["strike"] - spot).abs())
                            .nsmallest(max_rows, "spot_dist")
                            .index
                        )
                    else:
                        keep_idx = (
                            gex_by_strike.assign(abs_gex=gex_by_strike["GEX"].abs())
                            .nlargest(max_rows, "abs_gex")
                            .index
                        )
                    gex_by_strike = gex_by_strike.loc[keep_idx].sort_values("strike", ascending=False)

                z = gex_by_strike["GEX"].to_numpy().reshape(-1, 1)
                y = gex_by_strike["strike"].astype(float).to_list()
                x = [asset_label]
                max_abs = float(max(1.0, gex_by_strike["GEX"].abs().max()))
                y_min = float(gex_by_strike["strike"].min())
                y_max = float(gex_by_strike["strike"].max())

                fig = go.Figure(
                    data=go.Heatmap(
                        z=z,
                        x=x,
                        y=y,
                        colorscale=[
                            [0.00, "#4c1049"],
                            [0.18, "#283c66"],
                            [0.50, "#1a2432"],
                            [0.78, "#2fae74"],
                            [1.00, "#f0dc1f"],
                        ],
                        reversescale=False,
                        showscale=False,
                        zmid=0,
                        zmin=-max_abs,
                        zmax=max_abs,
                        hovertemplate="Strike %{y:.2f}<br>GEX %{z:,.0f}<br>Notional %{text}<extra></extra>",
                        text=[[ _fmt_notional(v[0]) ] for v in z],
                    )
                )

                # Mark nearest strike to spot.
                if spot > 0:
                    nearest_idx = (gex_by_strike["strike"] - spot).abs().idxmin()
                    nearest_strike = float(gex_by_strike.loc[nearest_idx, "strike"])
                    fig.add_hline(
                        y=nearest_strike,
                        line_dash="dot",
                        line_color="#ffffff",
                        opacity=0.8,
                    )
                    fig.add_annotation(
                        x=asset_label,
                        y=nearest_strike,
                        text=f"Spot {spot:.2f}",
                        showarrow=False,
                        xanchor="left",
                        yanchor="bottom",
                        font=dict(size=10, color="#dfe6f3"),
                        bgcolor="rgba(12,18,28,0.65)",
                    )

                # Right-side value ladder text, with adaptive density to avoid overlap.
                label_df = gex_by_strike.copy()
                if label_density == "None":
                    label_df = label_df.iloc[0:0]
                elif label_density.startswith("Top "):
                    try:
                        keep_n = int(label_density.split("Top ", 1)[1])
                    except Exception:
                        keep_n = 8
                    label_df = (
                        label_df.assign(abs_gex=label_df["GEX"].abs())
                        .nlargest(keep_n, "abs_gex")[["strike", "GEX"]]
                        .sort_values("strike", ascending=False)
                    )
                elif len(label_df) > 36:
                    key_abs = (
                        label_df.assign(abs_gex=label_df["GEX"].abs())
                        .nlargest(12, "abs_gex")[["strike", "GEX"]]
                    )
                    if spot > 0:
                        key_spot = (
                            label_df.assign(spot_dist=(label_df["strike"] - spot).abs())
                            .nsmallest(8, "spot_dist")[["strike", "GEX"]]
                        )
                        label_df = pd.concat([key_abs, key_spot], ignore_index=True).drop_duplicates(subset=["strike"])
                    else:
                        label_df = key_abs
                    label_df = label_df.sort_values("strike", ascending=False)

                for _, row in label_df.iterrows():
                    fig.add_annotation(
                        x=0.985,
                        xref="paper",
                        y=float(row["strike"]),
                        yref="y",
                        text=_fmt_notional(row["GEX"]),
                        showarrow=False,
                        xanchor="right",
                        yanchor="middle",
                        font=dict(size=10, color="#dbe6f7"),
                    )

                fig.update_layout(
                    template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white",
                    height=700,
                    margin=dict(l=10, r=10, t=30, b=10),
                    xaxis_title="",
                    yaxis_title="Strike",
                    dragmode="zoom",
                    uirevision=f"{asset_label}-{strike_window_pct}-{max_rows}-{row_mode}-{label_density}",
                )
                fig.update_yaxes(
                    autorange="reversed",
                    range=[y_max, y_min],
                    tickformat=".0f",
                    showgrid=False,
                    tickmode="linear",
                    dtick=max(1.0, round((y_max - y_min) / 16.0, 2)),
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={"scrollZoom": True, "displayModeBar": True, "doubleClick": "reset"},
                )

            c_spy, c_qqq = st.columns(2)
            with c_spy:
                st.markdown("**SPY**")
                _render_gex_heatmap("SPY", multi_asset_data.get("SPY") if multi_asset_data else None)
            with c_qqq:
                st.markdown("**QQQ**")
                _render_gex_heatmap("QQQ", multi_asset_data.get("QQQ") if multi_asset_data else None)

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
        if active_view == "📅 Earnings Calendar":
            st.markdown(
                '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📊 Earnings Detail</div></div><div class="terminal-body">',
                unsafe_allow_html=True,
            )
            selected = st.session_state.get("selected_earnings")
            if selected and selected.get("symbol"):
                symbol = selected["symbol"]
                detail = get_earnings_detail(symbol, finnhub_key)
                st.markdown(f"### {detail.get('name', symbol)} ({symbol})")
                c1, c2 = st.columns(2)
                price_val = detail.get("price")
                chg = detail.get("change")
                dp = detail.get("change_pct")
                c1.metric("Price", f"${price_val:,.2f}" if price_val not in (None, "") else "N/A")
                c2.metric(
                    "Change",
                    f"{chg:+.2f}" if chg not in (None, "") else "N/A",
                    f"{dp:+.2f}%" if dp not in (None, "") else None,
                )
                st.caption(
                    f"Date: {selected.get('date', 'N/A')} • {selected.get('time', 'Time TBA')} • "
                    f"Source: {selected.get('source', 'N/A')} • "
                    f"Confidence: {selected.get('confidence_label', 'Low')} {selected.get('confidence_score', 0)}% • "
                    f"AsOf: {selected.get('asof_utc', 'n/a')}"
                )
                st.markdown(
                    f"Industry: `{detail.get('industry', 'N/A')}`  \n"
                    f"Market Cap: `{detail.get('market_cap', 'N/A')}`  \n"
                    f"Next Earnings: `{detail.get('next_earnings', 'N/A')}`"
                )
                hist = detail.get("history", [])
                if hist:
                    hist_df = pd.DataFrame(hist)
                    st.markdown("**Recent Earnings History**")
                    st.dataframe(hist_df, width="stretch", hide_index=True)
                else:
                    st.info("No earnings history available.")
            else:
                st.info("Select an earnings card from the calendar to view details here.")
            st.markdown("</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📰 Live News Feed</div></div><div class="terminal-body">',
                unsafe_allow_html=True,
            )
            rss_news = get_rss_news(finnhub_key)
            visible_news = [
                article
                for article in (rss_news or [])
                if str(article.get("headline", "")).strip()
            ]
            st.markdown('<div class="news-rail-title">Headlines</div>', unsafe_allow_html=True)
            st.markdown('<div class="news-rail">', unsafe_allow_html=True)
            if visible_news:
                for article in visible_news[:32]:
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
