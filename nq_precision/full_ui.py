import time
from datetime import datetime, timedelta
import html
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
    get_futures_opening_structure,
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
    .skeleton-box {{
        border: 1px solid #2f3947;
        border-radius: 10px;
        height: 390px;
        background: linear-gradient(90deg, #151d2a 25%, #1e2837 37%, #151d2a 63%);
        background-size: 400% 100%;
        animation: shimmer 1.3s ease-in-out infinite;
    }}
    @keyframes shimmer {{
        0% {{ background-position: 100% 0; }}
        100% {{ background-position: 0 0; }}
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
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">☀️ Morning Playbook</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
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


def _render_level_quality_panel(data_0dte, data_weekly, nq_now):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🎯 Level Quality Engine</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
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

    quality_rows = []
    for name, px in rows:
        base = int((level_conf.get(name, {}) or {}).get("score", 40))
        dist = abs(float(px - nq_now))
        if dist <= 80:
            dist_bonus = 10
        elif dist <= 200:
            dist_bonus = 5
        else:
            dist_bonus = 0

        confl_bonus = 0
        nearest_weekly = None
        if weekly_refs:
            nearest_weekly = min(abs(px - w) for w in weekly_refs)
            if nearest_weekly <= 10:
                confl_bonus = 20
            elif nearest_weekly <= 25:
                confl_bonus = 12
            elif nearest_weekly <= 50:
                confl_bonus = 6

        final_score = int(max(0, min(100, round((base * 0.78) + dist_bonus + confl_bonus))))
        label = "High" if final_score >= 70 else "Medium" if final_score >= 45 else "Low"
        quality_rows.append(
            {
                "Level": name,
                "Price": round(px, 2),
                "Dist (pts)": round(px - nq_now, 1),
                "Base": base,
                "Confluence": 0 if nearest_weekly is None else round(nearest_weekly, 1),
                "Final Score": final_score,
                "Quality": label,
            }
        )

    qdf = pd.DataFrame(quality_rows).sort_values(["Final Score", "Dist (pts)"], ascending=[False, True])
    st.dataframe(qdf, width="stretch", hide_index=True)
    st.caption("Final Score blends base options confidence, distance-to-spot usability, and weekly confluence.")
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_opening_structure_panel(opening):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">⏱ Opening Structure (First 60m)</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
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
    p1.metric("Prior Day High", f"{opening.get('prior_day_high', 0):.2f}" if opening.get("prior_day_high") else "N/A")
    p2.metric("Prior Day Low", f"{opening.get('prior_day_low', 0):.2f}" if opening.get("prior_day_low") else "N/A")
    p3.metric("Prior Day Close", f"{opening.get('prior_day_close', 0):.2f}" if opening.get("prior_day_close") else "N/A")
    p4.metric("Minutes Since Open", f"{int(opening.get('minutes_since_open', 0))}m")

    ib_complete = opening.get("initial_balance_complete", False)
    ib_status = "Complete" if ib_complete else "Building"
    st.markdown(
        f"**Open Type:** `{opening.get('opening_type', 'N/A')}` • "
        f"**IB:** `{ib_status}` • "
        f"**IB High/Low:** `{opening.get('initial_balance_high', 0):.2f}` / `{opening.get('initial_balance_low', 0):.2f}`  "
        if opening.get("initial_balance_high") and opening.get("initial_balance_low")
        else f"**Open Type:** `{opening.get('opening_type', 'N/A')}` • **IB:** `{ib_status}`"
    )
    st.caption(f"{opening.get('opening_note', '')} • asof {opening.get('asof_et', 'n/a')}")
    st.markdown("</div></div>", unsafe_allow_html=True)


def _render_event_risk_panel(event_risk):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🚨 Event-Risk Engine</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
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


def _render_breadth_internals_panel(breadth_data, nq_day_change_pct, es_change_pct):
    st.markdown(
        '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📡 Breadth & Internals (Futures Context)</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
        unsafe_allow_html=True,
    )
    if not breadth_data:
        st.info("Breadth/internals unavailable.")
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

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
        event_risk = get_event_risk_snapshot(finnhub_key, hours_ahead=24)
        breadth_internals = get_futures_breadth_internals()

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
            ("📅 Earnings Calendar", "📅 Earnings Calendar"),
            ("🗓 Economic Calendar", "🗓 Economic Calendar"),
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

                options_freshness = str((data_0dte.get("data_meta", {}) or {}).get("options_freshness", "unknown"))
                econ_freshness = str(get_dataset_freshness("econ_calendar", max_age_sec=120).get("status", "unknown"))
                breadth_freshness = str(get_dataset_freshness("breadth_internals", max_age_sec=90).get("status", "unknown"))
                playbook = _build_morning_playbook(
                    data_0dte=data_0dte,
                    data_weekly=data_weekly,
                    nq_now=nq_now,
                    event_risk=event_risk,
                )
                _render_morning_playbook(
                    playbook=playbook,
                    nq_source=nq_source,
                    options_freshness=options_freshness,
                    econ_freshness=econ_freshness,
                    breadth_freshness=breadth_freshness,
                )
                _render_level_quality_panel(
                    data_0dte=data_0dte,
                    data_weekly=data_weekly,
                    nq_now=nq_now,
                )
                _render_opening_structure_panel(opening_structure)
                _render_event_risk_panel(event_risk)
                _render_breadth_internals_panel(
                    breadth_data=breadth_internals,
                    nq_day_change_pct=nq_day_change_pct,
                    es_change_pct=float((market_data.get("es", {}) or {}).get("change_pct", 0.0)),
                )

                st.markdown(
                    '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📊 Market Sentiment</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
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
                st.markdown("</div></div>", unsafe_allow_html=True)

                st.markdown(
                    '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">🧩 Nasdaq Stocks Heat Map</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
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

                skeleton = st.empty()
                skeleton.markdown('<div class="skeleton-box"></div>', unsafe_allow_html=True)
                heatmap_df = get_nasdaq_heatmap_data(
                    universe=st.session_state.heatmap_universe,
                    size_mode=st.session_state.heatmap_size_mode,
                    timeframe=st.session_state.heatmap_timeframe,
                    custom_symbols=st.session_state.heatmap_custom_symbols,
                )
                skeleton.empty()
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
            st.subheader("📈 Trinity-Style Dealer Exposure")
            st.caption("Two-panel horizontal GEX map for SPY and QQQ (0DTE). Monthly view removed.")

            g1, g2, g3 = st.columns(3)
            with g1:
                strike_window_pct = st.slider(
                    "Strike Window (%)",
                    min_value=1,
                    max_value=20,
                    value=6,
                    step=1,
                    key="gex_window_pct",
                )
            with g2:
                max_rows = st.slider(
                    "Ladder Rows",
                    min_value=20,
                    max_value=120,
                    value=70,
                    step=5,
                    key="gex_max_rows",
                )
            with g3:
                row_mode = st.selectbox(
                    "Row Selection",
                    options=["Top |GEX|", "Nearest Spot"],
                    index=0,
                    key="gex_row_mode",
                )
            st.caption("GEX panel updates on each app refresh cycle (uses short cache TTL).")

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
                window = strike_window_pct / 100.0
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
                        hovertemplate="Strike %{y:.2f}<br>GEX %{z:,.0f}<extra></extra>",
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
                if len(label_df) > 42:
                    key_abs = (
                        label_df.assign(abs_gex=label_df["GEX"].abs())
                        .nlargest(24, "abs_gex")[["strike", "GEX"]]
                    )
                    if spot > 0:
                        key_spot = (
                            label_df.assign(spot_dist=(label_df["strike"] - spot).abs())
                            .nsmallest(14, "spot_dist")[["strike", "GEX"]]
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
                )
                fig.update_yaxes(
                    autorange=False,
                    range=[low, high],
                    tickformat=".0f",
                    showgrid=False,
                )
                st.plotly_chart(fig, use_container_width=True)

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
                '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📊 Earnings Detail</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
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
                '<div class="terminal-shell"><div class="terminal-header"><div class="terminal-title">📰 Live News Feed</div><div class="toolbar-dots">⟳ ⊞ ⚙</div></div><div class="terminal-body">',
                unsafe_allow_html=True,
            )
            rss_news = get_rss_news()
            st.markdown('<div class="news-rail-title">Headlines</div>', unsafe_allow_html=True)
            st.markdown('<div class="news-rail">', unsafe_allow_html=True)
            if rss_news:
                for article in rss_news[:32]:
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
