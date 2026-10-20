"""Visual skin for the dashboard: palette, CSS, Plotly template and the
card / table / list components used at the top of the main view.

Everything here is presentation only. Data comes in already computed.
"""

from __future__ import annotations

import html
import math

import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

BG = "#0B1120"
PANEL = "#111A2B"
PANEL_2 = "#0E1626"
BORDER = "#1F2A40"
TEXT = "#E6ECF5"
MUTED = "#8A97B0"
BLUE = "#4F7CFF"
ORANGE = "#F2994A"
PURPLE = "#A56BFA"
GREEN = "#2FD3A0"
RED = "#F25F7A"
AMBER = "#F5B84B"
CYAN = "#38BDF8"

ACCENTS = {"blue": BLUE, "orange": ORANGE, "purple": PURPLE, "green": GREEN, "red": RED, "amber": AMBER}


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------------------
# Plotly template
# ---------------------------------------------------------------------------

TEMPLATE_NAME = "gamma_navy"


def register_plotly_template() -> None:
    if TEMPLATE_NAME in pio.templates:
        pio.templates.default = TEMPLATE_NAME
        return
    axis = dict(
        gridcolor="rgba(138,151,176,0.10)",
        zerolinecolor="rgba(138,151,176,0.18)",
        linecolor="rgba(138,151,176,0.18)",
        tickfont=dict(color=MUTED, size=11),
        title=dict(font=dict(color=MUTED, size=11)),
        showspikes=False,
    )
    tpl = go.layout.Template(
        layout=dict(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, system-ui, sans-serif", color=TEXT, size=12),
            colorway=[BLUE, ORANGE, PURPLE, GREEN, RED, CYAN, AMBER],
            xaxis=axis,
            yaxis=axis,
            legend=dict(font=dict(color=MUTED, size=11), bgcolor="rgba(0,0,0,0)"),
            hoverlabel=dict(bgcolor=PANEL, bordercolor=BORDER, font=dict(color=TEXT, family="Inter, sans-serif")),
            margin=dict(l=12, r=12, t=28, b=12),
        )
    )
    pio.templates[TEMPLATE_NAME] = tpl
    pio.templates.default = TEMPLATE_NAME


# ---------------------------------------------------------------------------
# CSS (appended after the legacy theme so it wins)
# ---------------------------------------------------------------------------

