import time
from datetime import datetime, timedelta, time as dt_time
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
    get_intraday_history,
    get_nq_intraday_data,
    get_nq_price_auto,
    get_quote_age_seconds,
    get_quote_age_label,
    get_qqq_price_with_source,
    get_runtime_health,
    get_rss_news,
    get_top_movers,
    process_expiration,
    process_multi_asset,
    schwab_is_configured,
)


def _quote_timestamp_ms(symbol):
    meta = st.session_state.get(f"quote_meta::{symbol}", {}) or {}
    ts = meta.get("timestamp_ms")
    try:
        return int(ts) if ts else None
    except Exception:
        return None


def _feed_runtime_status(nq_source, qqq_source):
    hard_quote_age_sec = int(st.secrets.get("HARD_QUOTE_MAX_AGE_SEC", 60))
    hard_sync_lag_sec = int(st.secrets.get("HARD_RATIO_SYNC_MAX_LAG_SEC", 10))
    options_hard_age_sec = int(st.secrets.get("HARD_OPTIONS_MAX_AGE_SEC", 150))

    nq_age = get_quote_age_seconds("NQ=F")
    qqq_age = get_quote_age_seconds("QQQ")
    nq_ts = _quote_timestamp_ms("NQ=F")
    qqq_ts = _quote_timestamp_ms("QQQ")
    sync_lag_s = None
    if nq_ts and qqq_ts:
        sync_lag_s = abs(int(nq_ts) - int(qqq_ts)) / 1000.0

    options_health = get_dataset_freshness("options:QQQ", max_age_sec=options_hard_age_sec)
    options_src = str(options_health.get("source", "unknown")).lower()
    options_status = str(options_health.get("status", "unknown")).lower()

    nq_rt = "schwab" in str(nq_source or "").lower()
    qqq_rt = "schwab" in str(qqq_source or "").lower()
    opt_rt = "schwab" in options_src

    if nq_rt and qqq_rt and opt_rt:
        mode = "Realtime"
    elif nq_rt and qqq_rt and not opt_rt:
        mode = "Mixed (Realtime Quotes / Delayed Options)"
    else:
        mode = "Fallback/Delayed"

    reasons = []
    freeze = False
    if nq_age is not None and nq_age > hard_quote_age_sec:
        freeze = True
        reasons.append(f"NQ age {nq_age}s > {hard_quote_age_sec}s")
    if qqq_age is not None and qqq_age > hard_quote_age_sec:
        freeze = True
        reasons.append(f"QQQ age {qqq_age}s > {hard_quote_age_sec}s")
    if sync_lag_s is not None and sync_lag_s > hard_sync_lag_sec:
        freeze = True
        reasons.append(f"NQ/QQQ sync lag {sync_lag_s:.1f}s > {hard_sync_lag_sec}s")
    if options_status == "stale_hard":
        freeze = True
        reasons.append("Options chain stale_hard")

    return {
        "mode": mode,
        "freeze_levels": bool(freeze),
        "reasons": reasons,
        "sync_lag_s": sync_lag_s,
        "nq_age_s": nq_age,
        "qqq_age_s": qqq_age,
        "options_status": options_status,
        "options_source": options_health.get("source", "unknown"),
        "hard_quote_age_sec": hard_quote_age_sec,
        "hard_sync_lag_sec": hard_sync_lag_sec,
    }


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
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');
    :root {{
        --viz-bg-0: #0a1019;
        --viz-bg-1: #121a27;
        --viz-panel: #151f2d;
        --viz-panel-2: #101823;
        --viz-text: #e6efff;
        --viz-muted: #8ea1bf;
        --viz-cyan: #38d7ff;
        --viz-green: #54efaa;
        --viz-amber: #ffd37f;
        --viz-red: #ff8b8b;
    }}
    .stApp {{
        background: radial-gradient(circle at 20% -20%, #171b22 0%, {bg_color} 38%, #090d14 100%);
        color: {text_color};
        font-family: "Space Grotesk", "Trebuchet MS", sans-serif;
    }}
    html, body, [class*="css"] {{
        font-family: "Space Grotesk", "Trebuchet MS", sans-serif;
    }}
    section.main > div {{
        padding-top: 0.5rem;
    }}
    h1 {{
        color: #f2f5fb;
        font-weight: 800;
        letter-spacing: 0.2px;
        margin-bottom: 0.2rem;
        font-family: "Space Grotesk", "Trebuchet MS", sans-serif;
    }}
    h2, h3 {{
        color: #e9edf5;
        font-family: "Space Grotesk", "Trebuchet MS", sans-serif;
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
    .viz-hero {{
        border: 1px solid #2b3749;
        border-radius: 16px;
        overflow: hidden;
        margin-bottom: 10px;
        background:
            radial-gradient(circle at 84% -20%, rgba(56, 215, 255, 0.20), transparent 55%),
            radial-gradient(circle at 14% 118%, rgba(84, 239, 170, 0.13), transparent 45%),
            linear-gradient(170deg, #172334 0%, #0e1520 100%);
        box-shadow: 0 14px 30px rgba(2, 8, 18, 0.45);
    }}
    .viz-hero-top {{
        padding: 14px 16px 12px 16px;
        border-bottom: 1px solid #2a3444;
    }}
    .viz-kicker {{
        margin: 0;
        color: #98a9c4;
        text-transform: uppercase;
        letter-spacing: 0.34px;
        font-size: 11px;
        font-weight: 700;
    }}
    .viz-big {{
        margin: 4px 0 0 0;
        color: #eaf4ff;
        font-weight: 700;
        font-size: clamp(30px, 5.6vw, 52px);
        line-height: 1.0;
        letter-spacing: 0.25px;
        font-family: "JetBrains Mono", "Consolas", monospace;
    }}
    .viz-chip-row {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 10px;
    }}
    .viz-chip {{
        border-radius: 999px;
        border: 1px solid #2a3544;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 700;
        color: #dce7fa;
        background: #152132;
    }}
    .viz-chip.pos {{
        border-color: #2f7d56;
        color: #9affc9;
        background: rgba(47, 125, 86, 0.24);
    }}
    .viz-chip.warn {{
        border-color: #7d6430;
        color: #ffe3a7;
        background: rgba(166, 123, 32, 0.24);
    }}
    .viz-chip.neg {{
        border-color: #7e3434;
        color: #ffc2c2;
        background: rgba(176, 56, 56, 0.22);
    }}
    .viz-kpi-grid {{
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 8px;
        padding: 12px 14px 14px 14px;
    }}
    .viz-kpi-card {{
        border: 1px solid #2b3748;
        border-radius: 10px;
        background: linear-gradient(180deg, #152132 0%, #101823 100%);
        padding: 8px 10px;
    }}
    .viz-kpi-card .k {{
        margin: 0;
        color: #8ca0bc;
        font-size: 10px;
        letter-spacing: 0.3px;
        text-transform: uppercase;
        font-weight: 700;
    }}
    .viz-kpi-card .v {{
        margin: 3px 0 0 0;
        color: #e8f1ff;
        font-size: 18px;
        line-height: 1.1;
        font-weight: 700;
        font-family: "JetBrains Mono", "Consolas", monospace;
    }}
    .viz-kpi-card .s {{
        margin: 4px 0 0 0;
        color: #88a0be;
        font-size: 10px;
        line-height: 1.15;
    }}
    .viz-alert-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 8px;
        margin: 8px 0 10px 0;
    }}
    .viz-alert {{
        border: 1px solid #2a3545;
        border-radius: 10px;
        padding: 8px 10px;
        background: #111a27;
    }}
    .viz-alert.high {{
        border-color: #7e3434;
        background: rgba(176, 56, 56, 0.14);
    }}
    .viz-alert.med {{
        border-color: #7d6430;
        background: rgba(166, 123, 32, 0.14);
    }}
    .viz-alert.low {{
        border-color: #2f5f8b;
        background: rgba(44, 79, 120, 0.14);
    }}
    .viz-alert .sev {{
        margin: 0;
        font-size: 10px;
        letter-spacing: 0.25px;
        font-weight: 700;
        text-transform: uppercase;
        color: #97abc7;
    }}
    .viz-alert .txt {{
        margin: 3px 0 0 0;
        font-size: 12px;
        color: #e1ecff;
        line-height: 1.2;
    }}
    .viz-alert .sub {{
        margin: 2px 0 0 0;
        font-size: 10px;
        color: #89a1be;
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
        .viz-kpi-grid {{
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }}
        .viz-alert-grid {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
    }}
    @media (max-width: 900px) {{
        .terminal-command-grid {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .futures-strip {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .viz-kpi-grid {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .viz-alert-grid {{
            grid-template-columns: repeat(1, minmax(0, 1fr));
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
    st.markdown('<div class="left-nav-title">Navigation</div>', unsafe_allow_html=True)

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


def _compute_tight_ratio(
    nq_now,
    qqq_price,
    nq_source="",
    qqq_source="",
    sync_lag_s=None,
    max_sync_lag_s=10,
):
    raw_ratio = float(nq_now / qqq_price) if qqq_price and qqq_price > 0 else 0.0
    sync_lag = float(sync_lag_s) if sync_lag_s is not None else None
    if sync_lag is not None and sync_lag > float(max_sync_lag_s):
        held = st.session_state.get("ratio_last_good::NQ_QQQ")
        if held and float(held.get("ratio", 0.0) or 0.0) > 0:
            out = dict(held)
            out["ratio_mode"] = f"Sync Hold ({sync_lag:.1f}s lag)"
            out["confidence_label"] = "Low"
            out["confidence_score"] = int(min(54, int(out.get("confidence_score", 50) or 50)))
            out["source_pair"] = f"{nq_source} / {qqq_source}"
            out["sync_lag_s"] = sync_lag
            return out
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
        out = {
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
            "sync_lag_s": sync_lag,
        }
        return out

    ratio_series = pd.Series([float(h["ratio"]) for h in history], dtype="float64")
    recent_series = ratio_series.tail(min(30, len(ratio_series)))
    med_ratio = float(recent_series.median()) if len(recent_series) > 0 else raw_ratio
    abs_dev_series = (recent_series - med_ratio).abs()
    mad_ratio = float(abs_dev_series.median()) if len(abs_dev_series) > 0 else 0.0

    # Keep live mapping responsive; apply history as a light stabilizer, not a hard anchor.
    floor_band = max(0.00020, med_ratio * 0.00020)  # 2 bps floor
    dyn_band = max(floor_band, 4.0 * mad_ratio)
    dev_pct_from_med = abs(raw_ratio - med_ratio) / max(1e-9, med_ratio) * 100.0
    outlier_clamped = False
    clamped_ratio = raw_ratio
    if dev_pct_from_med > 2.5:
        low_band = med_ratio - dyn_band
        high_band = med_ratio + dyn_band
        clamped_ratio = min(max(raw_ratio, low_band), high_band)
        outlier_clamped = abs(raw_ratio - clamped_ratio) > 1e-12

    if len(recent_series) >= 8:
        if dev_pct_from_med <= 0.35:
            tight_ratio = (0.85 * raw_ratio) + (0.15 * med_ratio)
        else:
            tight_ratio = (0.95 * clamped_ratio) + (0.05 * med_ratio)
    elif len(recent_series) >= 3:
        tight_ratio = (0.92 * raw_ratio) + (0.08 * med_ratio)
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

    out = {
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
        "sync_lag_s": sync_lag,
    }
    if sync_lag is None or sync_lag <= float(max_sync_lag_s):
        st.session_state["ratio_last_good::NQ_QQQ"] = dict(out)
    return out


def _stabilize_level_mapping(nq_now, qqq_price_live, cboe_price, ratio_meta):
    ratio_meta = dict(ratio_meta or {})
    qqq_live = float(qqq_price_live or 0.0)
    qqq_cboe = float(cboe_price or 0.0)

    qqq_level_anchor = qqq_live if qqq_live > 0 else qqq_cboe
    mode = "Live"
    note = ""

    if qqq_live > 0 and qqq_cboe > 0:
        q_dev_pct = abs(qqq_live - qqq_cboe) / qqq_cboe * 100.0
        if q_dev_pct <= 1.25:
            qqq_level_anchor = (0.85 * qqq_live) + (0.15 * qqq_cboe)
            mode = "Live/CBOE Blend"
        else:
            qqq_level_anchor = qqq_live
            mode = "Live Anchor"
            note = (
                f"QQQ live vs CBOE divergence {q_dev_pct:.2f}%. "
                "Using live anchor to avoid delayed-chain bias."
            )

    ratio_live = float(ratio_meta.get("ratio", 0.0) or 0.0)
    ratio_anchor = float(nq_now / qqq_level_anchor) if qqq_level_anchor > 0 else ratio_live

    if ratio_live <= 0:
        ratio_final = ratio_anchor
        mode = f"{mode} (anchor only)"
    else:
        r_dev_pct = abs(ratio_live - ratio_anchor) / max(1e-9, ratio_anchor) * 100.0
        if r_dev_pct > 1.75:
            ratio_final = ratio_anchor
            mode = f"{mode} (ratio reset)"
            if not note:
                note = (
                    f"Live ratio deviated {r_dev_pct:.2f}% from options anchor. "
                    "Resetting to anchored ratio for levels."
                )
        elif r_dev_pct > 0.75:
            ratio_final = (0.75 * ratio_live) + (0.25 * ratio_anchor)
            mode = f"{mode} (ratio blend)"
        else:
            ratio_final = ratio_live

    ratio_meta.update(
        {
            "ratio": float(ratio_final),
            "ratio_live": float(ratio_live),
            "ratio_levels_anchor": float(ratio_anchor),
            "ratio_mode": mode,
            "qqq_live": float(qqq_live),
            "qqq_levels_anchor": float(qqq_level_anchor),
        }
    )
    return ratio_meta, float(ratio_final), float(qqq_level_anchor), note


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


def _render_runtime_mode_banner(feed_status):
    if not feed_status:
        return
    mode = str(feed_status.get("mode", "Unknown"))
    freeze = bool(feed_status.get("freeze_levels"))
    nq_age = feed_status.get("nq_age_s")
    qqq_age = feed_status.get("qqq_age_s")
    sync_lag = feed_status.get("sync_lag_s")
    options_status = str(feed_status.get("options_status", "unknown"))
    details = (
        f"Mode: {mode} | NQ age: {nq_age if nq_age is not None else 'n/a'}s | "
        f"QQQ age: {qqq_age if qqq_age is not None else 'n/a'}s | "
        f"Sync lag: {sync_lag:.1f}s" if sync_lag is not None else
        f"Mode: {mode} | NQ age: {nq_age if nq_age is not None else 'n/a'}s | "
        f"QQQ age: {qqq_age if qqq_age is not None else 'n/a'}s | Sync lag: n/a"
    )
    details = f"{details} | Options: {options_status}"
    reasons = feed_status.get("reasons", []) or []
    if freeze:
        msg = "Data quality lock active: levels frozen to last valid snapshot."
        if reasons:
            msg += " " + " • ".join(reasons)
        st.error(msg)
        st.caption(details)
    elif "fallback" in mode.lower() or "mixed" in mode.lower():
        st.warning("Running in fallback/delayed mode. Treat levels as lower confidence.")
        st.caption(details)
    else:
        st.success("Realtime mode active.")
        st.caption(details)


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
    ratio_anchor = float(ratio_meta.get("ratio_levels_anchor", ratio_val) or ratio_val)
    ratio_mode = str(ratio_meta.get("ratio_mode", "Live"))
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
            "sub": f"{ratio_mode} • live {ratio_raw:.4f} • anchor {ratio_anchor:.4f} • ±{ratio_unc:.0f} pts • {ratio_conf}%",
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


def _is_high_signal_news(article):
    if not article:
        return False
    score = int(article.get("priority_score", 0) or 0)
    if score >= 3:
        return True
    headline = str(article.get("headline", "")).lower()
    source = str(article.get("source", "")).lower()
    strong_terms = [
        "fomc",
        "fed",
        "powell",
        "cpi",
        "pce",
        "nfp",
        "jobs",
        "treasury",
        "yield",
        "inflation",
        "earnings",
        "guidance",
        "downgrade",
        "upgrade",
        "tariff",
        "war",
        "sanction",
        "rate",
    ]
    if any(term in headline for term in strong_terms):
        return True
    if any(src in source for src in ["reuters", "wsj", "bloomberg", "dow jones", "cnbc"]):
        return True
    return False


def _build_trade_bias_engine(
    data_0dte,
    nq_now,
    regime_engine,
    cross_asset_matrix,
    event_risk,
    opening_structure,
    breadth_internals,
):
    if not data_0dte:
        return {}

    score = int(_safe_float((regime_engine or {}).get("score"), 0) or 0)
    reasons = []

    gf_distance = float(nq_now - data_0dte.get("g_flip_nq", nq_now))
    dn_distance = float(nq_now - data_0dte.get("dn_nq", nq_now))
    if gf_distance > 0:
        score -= 18
        reasons.append(f"Above Gamma Flip by {gf_distance:+.0f} pts (negative-gamma drift risk).")
    else:
        score += 12
        reasons.append(f"Below Gamma Flip by {gf_distance:+.0f} pts (mean-reversion support).")

    if abs(dn_distance) > 220:
        adj = -8 if dn_distance > 0 else 8
        score += adj
        reasons.append(f"Extended vs Delta Neutral ({dn_distance:+.0f} pts).")

    macro_pressure = float((cross_asset_matrix or {}).get("composite", 0.0) or 0.0)
    if macro_pressure >= 1.0:
        score += 9
        reasons.append(f"Cross-asset pressure supportive ({macro_pressure:+.2f}).")
    elif macro_pressure <= -1.0:
        score -= 9
        reasons.append(f"Cross-asset pressure defensive ({macro_pressure:+.2f}).")

    if event_risk and event_risk.get("lockout_active"):
        score -= 18
        reasons.append("High-impact event lockout active.")
    else:
        nh = (event_risk or {}).get("next_high")
        if nh and int(nh.get("seconds_to", 999999)) <= 3600:
            score -= 10
            reasons.append("High-impact release within 60 minutes.")

    open_drive = str((opening_structure or {}).get("open_drive_signal", "")).lower()
    if "up" in open_drive:
        score += 5
        reasons.append("Opening drive is biased up.")
    elif "down" in open_drive:
        score -= 5
        reasons.append("Opening drive is biased down.")

    nq_part = _safe_float(((breadth_internals or {}).get("NQ", {}) or {}).get("participation_score"), 0.0) or 0.0
    if nq_part >= 0.55:
        score += 6
        reasons.append(f"NQ participation is broad ({nq_part:+.2f}).")
    elif nq_part <= -0.55:
        score -= 6
        reasons.append(f"NQ participation is weak ({nq_part:+.2f}).")

    score = int(max(-100, min(100, score)))
    if score >= 22:
        bias = "LONG"
    elif score <= -22:
        bias = "SHORT"
    else:
        bias = "NEUTRAL"

    conviction = "High" if abs(score) >= 45 else "Medium" if abs(score) >= 25 else "Low"
    return {
        "bias": bias,
        "score": score,
        "conviction": conviction,
        "reasons": reasons[:5],
    }


def _render_trade_bias_panel(payload):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧠 Trade Bias Engine</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not payload:
        st.info("Trade bias unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    bias = str(payload.get("bias", "NEUTRAL")).upper()
    score = int(payload.get("score", 0) or 0)
    conviction = str(payload.get("conviction", "Low"))
    b1, b2, b3 = st.columns(3)
    b1.metric("Bias", bias)
    b2.metric("Bias Score", f"{score:+d}")
    b3.metric("Conviction", conviction)
    reasons = payload.get("reasons", [])
    if reasons:
        st.markdown("**Top Drivers**")
        for reason in reasons:
            st.markdown(f"- {reason}")
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_open_playbook_panel(playbook, data_0dte, nq_now):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📖 Open Playbook (If/Then)</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not playbook or not data_0dte:
        st.info("Open playbook unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    p_wall = float(data_0dte.get("p_wall", nq_now))
    p_floor = float(data_0dte.get("p_floor", nq_now))
    dn = float(data_0dte.get("dn_nq", nq_now))
    gf = float(data_0dte.get("g_flip_nq", nq_now))
    s_wall = float(data_0dte.get("s_wall", p_wall))
    s_floor = float(data_0dte.get("s_floor", p_floor))

    scenarios = [
        {
            "Trigger": f"Rejects {p_wall:.0f}-{p_wall + 12:.0f}",
            "Action": f"Fade to DN {dn:.0f}, then {p_floor:.0f}",
            "Invalidation": f"Accepts above {s_wall + 12:.0f}",
        },
        {
            "Trigger": f"Holds above GF {gf:.0f} and reclaims pullback",
            "Action": f"Momentum continuation toward {p_wall:.0f}",
            "Invalidation": f"Loses GF and closes below {dn:.0f}",
        },
        {
            "Trigger": f"Reclaims {p_floor:.0f} after liquidity sweep",
            "Action": f"Mean-revert back to DN {dn:.0f}",
            "Invalidation": f"Breaks/accepts below {s_floor - 10:.0f}",
        },
    ]
    st.dataframe(pd.DataFrame(scenarios), width="stretch", hide_index=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _build_level_reaction_stats(data_0dte, intraday_hist):
    if not data_0dte or intraday_hist is None or intraday_hist.empty:
        return pd.DataFrame()

    use = intraday_hist.copy()
    if not isinstance(use.index, pd.DatetimeIndex):
        return pd.DataFrame()
    day_key = use.index.tz_convert("America/New_York").date if use.index.tz else use.index.date
    use = use.assign(_day=day_key)

    levels = [
        ("Primary Wall", float(data_0dte.get("p_wall", 0))),
        ("Gamma Flip", float(data_0dte.get("g_flip_nq", 0))),
        ("Delta Neutral", float(data_0dte.get("dn_nq", 0))),
        ("Primary Floor", float(data_0dte.get("p_floor", 0))),
    ]
    rows = []
    by_day = use.groupby("_day", as_index=False).agg(
        high=("High", "max"),
        low=("Low", "min"),
        close=("Close", "last"),
    )
    total_days = int(len(by_day))
    if total_days == 0:
        return pd.DataFrame()

    for lvl_name, lvl_px in levels:
        if lvl_px <= 0:
            continue
        touched = (by_day["low"] <= lvl_px) & (by_day["high"] >= lvl_px)
        touched_df = by_day[touched]
        touches = int(len(touched_df))
        if touches == 0:
            rows.append(
                {
                    "Level": lvl_name,
                    "Touches (20D)": 0,
                    "Hold %": "0%",
                    "Break %": "0%",
                    "Avg Excursion": "0.0 pts",
                }
            )
            continue
        is_resistance = "wall" in lvl_name.lower()
        is_support = "floor" in lvl_name.lower()
        if is_resistance:
            held = int((touched_df["close"] <= lvl_px).sum())
            breaks = int((touched_df["close"] > lvl_px).sum())
            excursion = (touched_df["high"] - lvl_px).clip(lower=0)
        elif is_support:
            held = int((touched_df["close"] >= lvl_px).sum())
            breaks = int((touched_df["close"] < lvl_px).sum())
            excursion = (lvl_px - touched_df["low"]).clip(lower=0)
        else:
            held = int((touched_df["close"] - lvl_px).abs().le(18).sum())
            breaks = int(max(0, touches - held))
            excursion = (touched_df["high"] - touched_df["low"]).clip(lower=0)
        rows.append(
            {
                "Level": lvl_name,
                "Touches (20D)": touches,
                "Hold %": f"{(held / touches) * 100:.0f}%",
                "Break %": f"{(breaks / touches) * 100:.0f}%",
                "Avg Excursion": f"{float(excursion.mean() if len(excursion) else 0):.1f} pts",
            }
        )
    return pd.DataFrame(rows)


def _render_level_reaction_panel(stats_df):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🪃 Level Reaction Stats (Last ~20 Sessions)</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if stats_df is None or stats_df.empty:
        st.info("Reaction stats unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return
    st.dataframe(stats_df, width="stretch", hide_index=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _build_alert_center(data_0dte, nq_now, event_risk, ratio_meta, nq_source, qqq_source):
    alerts = []
    if data_0dte:
        checks = [
            ("Gamma Flip", float(data_0dte.get("g_flip_nq", nq_now)), 18),
            ("Delta Neutral", float(data_0dte.get("dn_nq", nq_now)), 25),
            ("Primary Wall", float(data_0dte.get("p_wall", nq_now)), 12),
            ("Primary Floor", float(data_0dte.get("p_floor", nq_now)), 12),
        ]
        for name, level, threshold in checks:
            dist = abs(float(nq_now - level))
            if dist <= threshold:
                sev = "HIGH" if dist <= threshold * 0.45 else "MED"
                alerts.append(
                    {
                        "Severity": sev,
                        "Alert": f"{name} proximity",
                        "Detail": f"NQ is {dist:.1f} pts from {name} ({level:.2f})",
                    }
                )

    if event_risk and event_risk.get("lockout_active"):
        lock = event_risk.get("lockout_event", {}) or {}
        alerts.append(
            {
                "Severity": "HIGH",
                "Alert": "Event lockout active",
                "Detail": f"{lock.get('event', 'High-impact release')} {lock.get('time_et', '')}",
            }
        )
    else:
        nh = (event_risk or {}).get("next_high")
        if nh and int(nh.get("seconds_to", 999999)) <= 3600:
            alerts.append(
                {
                    "Severity": "MED",
                    "Alert": "High-impact event due soon",
                    "Detail": f"{nh.get('event', 'Release')} in {_countdown_label(nh.get('seconds_to', 0))}",
                }
            )

    ratio_conf = int((ratio_meta or {}).get("confidence_score", 0) or 0)
    if ratio_conf < 55:
        alerts.append(
            {
                "Severity": "MED",
                "Alert": "Ratio quality reduced",
                "Detail": f"NQ/QQQ mapping confidence {ratio_conf}%",
            }
        )

    if "schwab" not in str(nq_source).lower():
        alerts.append(
            {
                "Severity": "LOW",
                "Alert": "NQ realtime fallback",
                "Detail": f"NQ source is {nq_source}",
            }
        )
    if "schwab" not in str(qqq_source).lower():
        alerts.append(
            {
                "Severity": "LOW",
                "Alert": "QQQ realtime fallback",
                "Detail": f"QQQ source is {qqq_source}",
            }
        )

    sev_rank = {"HIGH": 0, "MED": 1, "LOW": 2}
    alerts = sorted(alerts, key=lambda r: sev_rank.get(str(r.get("Severity", "LOW")), 3))
    return alerts[:8]


def _render_alert_center_panel(alerts):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🔔 Alert Center</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not alerts:
        st.success("No active high-priority alerts.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return
    st.dataframe(pd.DataFrame(alerts), width="stretch", hide_index=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _third_friday(year, month):
    d = datetime(year, month, 1)
    offset = (4 - d.weekday()) % 7
    first_friday = d + timedelta(days=offset)
    return first_friday + timedelta(days=14)


def _expected_nq_front_contract(now_et=None):
    if now_et is None:
        now_et = datetime.now(ZoneInfo("America/New_York"))
    q_months = [3, 6, 9, 12]
    year = now_et.year

    def _next_quarter(y, m):
        idx = q_months.index(m)
        if idx == len(q_months) - 1:
            return y + 1, q_months[0]
        return y, q_months[idx + 1]

    quarter = None
    for qm in q_months:
        if now_et.month <= qm:
            quarter = qm
            break
    if quarter is None:
        year += 1
        quarter = 3

    expiry = _third_friday(year, quarter).replace(tzinfo=now_et.tzinfo)
    roll_start = expiry - timedelta(days=8)
    if now_et >= roll_start:
        year, quarter = _next_quarter(year, quarter)
    month_codes = {3: "H", 6: "M", 9: "U", 12: "Z"}
    return f"NQ{month_codes[quarter]}{str(year)[-2:]}", roll_start.strftime("%Y-%m-%d")


def _build_contract_roll_status(nq_source):
    src = str(nq_source or "")
    m = re.search(r"/NQ([HMUZ])(\d{2,4})", src.upper())
    current = None
    if m:
        yy = m.group(2)[-2:]
        current = f"NQ{m.group(1)}{yy}"

    expected, roll_start = _expected_nq_front_contract()
    status = "OK"
    note = f"Expected active front contract: {expected} (roll window starts {roll_start} ET)."
    if current and current != expected:
        status = "ROLL"
        note = f"Feed contract {current} differs from expected {expected}."
    elif not current:
        status = "UNKNOWN"
        note = f"Source does not expose explicit contract token. {note}"
    return {"status": status, "current": current or "N/A", "expected": expected, "note": note}


def _render_contract_roll_panel(payload):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📅 Contract Rollover Watch</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not payload:
        st.info("Rollover status unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Feed Contract", payload.get("current", "N/A"))
    c2.metric("Expected Front", payload.get("expected", "N/A"))
    c3.metric("Status", payload.get("status", "UNKNOWN"))
    msg = str(payload.get("note", ""))
    if payload.get("status") == "ROLL":
        st.warning(msg)
    elif payload.get("status") == "OK":
        st.success(msg)
    else:
        st.info(msg)
    st.markdown("</div></div>", unsafe_allow_html=True)


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


def _style_dashboard_figure(fig, height=260, margin=None):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Space Grotesk, Trebuchet MS, sans-serif",
            color="#dce8fb",
            size=12,
        ),
        margin=margin or dict(l=14, r=14, t=38, b=14),
    )
    return fig


def _render_market_overview_visuals(
    data_0dte,
    nq_now,
    qqq_price,
    nq_source,
    qqq_source,
    ratio_meta,
    sentiment_score,
    fg,
    event_risk,
    market_data,
    trade_bias_engine,
    alert_center,
    reaction_stats_df,
    nq_data,
    nq_day_change_pct,
):
    if not data_0dte:
        st.info("No 0DTE data available for dashboard view.")
        return

    dn_level = float(data_0dte.get("dn_nq", nq_now))
    gf_level = float(data_0dte.get("g_flip_nq", nq_now))
    p_wall = float(data_0dte.get("p_wall", nq_now))
    p_floor = float(data_0dte.get("p_floor", nq_now))
    s_wall = float(data_0dte.get("s_wall", p_wall))
    s_floor = float(data_0dte.get("s_floor", p_floor))

    dn_distance = float(nq_now - dn_level)
    gf_distance = float(nq_now - gf_level)
    expected_move = float(data_0dte.get("nq_em_full", 0.0) or 0.0)
    net_delta = float(data_0dte.get("net_delta", 0.0) or 0.0)

    bias = str((trade_bias_engine or {}).get("bias", "NEUTRAL")).upper()
    bias_score = int((trade_bias_engine or {}).get("score", 0) or 0)
    bias_conviction = str((trade_bias_engine or {}).get("conviction", "Low"))
    bias_meter = int(max(0, min(100, (bias_score + 100) / 2.0)))

    ratio_conf = int((ratio_meta or {}).get("confidence_score", 0) or 0)
    ratio_lbl = str((ratio_meta or {}).get("confidence_label", "Low"))
    ratio_mode = str((ratio_meta or {}).get("ratio_mode", "Live"))
    ratio_unc = float((ratio_meta or {}).get("uncertainty_pts", 0.0) or 0.0)

    fg_score = int(_safe_float((fg or {}).get("score"), 50) or 50)
    fg_rating = str((fg or {}).get("rating", "Neutral")).title()

    high_ct = int((event_risk or {}).get("today_high_count", 0) or 0)
    med_ct = int((event_risk or {}).get("today_medium_count", 0) or 0)
    total_events = int((event_risk or {}).get("total_events", 0) or 0)
    lockout = bool((event_risk or {}).get("lockout_active"))
    next_event = ((event_risk or {}).get("next_events") or [None])[0]
    next_event_txt = "-"
    if next_event:
        next_event_txt = (
            f"{next_event.get('time_et', 'n/a')} "
            f"{str(next_event.get('event', 'Event'))[:28]}"
        )

    regime_txt = "NEGATIVE GAMMA" if gf_distance > 0 else "POSITIVE GAMMA"
    regime_cls = "neg" if gf_distance > 0 else "pos"
    ratio_cls = "pos" if ratio_lbl.lower() == "high" else "warn" if ratio_lbl.lower() == "medium" else "neg"
    event_cls = "neg" if lockout else "warn" if high_ct > 0 else "pos"
    bias_cls = "pos" if bias == "LONG" else "neg" if bias == "SHORT" else "warn"

    kpis = [
        ("Dist GF", f"{gf_distance:+.0f}", f"vs {gf_level:.2f}"),
        ("Dist DN", f"{dn_distance:+.0f}", f"vs {dn_level:.2f}"),
        ("Expected", f"+/-{expected_move:.0f}", "0DTE range"),
        ("Wall Span", f"{abs(p_wall - p_floor):.0f}", f"{p_floor:.0f}-{p_wall:.0f}"),
        ("Net Delta", f"{net_delta:,.0f}", "book pressure"),
        ("Ratio Err", f"+/-{ratio_unc:.0f}", ratio_mode),
    ]
    kpi_html = []
    for title, val, sub in kpis:
        kpi_html.append(
            '<div class="viz-kpi-card">'
            f'<p class="k">{html.escape(title)}</p>'
            f'<p class="v">{html.escape(str(val))}</p>'
            f'<p class="s">{html.escape(str(sub))}</p>'
            "</div>"
        )

    st.markdown(
        f"""
        <div class="viz-hero">
            <div class="viz-hero-top">
                <p class="viz-kicker">NQ Visual Command Center</p>
                <p class="viz-big">{nq_now:,.2f}</p>
                <div class="viz-chip-row">
                    <span class="viz-chip {regime_cls}">{regime_txt}</span>
                    <span class="viz-chip {bias_cls}">Bias {bias} ({bias_score:+d})</span>
                    <span class="viz-chip {ratio_cls}">Ratio {ratio_lbl} {ratio_conf}%</span>
                    <span class="viz-chip {event_cls}">Event {'LOCKOUT' if lockout else 'CLEAR'}</span>
                    <span class="viz-chip">NQ {html.escape(str(nq_source))}</span>
                    <span class="viz-chip">QQQ {html.escape(str(qqq_source))}</span>
                </div>
            </div>
            <div class="viz-kpi-grid">
                {''.join(kpi_html)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns([1.20, 1.05, 1.75], gap="small")
    with m1:
        fig_meter = go.Figure()
        fig_meter.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=float(bias_meter),
                title={"text": "Bias Pressure"},
                domain={"x": [0.0, 0.48], "y": [0.0, 1.0]},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#44e8b7"},
                    "steps": [
                        {"range": [0, 35], "color": "rgba(255,139,139,0.24)"},
                        {"range": [35, 65], "color": "rgba(255,211,127,0.22)"},
                        {"range": [65, 100], "color": "rgba(84,239,170,0.24)"},
                    ],
                },
            )
        )
        fig_meter.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=float(sentiment_score),
                title={"text": "Sentiment"},
                domain={"x": [0.52, 1.0], "y": [0.0, 1.0]},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#38d7ff"},
                    "steps": [
                        {"range": [0, 35], "color": "rgba(255,139,139,0.24)"},
                        {"range": [35, 65], "color": "rgba(255,211,127,0.22)"},
                        {"range": [65, 100], "color": "rgba(84,239,170,0.24)"},
                    ],
                },
            )
        )
        _style_dashboard_figure(fig_meter, height=248, margin=dict(l=8, r=8, t=38, b=4))
        st.plotly_chart(fig_meter, use_container_width=True)

    level_conf = data_0dte.get("level_confidence", {}) or {}
    conf_counts = {"High": 0, "Medium": 0, "Low": 0}
    for payload in level_conf.values():
        lbl = str((payload or {}).get("label", "Low")).title()
        if lbl in conf_counts:
            conf_counts[lbl] += 1
    if conf_counts["High"] + conf_counts["Medium"] + conf_counts["Low"] == 0:
        conf_counts = {"High": 2, "Medium": 2, "Low": 2}

    with m2:
        fig_conf = go.Figure(
            data=[
                go.Pie(
                    labels=list(conf_counts.keys()),
                    values=list(conf_counts.values()),
                    hole=0.62,
                    marker=dict(colors=["#54efaa", "#ffd37f", "#ff8b8b"]),
                    textinfo="percent",
                    sort=False,
                )
            ]
        )
        fig_conf.update_layout(
            annotations=[dict(text="Levels", showarrow=False, font=dict(size=12, color="#dce8fb"))]
        )
        _style_dashboard_figure(fig_conf, height=178, margin=dict(l=8, r=8, t=28, b=4))
        st.plotly_chart(fig_conf, use_container_width=True)

        other_events = max(0, total_events - high_ct - med_ct)
        fig_event = go.Figure(
            data=[
                go.Pie(
                    labels=["High", "Medium", "Other"],
                    values=[max(1, high_ct), max(1, med_ct), max(1, other_events)],
                    hole=0.62,
                    marker=dict(colors=["#ff8b8b", "#ffd37f", "#38d7ff"]),
                    textinfo="none",
                    sort=False,
                )
            ]
        )
        fig_event.update_layout(
            annotations=[dict(text=f"FG {fg_score}<br>{html.escape(fg_rating)}", showarrow=False, font=dict(size=11, color="#dce8fb"))]
        )
        _style_dashboard_figure(fig_event, height=178, margin=dict(l=8, r=8, t=14, b=2))
        st.plotly_chart(fig_event, use_container_width=True)

    with m3:
        gex_df = (data_0dte or {}).get("df")
        qqq_spot = _safe_float(qqq_price, None)
        gex_ready = (
            gex_df is not None
            and not gex_df.empty
            and "strike" in gex_df.columns
            and "GEX" in gex_df.columns
            and qqq_spot is not None
            and qqq_spot > 0
        )
        if gex_ready:
            strike_map = (
                gex_df.groupby("strike", as_index=False)["GEX"]
                .sum()
                .sort_values("strike")
                .copy()
            )
            window = 0.065
            low = float(qqq_spot * (1.0 - window))
            high = float(qqq_spot * (1.0 + window))
            strike_map = strike_map[(strike_map["strike"] >= low) & (strike_map["strike"] <= high)].copy()
            if strike_map.empty:
                strike_map = (
                    gex_df.groupby("strike", as_index=False)["GEX"]
                    .sum()
                    .assign(spot_dist=lambda d: (d["strike"] - float(qqq_spot)).abs())
                    .nsmallest(26, "spot_dist")
                    .copy()
                )
            if len(strike_map) > 22:
                strike_map = (
                    strike_map.assign(abs_gex=lambda d: d["GEX"].abs())
                    .nlargest(22, "abs_gex")
                    .sort_values("strike")
                    .copy()
                )
            colors = ["#77ddb0" if float(v) >= 0 else "#f29595" for v in strike_map["GEX"]]
            fig_gex = go.Figure(
                data=[
                    go.Bar(
                        x=strike_map["GEX"],
                        y=strike_map["strike"].astype(float),
                        orientation="h",
                        marker=dict(color=colors),
                        text=[f"{float(v)/1_000_000:.1f}M" for v in strike_map["GEX"]],
                        textposition="outside",
                    )
                ]
            )
            fig_gex.add_vline(x=0, line_width=1, line_color="#7e90ab", line_dash="dot")
            g_flip_strike = _safe_float((data_0dte or {}).get("g_flip_strike"), None)
            if g_flip_strike is not None:
                fig_gex.add_hline(
                    y=float(g_flip_strike),
                    line_width=1,
                    line_color="#ffd37f",
                    line_dash="dot",
                    annotation_text="Gamma Flip",
                    annotation_position="top right",
                )
            fig_gex.add_hline(
                y=float(qqq_spot),
                line_width=1,
                line_color="#38d7ff",
                line_dash="dash",
                annotation_text=f"QQQ Spot {float(qqq_spot):.2f}",
                annotation_position="top left",
            )
            fig_gex.update_xaxes(title_text="Net GEX (notional)")
            fig_gex.update_yaxes(title_text="QQQ Strike", tickformat=".2f")
            _style_dashboard_figure(fig_gex, height=370, margin=dict(l=20, r=14, t=34, b=28))
            st.plotly_chart(fig_gex, use_container_width=True)
        else:
            lvl_df = pd.DataFrame(
                [
                    {"Level": "P Wall", "Dist": float(p_wall - nq_now)},
                    {"Level": "S Wall", "Dist": float(s_wall - nq_now)},
                    {"Level": "G Flip", "Dist": float(gf_level - nq_now)},
                    {"Level": "D Neutral", "Dist": float(dn_level - nq_now)},
                    {"Level": "P Floor", "Dist": float(p_floor - nq_now)},
                    {"Level": "S Floor", "Dist": float(s_floor - nq_now)},
                ]
            )
            lvl_df = lvl_df.sort_values("Dist", ascending=False)
            lvl_colors = ["#ff8b8b" if v > 0 else "#54efaa" if v < 0 else "#ffd37f" for v in lvl_df["Dist"]]
            fig_levels = go.Figure(
                data=[
                    go.Bar(
                        x=lvl_df["Dist"],
                        y=lvl_df["Level"],
                        orientation="h",
                        marker=dict(color=lvl_colors),
                        text=[f"{v:+.0f}" for v in lvl_df["Dist"]],
                        textposition="outside",
                    )
                ]
            )
            fig_levels.add_vline(x=0, line_width=1, line_color="#7e90ab", line_dash="dot")
            fig_levels.update_xaxes(title_text="Distance (pts)")
            fig_levels.update_yaxes(title_text="")
            _style_dashboard_figure(fig_levels, height=370, margin=dict(l=28, r=12, t=34, b=28))
            st.plotly_chart(fig_levels, use_container_width=True)

    has_tape = nq_data is not None and not nq_data.empty and "Close" in nq_data.columns
    b1, b2 = st.columns([1.0, 2.0] if has_tape else [1.0, 1.0], gap="small")
    with b1:
        pulse = [
            ("NQ", float(nq_day_change_pct)),
            ("ES", float(_safe_float((market_data.get("es", {}) or {}).get("change_pct"), 0.0) or 0.0)),
            ("YM", float(_safe_float((market_data.get("ym", {}) or {}).get("change_pct"), 0.0) or 0.0)),
            ("RTY", float(_safe_float((market_data.get("rty", {}) or {}).get("change_pct"), 0.0) or 0.0)),
            ("GC", float(_safe_float((market_data.get("gc", {}) or {}).get("change_pct"), 0.0) or 0.0)),
            ("DXY", float(_safe_float((market_data.get("dxy", {}) or {}).get("change_pct"), 0.0) or 0.0)),
            ("VIX", float(_safe_float((market_data.get("vix", {}) or {}).get("change_pct"), 0.0) or 0.0)),
        ]
        pulse_df = pd.DataFrame(pulse, columns=["Asset", "Change"])
        pulse_colors = ["#54efaa" if v >= 0 else "#ff8b8b" for v in pulse_df["Change"]]
        fig_pulse = go.Figure(
            data=[go.Bar(x=pulse_df["Asset"], y=pulse_df["Change"], marker=dict(color=pulse_colors))]
        )
        fig_pulse.add_hline(y=0, line_width=1, line_color="#7e90ab", line_dash="dot")
        fig_pulse.update_yaxes(title_text="%")
        _style_dashboard_figure(fig_pulse, height=220, margin=dict(l=14, r=8, t=30, b=24))
        st.plotly_chart(fig_pulse, use_container_width=True)

        if reaction_stats_df is not None and not reaction_stats_df.empty:
            rs = reaction_stats_df.copy()
            rs["HoldPct"] = pd.to_numeric(
                rs["Hold %"].astype(str).str.replace("%", "", regex=False),
                errors="coerce",
            ).fillna(0.0)
            fig_react = go.Figure(
                data=[
                    go.Bar(
                        x=rs["Level"],
                        y=rs["HoldPct"],
                        marker=dict(color="#38d7ff"),
                        text=[f"{v:.0f}%" for v in rs["HoldPct"]],
                        textposition="outside",
                    )
                ]
            )
            fig_react.update_yaxes(title_text="Hold %", range=[0, 100])
            _style_dashboard_figure(fig_react, height=208, margin=dict(l=14, r=8, t=28, b=44))
            st.plotly_chart(fig_react, use_container_width=True)

    with b2:
        if has_tape:
            tape_df = nq_data.copy()
            close = tape_df["Close"].astype(float).tail(220)
            fig_tape = go.Figure()
            fig_tape.add_trace(
                go.Scatter(
                    x=close.index,
                    y=close.values,
                    mode="lines",
                    line=dict(color="#57dfff", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(56,215,255,0.12)",
                    name="NQ",
                )
            )
            fig_tape.add_hline(y=gf_level, line_color="#ff9b9b", line_dash="dot", annotation_text="GF")
            fig_tape.add_hline(y=dn_level, line_color="#ffd37f", line_dash="dot", annotation_text="DN")
            fig_tape.add_hline(y=p_wall, line_color="#9ee6c2", line_dash="dash", annotation_text="Wall")
            fig_tape.add_hline(y=p_floor, line_color="#9ee6c2", line_dash="dash", annotation_text="Floor")
            fig_tape.update_xaxes(title_text="")
            fig_tape.update_yaxes(title_text="Price")
            _style_dashboard_figure(fig_tape, height=432, margin=dict(l=16, r=12, t=28, b=18))
            st.plotly_chart(fig_tape, use_container_width=True)
        else:
            fallback_rows = [
                {"Metric": "Ratio Quality", "Value": float(ratio_conf)},
                {"Metric": "Bias Score", "Value": float(max(0, min(100, bias_meter)))},
                {"Metric": "Sentiment", "Value": float(max(0, min(100, sentiment_score)))},
                {"Metric": "Fear & Greed", "Value": float(max(0, min(100, fg_score)))},
            ]
            fallback_df = pd.DataFrame(fallback_rows)
            fig_fallback = go.Figure(
                data=[
                    go.Bar(
                        x=fallback_df["Metric"],
                        y=fallback_df["Value"],
                        marker=dict(color=["#38d7ff", "#54efaa", "#ffd37f", "#ff8b8b"]),
                        text=[f"{v:.0f}" for v in fallback_df["Value"]],
                        textposition="outside",
                    )
                ]
            )
            fig_fallback.update_yaxes(title_text="Score", range=[0, 100])
            _style_dashboard_figure(fig_fallback, height=300, margin=dict(l=14, r=10, t=32, b=28))
            st.plotly_chart(fig_fallback, use_container_width=True)
            st.caption("Intraday tape unavailable. Showing structural score snapshot.")

    active_alerts = alert_center or []
    if active_alerts:
        sev_to_cls = {"HIGH": "high", "MED": "med", "LOW": "low"}
        alert_rows = active_alerts[:4]
        alert_cols = st.columns(len(alert_rows)) if alert_rows else []
        for idx, row in enumerate(alert_rows):
            sev = str(row.get("Severity", "LOW")).upper()
            cls = sev_to_cls.get(sev, "low")
            with alert_cols[idx]:
                st.markdown(
                    (
                        f'<div class="viz-alert {cls}">'
                        f'<p class="sev">{sev}</p>'
                        f'<p class="txt">{html.escape(str(row.get("Alert", "Alert")))}</p>'
                        f'<p class="sub">{html.escape(str(row.get("Detail", ""))[:88])}</p>'
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
    else:
        st.caption("No active alerts. Next event: " + next_event_txt)

    st.caption(
        f"Next event: {next_event_txt} | Conviction: {bias_conviction} | "
        f"High impact today: {high_ct} | Medium impact today: {med_ct}"
    )


def _render_clean_dashboard(
    nq_now,
    nq_day_change_pct,
    nq_source,
    qqq_price,
    qqq_source,
    nq_data,
    data_0dte,
    market_data,
    event_risk,
):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🛰 Asset Command Strip</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    es = market_data.get("es", {}) or {}
    rty = market_data.get("rty", {}) or {}
    iwm = market_data.get("iwm", {}) or {}
    dia = market_data.get("dia", {}) or {}
    gc = market_data.get("gc", {}) or {}
    cl = market_data.get("cl", {}) or {}

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    nq_change = float(nq_now * (_safe_float(nq_day_change_pct, 0.0) / 100.0))
    c1.metric("NQ", f"{nq_now:,.2f}", f"{nq_change:+.2f} ({_safe_float(nq_day_change_pct, 0.0):+.2f}%)")
    c1.caption(f"{nq_source} • {get_quote_age_label('NQ=F')}")
    c2.metric("ES", f"{_safe_float(es.get('price'), 0.0):,.2f}", f"{_safe_float(es.get('change_pct'), 0.0):+.2f}%")
    c2.caption(str(es.get("source", "source n/a")))
    c3.metric("IWM", f"{_safe_float(iwm.get('price'), 0.0):,.2f}", f"{_safe_float(iwm.get('change_pct'), 0.0):+.2f}%")
    c3.caption(str(iwm.get("source", "source n/a")))
    c4.metric("DIA", f"{_safe_float(dia.get('price'), 0.0):,.2f}", f"{_safe_float(dia.get('change_pct'), 0.0):+.2f}%")
    c4.caption(str(dia.get("source", "source n/a")))
    c5.metric("GC", f"{_safe_float(gc.get('price'), 0.0):,.2f}", f"{_safe_float(gc.get('change_pct'), 0.0):+.2f}%")
    c5.caption(str(gc.get("source", "source n/a")))
    c6.metric("CL", f"{_safe_float(cl.get('price'), 0.0):,.2f}", f"{_safe_float(cl.get('change_pct'), 0.0):+.2f}%")
    c6.caption(str(cl.get("source", "source n/a")))
    st.markdown("</div></div>", unsafe_allow_html=True)

    main_col, side_col = st.columns([4.6, 1.6], gap="small")
    with main_col:
        st.markdown(
            '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📈 NQ Tape</div></div><div class="terminal-body">',
            unsafe_allow_html=True,
        )
        if nq_data is not None and not nq_data.empty and "Close" in nq_data.columns:
            close = nq_data["Close"].astype(float)
            fig_nq = go.Figure()
            fig_nq.add_trace(
                go.Scatter(
                    x=close.index,
                    y=close.values,
                    mode="lines",
                    line=dict(color="#7ed7ff", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(126,215,255,0.12)",
                    name="NQ",
                )
            )
            if data_0dte:
                fig_nq.add_hline(
                    y=float(data_0dte.get("g_flip_nq", nq_now)),
                    line_color="#ffd37f",
                    line_dash="dot",
                    annotation_text="Gamma Flip",
                )
                fig_nq.add_hline(
                    y=float(data_0dte.get("dn_nq", nq_now)),
                    line_color="#9ee6c2",
                    line_dash="dot",
                    annotation_text="Delta Neutral",
                )
            _style_dashboard_figure(fig_nq, height=370, margin=dict(l=14, r=10, t=24, b=14))
            st.plotly_chart(fig_nq, use_container_width=True)
        else:
            st.info("NQ intraday feed unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)

        st.markdown(
            '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧲 QQQ Gamma by Strike</div></div><div class="terminal-body">',
            unsafe_allow_html=True,
        )
        gex_df = (data_0dte or {}).get("df")
        qqq_spot = _safe_float(qqq_price, None)
        if gex_df is not None and not gex_df.empty and qqq_spot and qqq_spot > 0 and "GEX" in gex_df.columns:
            strike_map = (
                gex_df.groupby("strike", as_index=False)["GEX"]
                .sum()
                .sort_values("strike")
                .copy()
            )
            low = float(qqq_spot * 0.94)
            high = float(qqq_spot * 1.06)
            strike_map = strike_map[(strike_map["strike"] >= low) & (strike_map["strike"] <= high)].copy()
            if strike_map.empty:
                strike_map = (
                    gex_df.groupby("strike", as_index=False)["GEX"]
                    .sum()
                    .assign(spot_dist=lambda d: (d["strike"] - float(qqq_spot)).abs())
                    .nsmallest(24, "spot_dist")
                )
            if len(strike_map) > 28:
                strike_map = (
                    strike_map.assign(abs_gex=lambda d: d["GEX"].abs())
                    .nlargest(28, "abs_gex")
                    .sort_values("strike")
                )
            colors = ["#77ddb0" if float(v) >= 0 else "#f29595" for v in strike_map["GEX"]]
            fig_gex = go.Figure(
                data=[
                    go.Bar(
                        x=strike_map["GEX"],
                        y=strike_map["strike"].astype(float),
                        orientation="h",
                        marker=dict(color=colors),
                        text=[f"{float(v)/1_000_000:.1f}M" for v in strike_map["GEX"]],
                        textposition="outside",
                    )
                ]
            )
            fig_gex.add_vline(x=0, line_color="#7e90ab", line_dash="dot")
            fig_gex.add_hline(
                y=float(qqq_spot),
                line_color="#38d7ff",
                line_dash="dash",
                annotation_text=f"QQQ Spot {float(qqq_spot):.2f}",
            )
            g_flip = _safe_float((data_0dte or {}).get("g_flip_strike"), None)
            if g_flip:
                fig_gex.add_hline(y=float(g_flip), line_color="#ffd37f", line_dash="dot", annotation_text="Gamma Flip")
            fig_gex.update_xaxes(title_text="Net GEX")
            fig_gex.update_yaxes(title_text="QQQ Strike", tickformat=".2f")
            _style_dashboard_figure(fig_gex, height=340, margin=dict(l=14, r=10, t=24, b=14))
            st.plotly_chart(fig_gex, use_container_width=True)
            st.caption(f"QQQ source: {qqq_source}")
        else:
            st.info("QQQ gamma map unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)

    with side_col:
        st.markdown(
            '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🏦 Rates & Macro</div></div><div class="terminal-body">',
            unsafe_allow_html=True,
        )
        tnx = market_data.get("10y", {}) or {}
        dxy = market_data.get("dxy", {}) or {}
        vix = market_data.get("vix", {}) or {}
        vvix = market_data.get("vvix", {}) or {}
        st.metric("US10Y", f"{_safe_float(tnx.get('price'), 0.0):.2f}", f"{_safe_float(tnx.get('change'), 0.0):+.2f}")
        st.metric("DXY", f"{_safe_float(dxy.get('price'), 0.0):.2f}", f"{_safe_float(dxy.get('change_pct'), 0.0):+.2f}%")
        st.metric("VIX", f"{_safe_float(vix.get('price'), 0.0):.2f}", f"{_safe_float(vix.get('change_pct'), 0.0):+.2f}%")
        st.metric("VVIX", f"{_safe_float(vvix.get('price'), 0.0):.2f}", f"{_safe_float(vvix.get('change_pct'), 0.0):+.2f}%")
        nh = (event_risk or {}).get("next_high")
        if nh:
            st.caption(f"Next high-impact: {nh.get('time_et', 'n/a')} {nh.get('event', '')}")
            st.caption(f"Countdown: {_countdown_label(nh.get('seconds_to', 0))}")
        else:
            st.caption("No high-impact events in near horizon.")
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
        "Profitabul-style IB dashboard: dense probabilities, breakout profile, scenario matrix, and session explorer."
    )

    symbol_options = {
        "NQ Futures": "NQ=F",
        "ES Futures": "ES=F",
        "YM Futures": "YM=F",
    }

    c1, c2, c3, c4, c5, c6 = st.columns(6)
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
    with c6:
        layout_mode = st.selectbox(
            "Layout",
            ["Profitabul-style", "Classic"],
            index=0,
            key="ib_layout_mode",
        )

    run_col, info_col = st.columns([1, 4])
    with run_col:
        run_report = st.button("🔄 Run / Refresh IB Report", use_container_width=True)
    with info_col:
        st.caption("Report updates on button click to avoid expensive reruns and keep the panel responsive.")

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
    single_break_pct = float(filtered["single_side_break"].mean() * 100.0)
    no_break_pct = float(filtered["no_break"].mean() * 100.0)
    first_up_pct = float((filtered["first_break"] == "up").mean() * 100.0)
    first_down_pct = float((filtered["first_break"] == "down").mean() * 100.0)
    first_both_pct = float((filtered["first_break"] == "both").mean() * 100.0)
    hit_025_pct = float(filtered["hit_025_any"].mean() * 100.0)
    hit_050_pct = float(filtered["hit_050_any"].mean() * 100.0)
    hit_100_pct = float(filtered["hit_100_any"].mean() * 100.0)
    med_ib_range = float(filtered["ib_range"].median())
    med_ib_range_pct = float(filtered["ib_range_pct"].median())
    med_session_range = float(filtered["session_range"].median()) if "session_range" in filtered.columns else float("nan")
    avg_min_to_break = (
        float(filtered["minutes_to_first_break"].dropna().mean())
        if "minutes_to_first_break" in filtered.columns and filtered["minutes_to_first_break"].notna().any()
        else None
    )
    close_above_mid_pct = float(filtered["close_above_ib_mid"].mean() * 100.0) if "close_above_ib_mid" in filtered.columns else 0.0

    if layout_mode == "Profitabul-style":
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sample Size", f"{total}")
        m2.metric("Single-Side Break", f"{single_break_pct:.1f}%")
        m3.metric("Both-Side Break", f"{both_break_pct:.1f}%")
        m4.metric("No Break Day", f"{no_break_pct:.1f}%")

        mm1, mm2, mm3, mm4 = st.columns(4)
        mm1.metric("Up Break Probability", f"{up_break_pct:.1f}%")
        mm2.metric("Down Break Probability", f"{down_break_pct:.1f}%")
        mm3.metric("Median IB Range", f"{med_ib_range:.1f} pts")
        mm4.metric("Median Session Range", f"{med_session_range:.1f} pts" if not pd.isna(med_session_range) else "n/a")

        mmm1, mmm2, mmm3, mmm4 = st.columns(4)
        mmm1.metric("First Break Up", f"{first_up_pct:.1f}%")
        mmm2.metric("First Break Down", f"{first_down_pct:.1f}%")
        mmm3.metric("Close > IB Mid", f"{close_above_mid_pct:.1f}%")
        mmm4.metric("Avg Min To Break", f"{avg_min_to_break:.0f}m" if avg_min_to_break is not None else "n/a")
    else:
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
        f"Avg Down Extension: {float(filtered['ext_mult_down'].mean()):.2f}x | "
        f"First Break (both): {first_both_pct:.1f}%"
    )

    prob_cols = st.columns([1.2, 1.2, 1.2, 1.2])
    with prob_cols[0]:
        st.metric("Hit 0.25x IB", f"{hit_025_pct:.1f}%")
    with prob_cols[1]:
        st.metric("Hit 0.50x IB", f"{hit_050_pct:.1f}%")
    with prob_cols[2]:
        st.metric("Hit 1.00x IB", f"{hit_100_pct:.1f}%")
    with prob_cols[3]:
        expectancy = float(filtered["ext_mult_up"].mean() - filtered["ext_mult_down"].mean())
        st.metric("Ext Bias (Up-Down)", f"{expectancy:+.2f}x")

    st.markdown("### Directional Probability Block")
    pblock = pd.DataFrame(
        [
            ("Break Up (any)", up_break_pct),
            ("Break Down (any)", down_break_pct),
            ("First Break Up", first_up_pct),
            ("First Break Down", first_down_pct),
            ("Single-Side Day", single_break_pct),
            ("Both-Side Day", both_break_pct),
            ("No Break Day", no_break_pct),
        ],
        columns=["Metric", "Probability %"],
    )
    pblock["Probability %"] = pblock["Probability %"].map(lambda v: round(float(v), 1))
    st.dataframe(pblock, width="stretch", hide_index=True)

    st.markdown("### Conditional Scenario Matrix")
    scen = (
        filtered.groupby(["gap_dir", "open_vs_overnight_mid", "ib_end_vs_vwap"], dropna=False)
        .agg(
            Sessions=("date", "count"),
            UpBreak=("break_up", "mean"),
            DownBreak=("break_down", "mean"),
            NoBreak=("no_break", "mean"),
            FirstUp=("first_break", lambda s: (s == "up").mean()),
            FirstDown=("first_break", lambda s: (s == "down").mean()),
            AvgExtUp=("ext_mult_up", "mean"),
            AvgExtDown=("ext_mult_down", "mean"),
            AvgMinToBreak=("minutes_to_first_break", "mean"),
        )
        .reset_index()
    )
    if not scen.empty:
        scen["Scenario"] = scen.apply(
            lambda r: f"Gap {str(r['gap_dir']).title()} | Open-ON {str(r['open_vs_overnight_mid']).title()} | IB-vVWAP {str(r['ib_end_vs_vwap']).title()}",
            axis=1,
        )
        for col in ["UpBreak", "DownBreak", "NoBreak", "FirstUp", "FirstDown"]:
            scen[col] = scen[col] * 100.0
        min_samp = max(3, int(round(total * 0.06)))
        scen = scen[scen["Sessions"] >= min_samp].copy()
        scen = scen.sort_values(["Sessions", "UpBreak"], ascending=[False, False])
        show_cols = [
            "Scenario",
            "Sessions",
            "UpBreak",
            "DownBreak",
            "NoBreak",
            "FirstUp",
            "FirstDown",
            "AvgExtUp",
            "AvgExtDown",
            "AvgMinToBreak",
        ]
        scen_show = scen[show_cols].copy()
        fmt = {
            "UpBreak": "{:.1f}%",
            "DownBreak": "{:.1f}%",
            "NoBreak": "{:.1f}%",
            "FirstUp": "{:.1f}%",
            "FirstDown": "{:.1f}%",
            "AvgExtUp": "{:.2f}x",
            "AvgExtDown": "{:.2f}x",
            "AvgMinToBreak": "{:.0f}m",
        }
        st.dataframe(scen_show.style.format(fmt), width="stretch", hide_index=True, height=300)
    else:
        st.caption("Not enough filtered samples to build scenario matrix.")

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
        if "minutes_to_first_break" in filtered.columns and filtered["minutes_to_first_break"].notna().any():
            hist_df = filtered[filtered["minutes_to_first_break"].notna()].copy()
            fig_t = px.histogram(
                hist_df,
                x="minutes_to_first_break",
                nbins=24,
                title="Time To First Break (minutes after IB end)",
                color_discrete_sequence=["#00D9FF"],
            )
            fig_t.update_layout(
                template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white",
                height=340,
                margin=dict(l=20, r=20, t=50, b=20),
                xaxis_title="Minutes",
                yaxis_title="Count",
                showlegend=False,
            )
            st.plotly_chart(fig_t, use_container_width=True)
        else:
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

    w1, w2 = st.columns(2)
    with w1:
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
    with w2:
        st.markdown("### Extension Percentiles")
        ext_tbl = pd.DataFrame(
            [
                {
                    "Leg": "Up Extension",
                    "P50": float(filtered["ext_mult_up"].quantile(0.50)),
                    "P75": float(filtered["ext_mult_up"].quantile(0.75)),
                    "P90": float(filtered["ext_mult_up"].quantile(0.90)),
                },
                {
                    "Leg": "Down Extension",
                    "P50": float(filtered["ext_mult_down"].quantile(0.50)),
                    "P75": float(filtered["ext_mult_down"].quantile(0.75)),
                    "P90": float(filtered["ext_mult_down"].quantile(0.90)),
                },
            ]
        )
        st.dataframe(
            ext_tbl.style.format({"P50": "{:.2f}x", "P75": "{:.2f}x", "P90": "{:.2f}x"}),
            width="stretch",
            hide_index=True,
            height=280,
        )

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
        "first_break_time_et",
        "minutes_to_first_break",
        "break_up",
        "break_down",
        "both_break",
        "no_break",
        "ext_mult_up",
        "ext_mult_down",
        "session_range",
        "close_in_ib_pos",
        "high_impact_day",
    ]
    table_df = filtered[table_cols].copy().sort_values("date", ascending=False)
    for col in [
        "ib_range",
        "ib_range_pct",
        "ext_mult_up",
        "ext_mult_down",
        "session_range",
        "close_in_ib_pos",
    ]:
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
    st.subheader("📊 NQ Level Builder")
    st.caption("Update daily/weekly levels and copy the export string.")

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
    if "focus_mode" not in st.session_state:
        st.session_state.focus_mode = True
    if "show_command_bar" not in st.session_state:
        st.session_state.show_command_bar = False
    if "show_futures_strip" not in st.session_state:
        st.session_state.show_futures_strip = False
    if "rail_mode" not in st.session_state:
        st.session_state.rail_mode = "Auto"
    if "lean_overview" not in st.session_state:
        st.session_state.lean_overview = True
    if "show_monthly_views" not in st.session_state:
        st.session_state.show_monthly_views = False
    if "news_signal_mode" not in st.session_state:
        st.session_state.news_signal_mode = "High-Signal"
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

    with st.sidebar.expander("Layout", expanded=False):
        st.checkbox("🗜 Compact Mode", key="compact_mode")

    manual_override = st.sidebar.checkbox("✏️ Manual NQ Price")
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

    level_mapping_note = ""
    feed_status = None

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

        feed_status = _feed_runtime_status(nq_source=nq_source, qqq_source=qqq_source)
        ratio_meta = _compute_tight_ratio(
            nq_now=nq_now,
            qqq_price=qqq_price,
            nq_source=nq_source,
            qqq_source=qqq_source,
            sync_lag_s=feed_status.get("sync_lag_s"),
            max_sync_lag_s=float(feed_status.get("hard_sync_lag_sec", 10)),
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

        ratio_meta, ratio, qqq_price_levels, level_mapping_note = _stabilize_level_mapping(
            nq_now=nq_now,
            qqq_price_live=qqq_price,
            cboe_price=cboe_price,
            ratio_meta=ratio_meta,
        )

        levels_cache_key = "levels_last_good::QQQ"
        cached_levels = st.session_state.get(levels_cache_key)
        freeze_levels = bool((feed_status or {}).get("freeze_levels"))

        data_0dte = None
        data_weekly = None
        data_monthly = None

        if freeze_levels and cached_levels:
            data_0dte = cached_levels.get("data_0dte")
            data_weekly = cached_levels.get("data_weekly")
            data_monthly = cached_levels.get("data_monthly")
            ratio = float(cached_levels.get("ratio", ratio) or ratio)
            ratio_meta = dict(ratio_meta or {})
            ratio_meta["ratio"] = ratio
            ratio_meta["ratio_mode"] = f"{ratio_meta.get('ratio_mode', 'Live')} (frozen snapshot)"
            note_lock = "Level engine locked to last good snapshot due data-quality guardrails."
            level_mapping_note = f"{level_mapping_note} {note_lock}".strip()
        else:
            exp_0dte, exp_weekly, exp_monthly = get_expirations_by_type(df_raw)

            if exp_0dte:
                data_0dte = process_expiration(
                    df_raw, exp_0dte, qqq_price_levels, ratio, nq_now, options_ticker="QQQ"
                )

            if exp_weekly and exp_weekly != exp_0dte:
                data_weekly = process_expiration(
                    df_raw, exp_weekly, qqq_price_levels, ratio, nq_now, options_ticker="QQQ"
                )

            if exp_monthly and exp_monthly not in [exp_0dte, exp_weekly]:
                data_monthly = process_expiration(
                    df_raw, exp_monthly, qqq_price_levels, ratio, nq_now, options_ticker="QQQ"
                )

            if data_0dte and not freeze_levels:
                st.session_state[levels_cache_key] = {
                    "data_0dte": data_0dte,
                    "data_weekly": data_weekly,
                    "data_monthly": data_monthly,
                    "ratio": float(ratio),
                    "saved_at": datetime.now().isoformat(),
                }

        market_data = get_market_overview_yahoo()
        event_risk = get_event_risk_snapshot(finnhub_key, hours_ahead=24)

    nq_data = None
    if data_0dte:
        nq_data = get_nq_intraday_data()

    nav_sections = {
        "Workspace": [("🏠 Dashboard", "🏠 Dashboard")],
        "Tools": [("📊 NQ Level Builder", "📊 NQ Level Builder")],
    }
    available_views = {value for items in nav_sections.values() for _, value in items}
    if st.session_state.get("main_left_nav") not in available_views:
        st.session_state.main_left_nav = "🏠 Dashboard"

    nav_col, center_col = st.columns([0.95, 6.40], gap="small")
    right_col = None

    with nav_col:
        active_view = _render_left_nav(nav_sections)

    with center_col:
        _render_runtime_mode_banner(feed_status)
        if level_mapping_note:
            st.warning(level_mapping_note)
        with st.expander("Data Health & Feed Diagnostics", expanded=False):
            _render_data_health_strip(
                nq_source=nq_source,
                qqq_source=qqq_source,
                ratio_meta=ratio_meta,
                data_0dte=data_0dte,
                market_data=market_data,
                finnhub_key=finnhub_key,
            )
        if active_view == "🏠 Dashboard":
            _render_clean_dashboard(
                nq_now=nq_now,
                nq_day_change_pct=nq_day_change_pct,
                nq_source=nq_source,
                qqq_price=qqq_price,
                qqq_source=qqq_source,
                nq_data=nq_data,
                data_0dte=data_0dte,
                market_data=market_data,
                event_risk=event_risk,
            )
        elif active_view == "📊 NQ Level Builder":
            _render_nq_level_builder_panel(
                data_0dte=data_0dte,
                data_weekly=data_weekly,
            )

    if right_col is not None:
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
                base_news = [
                    article
                    for article in (rss_news or [])
                    if str(article.get("headline", "")).strip()
                ]
                news_mode = str(st.session_state.get("news_signal_mode", "High-Signal"))
                if news_mode == "High-Signal":
                    visible_news = [a for a in base_news if _is_high_signal_news(a)]
                else:
                    visible_news = list(base_news)
                if not visible_news and base_news:
                    visible_news = base_news[:12]
                st.caption(
                    f"{len(visible_news)} headlines • mode: {news_mode} • refreshes on app cycle"
                )
                st.markdown('<div class="news-rail">', unsafe_allow_html=True)
                if visible_news:
                    for article in visible_news[:20]:
                        raw_headline = str(article.get("headline", "No title")).strip()
                        headline_short = (raw_headline[:177] + "…") if len(raw_headline) > 178 else raw_headline
                        headline = html.escape(headline_short)
                        source = html.escape(str(article.get("source", "Unknown")))
                        link = article.get("link", "#")
                        published = html.escape(str(article.get("published", "")))
                        st.markdown(
                            f"""
                            <div class="news-item">
                                <div style="font-weight:700;color:#e9eef7;font-size:14px;line-height:1.3;">{headline}</div>
                                <div style="color:#9da8ba;font-size:11px;margin-top:5px;">{source} • {published}</div>
                                <div style="margin-top:7px;"><a href="{link}" target="_blank">Open</a></div>
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