SKIN_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');
:root {{
  --sk-bg: {BG}; --sk-panel: {PANEL}; --sk-panel-2: {PANEL_2}; --sk-border: {BORDER};
  --sk-text: {TEXT}; --sk-muted: {MUTED}; --sk-blue: {BLUE}; --sk-orange: {ORANGE};
  --sk-purple: {PURPLE}; --sk-green: {GREEN}; --sk-red: {RED}; --sk-amber: {AMBER};
  --sk-radius: 14px;
}}
.stApp {{
  background: radial-gradient(1200px 600px at 15% -10%, #16213A 0%, var(--sk-bg) 55%) fixed !important;
  color: var(--sk-text) !important;
  font-family: "Inter", system-ui, sans-serif !important;
}}
html, body, [class*="css"], .stMarkdown, .stMarkdown p, label, button, input, textarea {{
  font-family: "Inter", system-ui, sans-serif !important;
}}
[data-testid="stHeader"] {{ background: transparent !important; }}
[data-testid="stMainBlockContainer"], .block-container {{
  padding-top: 1.4rem !important; padding-left: 1.6rem !important; padding-right: 1.6rem !important; max-width: 1680px;
}}
[data-testid="stHorizontalBlock"] {{ gap: 0.9rem !important; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: #0D1424 !important; border-right: 1px solid var(--sk-border) !important; }}
[data-testid="stSidebar"] h2 {{ font-size: 13px !important; color: var(--sk-muted) !important; text-transform: uppercase; letter-spacing: .08em; font-weight: 600 !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] details {{ background: transparent !important; border: 1px solid var(--sk-border) !important; border-radius: 10px !important; }}
.sk-brand {{ display:flex; align-items:center; gap:10px; padding: 2px 2px 14px 2px; margin-bottom: 8px; border-bottom: 1px solid var(--sk-border); }}
.sk-brand-mark {{ width:30px; height:30px; border-radius:9px; display:grid; place-items:center;
  background: linear-gradient(135deg, var(--sk-blue), var(--sk-purple)); color:#fff; font-weight:700; font-size:14px; }}
.sk-brand-name {{ font-weight:700; font-size:16px; color: var(--sk-text); line-height:1.1; }}
.sk-brand-sub {{ font-size:11px; color: var(--sk-muted); }}

/* Generic panel look for Streamlit pieces */
[data-testid="stExpander"] details {{ background: var(--sk-panel) !important; border: 1px solid var(--sk-border) !important; border-radius: var(--sk-radius) !important; }}
[data-testid="stMetric"] {{ background: var(--sk-panel) !important; border: 1px solid var(--sk-border) !important; border-radius: 12px !important; padding: 12px 14px !important; }}
[data-testid="stMetricLabel"] p {{ color: var(--sk-muted) !important; font-size: 12px !important; text-transform: none !important; }}
[data-testid="stMetricValue"] {{ color: var(--sk-text) !important; font-size: 22px !important; font-weight: 600 !important; }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--sk-border) !important; border-radius: 12px !important; overflow: hidden; }}
[data-testid="stPlotlyChart"] {{ background: var(--sk-panel); border: 1px solid var(--sk-border); border-radius: var(--sk-radius); padding: 6px 6px 2px 6px; }}
[data-testid="stAlert"] {{ border-radius: 12px !important; }}
/* Streamlit's chart theme paints the page color behind every chart; let the panel show through. */
[data-testid="stPlotlyChart"] .main-svg {{ background: transparent !important; }}
.stButton > button, .stDownloadButton > button {{ border-radius: 9px !important; border: 1px solid var(--sk-border) !important; background: var(--sk-panel) !important; color: var(--sk-text) !important; }}
.stButton > button:hover {{ border-color: var(--sk-blue) !important; }}
[data-testid="stCaptionContainer"] {{ color: var(--sk-muted) !important; }}

/* Legacy panels, restyled */
.terminal-shell {{ background: transparent !important; border: 0 !important; box-shadow: none !important; margin: 14px 0 6px 0 !important; }}
.terminal-header {{ background: transparent !important; border: 0 !important; padding: 0 !important; color: var(--sk-text) !important;
  font-size: 15px !important; font-weight: 600 !important; text-transform: none !important; letter-spacing: 0 !important; }}
.terminal-body:empty {{ display: none !important; }}
.command-mini-card, .command-status-card, .trade-plan-stat, .health-card, .viz-kpi-card, .viz-alert {{
  background: var(--sk-panel) !important; border: 1px solid var(--sk-border) !important; border-radius: var(--sk-radius) !important; box-shadow: none !important;
}}
.command-mini-card .eyebrow {{ color: var(--sk-muted) !important; letter-spacing: .06em; }}
.command-mini-card .headline {{ font-family: "Inter", sans-serif !important; font-weight: 600 !important; }}
.command-list-item {{ background: var(--sk-panel-2) !important; border: 1px solid var(--sk-border) !important; border-radius: 10px !important; }}

/* Top bar */
.sk-topbar {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin: 0 0 16px 0; flex-wrap: wrap; }}
.sk-title {{ font-size: 22px; font-weight: 700; color: var(--sk-text); margin:0; line-height:1.15; }}
.sk-subtitle {{ font-size: 12.5px; color: var(--sk-muted); margin: 3px 0 0 0; }}
.sk-top-right {{ display:flex; align-items:center; gap:8px; flex-wrap: wrap; }}
.sk-chip {{ display:inline-flex; align-items:center; gap:7px; padding: 7px 12px; border-radius: 9px; font-size: 12.5px; font-weight: 500;
  background: var(--sk-panel); border: 1px solid var(--sk-border); color: var(--sk-text); white-space: nowrap; }}
.sk-chip .dot {{ width:7px; height:7px; border-radius: 50%; display:inline-block; }}
.sk-chip.primary {{ background: var(--sk-blue); border-color: var(--sk-blue); color: #fff; font-weight: 600; }}
.sk-bell {{ position: relative; }}
.sk-bell .count {{ position:absolute; top:-6px; right:-6px; min-width:17px; height:17px; padding:0 4px; border-radius: 9px; background: var(--sk-red);
  color:#fff; font-size: 10px; font-weight: 700; display:grid; place-items:center; }}

/* KPI cards */
.sk-kpi-grid {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-bottom: 16px; }}
.sk-kpi {{ position: relative; overflow: hidden; border-radius: var(--sk-radius); padding: 14px 16px 12px 16px; min-height: 112px;
  border: 1px solid var(--kpi-border); background: linear-gradient(140deg, var(--kpi-tint) 0%, rgba(17,26,43,0.92) 72%); }}
.sk-kpi .label {{ font-size: 13px; color: #C9D3E6; font-weight: 500; margin:0; }}
.sk-kpi .value {{ font-size: 26px; font-weight: 700; color: #fff; margin: 6px 0 2px 0; letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }}
.sk-kpi .sub {{ font-size: 12.5px; font-weight: 600; margin: 0; }}
.sk-kpi .badge {{ position:absolute; top: 12px; right: 12px; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 7px;
  color: var(--kpi-accent); background: var(--kpi-badge); }}
.sk-kpi .spark {{ position:absolute; right: 10px; bottom: 10px; width: 40%; height: 46px; z-index: 0; }}
.sk-kpi .label, .sk-kpi .value, .sk-kpi .sub {{ position: relative; z-index: 1; }}

/* Panels */
.sk-panel {{ background: var(--sk-panel); border: 1px solid var(--sk-border); border-radius: var(--sk-radius); padding: 14px 16px; }}
.sk-panel-head {{ display:flex; align-items:baseline; justify-content:space-between; gap: 10px; margin-bottom: 8px; }}
.sk-panel-title {{ font-size: 15px; font-weight: 600; color: var(--sk-text); margin: 0; }}
.sk-panel-sub {{ font-size: 12px; color: var(--sk-muted); margin: 2px 0 0 0; }}
.sk-section-title {{ font-size: 16px; font-weight: 600; color: var(--sk-text); margin: 18px 0 8px 0; display:flex; justify-content:space-between; align-items:baseline; }}
.sk-section-title .aside {{ font-size: 12px; color: var(--sk-muted); font-weight: 500; }}
.sk-stats {{ display:flex; gap: 22px; flex-wrap: wrap; margin: 2px 0 0 0; }}
.sk-stat .k {{ font-size: 11.5px; color: var(--sk-muted); margin:0; display:flex; align-items:center; gap:6px; }}
.sk-stat .v {{ font-size: 18px; font-weight: 700; color: var(--sk-text); margin: 2px 0 0 0; font-variant-numeric: tabular-nums; }}

/* Activity list */
.sk-activity {{ background: var(--sk-panel); border: 1px solid var(--sk-border); border-radius: var(--sk-radius); padding: 14px 14px 6px 14px; height: 100%; }}
.sk-act-item {{ display:grid; grid-template-columns: 34px 1fr auto; gap: 11px; align-items:center; padding: 9px 2px; border-top: 1px solid rgba(31,42,64,0.7); }}
.sk-act-item:first-of-type {{ border-top: 0; }}
.sk-act-icon {{ width: 34px; height: 34px; border-radius: 9px; display:grid; place-items:center; font-size: 15px; font-weight: 700; }}
.sk-act-title {{ font-size: 13px; font-weight: 600; color: var(--sk-text); margin:0; line-height:1.25; }}
.sk-act-sub {{ font-size: 11.5px; color: var(--sk-muted); margin: 2px 0 0 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 260px; }}
.sk-act-right {{ font-size: 12.5px; font-weight: 600; color: var(--sk-text); text-align:right; white-space: nowrap; }}

/* Table */
.sk-table-wrap {{ background: var(--sk-panel); border: 1px solid var(--sk-border); border-radius: var(--sk-radius); overflow: hidden; }}
.sk-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.sk-table th {{ text-align:left; font-weight: 600; color: var(--sk-muted); font-size: 12px; padding: 10px 14px; background: {PANEL_2}; border-bottom: 1px solid var(--sk-border); }}
.sk-table td {{ padding: 9px 14px; border-bottom: 1px solid rgba(31,42,64,0.65); color: var(--sk-text); font-variant-numeric: tabular-nums; }}
.sk-table tr:last-child td {{ border-bottom: 0; }}
div[data-testid="stMarkdownContainer"] .sk-table th, div[data-testid="stMarkdownContainer"] .sk-table td {{ border-left: 0 !important; border-right: 0 !important; border-top: 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-table {{ margin: 0 !important; display: table !important; }}
.sk-table-wrap {{ overflow-x: auto; }}
.sk-table tr.spot td {{ background: rgba(79,124,255,0.08); }}
.sk-table td.num, .sk-table th.num {{ text-align: right; }}
.sk-pill {{ display:inline-block; padding: 3px 9px; border-radius: 6px; font-size: 11.5px; font-weight: 600; }}
.sk-pos {{ color: var(--sk-green); }} .sk-neg {{ color: var(--sk-red); }} .sk-muted {{ color: var(--sk-muted); }}

/* Streamlit markdown sets p sizes and margins; keep the component typography exact. */
div[data-testid="stMarkdownContainer"] .sk-title {{ font-size: 22px !important; margin: 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-subtitle {{ font-size: 12.5px !important; margin: 3px 0 0 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-kpi .label {{ font-size: 13px !important; margin: 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-kpi .value {{ font-size: 26px !important; margin: 6px 0 2px 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-kpi .sub {{ font-size: 12.5px !important; margin: 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-panel-title {{ font-size: 15px !important; margin: 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-panel-sub {{ font-size: 12px !important; margin: 2px 0 0 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-stat .k {{ font-size: 11.5px !important; margin: 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-stat .v {{ font-size: 18px !important; margin: 2px 0 0 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-act-title {{ font-size: 13px !important; margin: 0 !important; }}
div[data-testid="stMarkdownContainer"] .sk-act-sub {{ font-size: 11.5px !important; margin: 2px 0 0 0 !important; }}

/* Bordered containers act as panels; charts inside them drop their own frame. */
.st-key-sk_overview, .st-key-sk_overview_wrap {{ background: var(--sk-panel) !important; border-color: var(--sk-border) !important; border-radius: var(--sk-radius) !important; }}
.st-key-sk_overview [data-testid="stPlotlyChart"] {{ border: 0 !important; background: transparent !important; padding: 0 !important; }}
.st-key-sk_overview .sk-panel {{ border: 0 !important; background: transparent !important; padding: 2px 2px 0 2px !important; }}

@media (max-width: 1100px) {{ .sk-kpi-grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
@media (max-width: 640px) {{
  .sk-kpi-grid {{ grid-template-columns: 1fr; }}
  .sk-table th:nth-child(5), .sk-table td:nth-child(5), .sk-table th:nth-child(6), .sk-table td:nth-child(6), .sk-table th:nth-child(7), .sk-table td:nth-child(7) {{ display: none; }}
  .sk-table th, .sk-table td {{ padding: 8px 9px !important; font-size: 12px !important; }}
  .sk-table td:first-child {{ white-space: normal; }}
}}
</style>
"""


def pill(text: str, color: str) -> str:
    return f'<span class="sk-pill" style="color:{color};background:{_rgba(color, 0.14)}">{html.escape(str(text))}</span>'


# ---------------------------------------------------------------------------
# Sparkline (inline SVG)
# ---------------------------------------------------------------------------

def sparkline_svg(values, color: str, uid: str, width: int = 160, height: int = 52) -> str:
    vals = [float(v) for v in (values or []) if v is not None and math.isfinite(float(v))]
    if len(vals) < 2:
        return ""
    if len(vals) > 60:
        step = len(vals) / 60.0
        vals = [vals[int(i * step)] for i in range(60)] + [vals[-1]]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pad = 4.0
    pts = [
        (i * (width / (len(vals) - 1)), pad + (height - 2 * pad) * (1.0 - (v - lo) / span))
        for i, v in enumerate(vals)
    ]
    # Catmull-Rom to cubic Bezier for a smooth curve.
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    area = d + f" L{width:.1f},{height:.1f} L0,{height:.1f} Z"
    gid = f"spk-{html.escape(uid)}"
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-hidden="true">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.45"/><stop offset="100%" stop-color="{color}" stop-opacity="0"/>'
        f"</linearGradient></defs>"
        f'<path d="{area}" fill="url(#{gid})" stroke="none"/>'
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def brand_html(title: str = "NQ Gamma Map", sub: str = "Dealer positioning for NQ") -> str:
    return (
        '<div class="sk-brand"><div class="sk-brand-mark">Γ</div>'
        f'<div><div class="sk-brand-name">{html.escape(title)}</div><div class="sk-brand-sub">{html.escape(sub)}</div></div></div>'
    )


def topbar_html(title: str, subtitle: str, chips: list[tuple[str, str]], alert_count: int = 0, primary: str | None = None) -> str:
    chip_html = []
    for text, color in chips:
        dot = f'<span class="dot" style="background:{color}"></span>' if color else ""
        chip_html.append(f'<span class="sk-chip">{dot}{html.escape(text)}</span>')
    bell = (
        '<span class="sk-chip sk-bell">Alerts'
        + (f'<span class="count">{int(alert_count)}</span>' if alert_count else "")
        + "</span>"
    )
    prim = f'<span class="sk-chip primary">{html.escape(primary)}</span>' if primary else ""
    return (
        '<div class="sk-topbar"><div>'
        f'<p class="sk-title">{html.escape(title)}</p><p class="sk-subtitle">{html.escape(subtitle)}</p></div>'
        f'<div class="sk-top-right">{"".join(chip_html)}{bell}{prim}</div></div>'
    )


def kpi_card_html(label: str, value: str, sub: str, sub_color: str, badge: str, accent: str, spark=None, uid: str = "k") -> str:
    color = ACCENTS.get(accent, accent)
    style = (
        f"--kpi-tint:{_rgba(color, 0.30)};--kpi-border:{_rgba(color, 0.38)};"
        f"--kpi-accent:{color};--kpi-badge:{_rgba(color, 0.18)}"
    )
    badge_html = f'<span class="badge">{html.escape(badge)}</span>' if badge else ""
    return (
        f'<div class="sk-kpi" style="{style}">{badge_html}'
        f'<p class="label">{html.escape(label)}</p>'
        f'<p class="value">{html.escape(value)}</p>'
        f'<p class="sub" style="color:{sub_color}">{html.escape(sub)}</p>'
        f"{sparkline_svg(spark, color, uid) if spark is not None else ''}</div>"
    )


def kpi_grid_html(cards: list[str]) -> str:
    return f'<div class="sk-kpi-grid">{"".join(cards)}</div>'


def activity_html(title: str, items: list[dict], aside: str = "") -> str:
    """items: {icon, color, title, sub, right}"""
    rows = []
    for it in items:
        color = ACCENTS.get(it.get("color", "blue"), it.get("color", BLUE))
        rows.append(
            '<div class="sk-act-item">'
            f'<div class="sk-act-icon" style="color:{color};background:{_rgba(color, 0.15)}">{html.escape(str(it.get("icon", "•")))}</div>'
            f'<div><p class="sk-act-title">{html.escape(str(it.get("title", "")))}</p>'
            f'<p class="sk-act-sub">{html.escape(str(it.get("sub", "")))}</p></div>'
            f'<div class="sk-act-right">{html.escape(str(it.get("right", "")))}</div></div>'
        )
    if not rows:
        rows.append('<p class="sk-act-sub" style="padding:8px 2px">Nothing needs attention right now.</p>')
    return (
        '<div class="sk-activity"><div class="sk-panel-head">'
        f'<p class="sk-panel-title">{html.escape(title)}</p><span class="sk-panel-sub">{html.escape(aside)}</span></div>'
        f'{"".join(rows)}</div>'
    )


def table_html(columns: list[tuple[str, str]], rows: list[dict], row_class_key: str = "_class") -> str:
    """columns: (key, header). Header starting with '#' right aligns. Cell values may be pre-rendered HTML."""
    head = "".join(
        f'<th class="{"num" if h.startswith("#") else ""}">{html.escape(h.lstrip("#"))}</th>' for _, h in columns
    )
    body = []
    for r in rows:
        cells = "".join(
            f'<td class="{"num" if h.startswith("#") else ""}">{r.get(k, "")}</td>' for k, h in columns
        )
        body.append(f'<tr class="{r.get(row_class_key, "")}">{cells}</tr>')
    return f'<div class="sk-table-wrap"><table class="sk-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def section_title_html(title: str, aside: str = "") -> str:
    return f'<div class="sk-section-title"><span>{html.escape(title)}</span><span class="aside">{html.escape(aside)}</span></div>'
