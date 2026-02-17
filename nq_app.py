import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import re
import finnhub
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────
# PAGE CONFIG & DARK THEME
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="NQ Precision Map",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
<style>
    .main {
        background-color: #0E1117;
    }
    .stMetric {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    .stMetric label {
        color: #888;
        font-size: 14px;
    }
    .stMetric [data-testid="stMetricValue"] {
        font-size: 28px;
        color: #00D9FF;
    }
    h1 {
        color: #00D9FF;
        font-weight: 700;
    }
    h2, h3 {
        color: #FFF;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: #1E1E1E;
        padding: 10px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #888;
        font-weight: 600;
        padding: 10px 20px;
        border-radius: 5px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #00D9FF;
        color: #000;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 NQ Precision Map")
st.markdown("**Real-time GEX & Delta Analysis** • Powered by CBOE Data")

FINNHUB_KEY = "csie7q9r01qt46e7sjm0csie7q9r01qt46e7sjmg"

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.header("⚙️ Settings")
manual_override = st.sidebar.checkbox("✏️ Manual NQ Override")

# ─────────────────────────────────────────────
# DATA FUNCTIONS
# ─────────────────────────────────────────────
@st.cache_data(ttl=60)
def get_cboe_options(ticker="QQQ"):
    try:
        url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{ticker}.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, None
        data = response.json()
        current_price = data["data"]["current_price"]
        options_raw = data["data"]["options"]
        df = pd.DataFrame(options_raw)
        pattern = re.compile(r'^(.+)(\d{6})([PC])(\d+)$')

        def parse_option(row):
            match = pattern.search(row['option'])
            if match:
                exp_str = match.group(2)
                option_type = 'call' if match.group(3) == 'C' else 'put'
                strike = int(match.group(4)) / 1000
                exp_date = datetime.strptime("20" + exp_str, "%Y%m%d")
                return pd.Series({'strike': strike, 'type': option_type, 'expiration': exp_date})
            return pd.Series({'strike': 0, 'type': 'unknown', 'expiration': None})

        parsed = df.apply(parse_option, axis=1)
        df = pd.concat([df, parsed], axis=1)
        df = df[df['type'] != 'unknown'].copy()
        return df, current_price
    except Exception as e:
        st.error(f"CBOE fetch failed: {e}")
        return None, None

@st.cache_data(ttl=10)
def get_nq_price_auto(finnhub_key):
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/NQ=F"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = data['chart']['result'][0]['meta']['regularMarketPrice']
            if price and price > 10000:
                return float(price), "Yahoo Finance"
    except:
        pass
    try:
        nq = yf.Ticker("NQ=F")
        data = nq.history(period="1d", interval="1m")
        if not data.empty:
            return float(data['Close'].iloc[-1]), "yfinance"
    except:
        pass
    return None, "unavailable"

@st.cache_data(ttl=10)
def get_qqq_price(finnhub_key):
    try:
        client = finnhub.Client(api_key=finnhub_key)
        quote = client.quote("QQQ")
        price = quote.get('c', 0)
        if price > 0:
            return float(price)
    except:
        pass
    return None

def get_nearest_expiration(df):
    today = datetime.now().date()
    expirations = sorted(df['expiration'].dropna().unique())
    for exp in expirations:
        if exp.date() >= today:
            days = (exp.date() - today).days
            label = "0DTE" if days == 0 else f"{days}DTE"
            return exp, label
    return None, None

def calculate_delta_neutral(df, qqq_price):
    """Calculate Delta Neutral Level"""
    
    # Create a copy to avoid modifying original df
    df_calc = df.copy()
    
    # Call delta exposure (dealers short calls = long delta)
    calls = df_calc[df_calc['type'] == 'call'].copy()
    calls['delta_notional'] = calls['open_interest'] * calls['delta'] * 100 * qqq_price
    
    # Put delta exposure (dealers long puts = short delta)
    puts = df_calc[df_calc['type'] == 'put'].copy()
    puts['delta_notional'] = puts['open_interest'] * puts['delta'] * 100 * qqq_price * -1
    
    # Combine
    all_delta = pd.concat([calls, puts])
    strike_delta = all_delta.groupby('strike')['delta_notional'].sum().reset_index()
    strike_delta = strike_delta.sort_values('strike')
    strike_delta['cumulative_delta'] = strike_delta['delta_notional'].cumsum()
    
    # Find minimum absolute cumulative delta
    min_idx = strike_delta['cumulative_delta'].abs().idxmin()
    dn_strike = strike_delta.loc[min_idx, 'strike']
    
    # Also calculate total delta exposure for the original df
    df_calc['delta_exposure'] = df_calc.apply(
        lambda x: x['open_interest'] * x['delta'] * 100 * (1 if x['type'] == 'call' else -1),
        axis=1
    )
    
    return dn_strike, strike_delta, df_calc

# Then update the function call:
# Change line 261 from:
dn_strike, strike_delta = calculate_delta_neutral(df, qqq_price)

# To:
dn_strike, strike_delta, df = calculate_delta_neutral(df, qqq_price)

# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────
with st.spinner("🔄 Loading data..."):

    # Get prices
    qqq_price = get_qqq_price(FINNHUB_KEY)
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
            format="%.2f"
        )
        nq_source = "Manual"
    else:
        nq_now, nq_source = get_nq_price_auto(FINNHUB_KEY)
        if not nq_now:
            nq_now = st.sidebar.number_input(
                "NQ Price (auto-fetch failed)",
                min_value=10000.0,
                max_value=50000.0,
                value=24760.0,
                step=0.25,
                format="%.2f"
            )
            nq_source = "Manual Fallback"

    ratio = nq_now / qqq_price if qqq_price > 0 else 0

    # Get options data
    df_raw, cboe_price = get_cboe_options("QQQ")
    if df_raw is None:
        st.error("Failed to fetch options")
        st.stop()

    if qqq_price == 0:
        qqq_price = cboe_price

    target_exp, exp_label = get_nearest_expiration(df_raw)
    if target_exp is None:
        st.error("No valid expirations")
        st.stop()

    df = df_raw[df_raw['expiration'] == target_exp].copy()
    df = df[df['open_interest'] > 0].copy()
    df = df[df['iv'] > 0].copy()
    df = df[(df['strike'] > qqq_price * 0.98) & (df['strike'] < qqq_price * 1.02)].copy()

    if len(df) == 0:
        st.error("No valid options data")
        st.stop()

    # Calculate metrics
    dn_strike, strike_delta = calculate_delta_neutral(df, qqq_price)
    dn_nq = dn_strike * ratio

    total_call_delta = df[df['type'] == 'call']['delta_exposure'].sum()
    total_put_delta = df[df['type'] == 'put']['delta_exposure'].sum()
    net_delta = total_call_delta + total_put_delta

    atm_strike = df.iloc[(df['strike'] - qqq_price).abs().argsort()[:1]]['strike'].values[0]
    atm_opts = df[df['strike'] == atm_strike]
    atm_call = atm_opts[atm_opts['type'] == 'call']
    atm_put = atm_opts[atm_opts['type'] == 'put']

    if len(atm_call) > 0 and len(atm_put) > 0:
        call_mid = (atm_call.iloc[0]['bid'] + atm_call.iloc[0]['ask']) / 2
        put_mid = (atm_put.iloc[0]['bid'] + atm_put.iloc[0]['ask']) / 2
        straddle = call_mid + put_mid
    else:
        straddle = qqq_price * 0.012

    nq_em_full = (straddle * 1.25 if straddle > 0 else qqq_price * 0.012) * ratio
    nq_em_050 = nq_em_full * 0.50
    nq_em_025 = nq_em_full * 0.25

    df['GEX'] = df.apply(
        lambda x: x['open_interest'] * x['gamma'] * (qqq_price ** 2) * 0.01 *
        (1 if x['type'] == 'call' else -1),
        axis=1
    )

    calls = df[df['type'] == 'call'].sort_values('GEX', ascending=False)
    puts = df[df['type'] == 'put'].sort_values('GEX')

    if len(calls) == 0 or len(puts) == 0:
        st.error("Insufficient data")
        st.stop()

    p_wall_strike = calls.iloc[0]['strike']
    p_floor_strike = puts.iloc[0]['strike']

    if p_floor_strike == p_wall_strike and len(puts) > 1:
        p_floor_strike = puts.iloc[1]['strike']

    s_wall_strike = p_wall_strike + 2
    for i in range(1, len(calls)):
        if calls.iloc[i]['strike'] != p_wall_strike:
            s_wall_strike = calls.iloc[i]['strike']
            break

    s_floor_strike = p_floor_strike - 2
    for i in range(1, len(puts)):
        candidate = puts.iloc[i]['strike']
        if candidate != p_floor_strike and candidate != p_wall_strike and candidate != s_wall_strike:
            s_floor_strike = candidate
            break

    g_flip_strike = df.groupby('strike')['GEX'].sum().abs().idxmin()

# ─────────────────────────────────────────────
# DISPLAY - KEY METRICS
# ─────────────────────────────────────────────
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("NQ", f"{nq_now:.2f}", nq_source)
col2.metric("QQQ", f"${qqq_price:.2f}")
col3.metric("Delta Neutral", f"{dn_nq:.2f}", "⚖️")
col4.metric("Net Delta", f"{net_delta:,.0f}", "🟢 Bull" if net_delta > 0 else "🔴 Bear")
col5.metric("Exp Move", f"±{nq_em_full:.0f}")
col6.metric("Exp", exp_label)

st.markdown("---")

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Levels", "📈 GEX Chart", "⚖️ Delta Chart"])

with tab1:
    # Levels table
    results = [
        ("Delta Neutral", dn_nq, 5.0, "⚖️"),
        ("Target Res", (p_wall_strike * ratio) + 35, 3.0, "🎯"),
        ("Primary Wall", p_wall_strike * ratio, 5.0, "🔴"),
        ("Primary Floor", p_floor_strike * ratio, 5.0, "🟢"),
        ("Target Supp", (p_floor_strike * ratio) - 35, 3.0, "🎯"),
        ("Secondary Wall", s_wall_strike * ratio, 3.0, "🟠"),
        ("Secondary Flr", s_floor_strike * ratio, 3.0, "🟡"),
        ("Gamma Flip", g_flip_strike * ratio, 10.0, "⚡"),
        ("Upper 0.50σ", nq_now + nq_em_050, 5.0, "📊"),
        ("Upper 0.25σ", nq_now + nq_em_025, 3.0, "📊"),
        ("Lower 0.25σ", nq_now - nq_em_025, 3.0, "📊"),
        ("Lower 0.50σ", nq_now - nq_em_050, 5.0, "📊")
    ]
    
    results_df = pd.DataFrame(results, columns=['Level', 'Price', 'Width', 'Icon'])
    results_df['Price'] = results_df['Price'].round(2)
    
    st.dataframe(
        results_df[['Icon', 'Level', 'Price', 'Width']].style.format({
            'Price': '{:.2f}',
            'Width': '{:.1f}'
        }),
        use_container_width=True,
        height=500,
        hide_index=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔴 Top Calls**")
        st.dataframe(
            calls[['strike', 'GEX', 'delta', 'open_interest']].head(5),
            use_container_width=True,
            hide_index=True
        )
    with col2:
        st.markdown("**🟢 Top Puts**")
        st.dataframe(
            puts[['strike', 'GEX', 'delta', 'open_interest']].head(5),
            use_container_width=True,
            hide_index=True
        )

with tab2:
    # GEX Chart
    st.subheader("GEX by Strike")
    
    gex_by_strike = df.groupby('strike')['GEX'].sum().reset_index()
    gex_by_strike = gex_by_strike.sort_values('strike')
    
    fig = go.Figure()
    
    # Positive GEX (calls)
    pos_gex = gex_by_strike[gex_by_strike['GEX'] > 0]
    fig.add_trace(go.Bar(
        x=pos_gex['strike'],
        y=pos_gex['GEX'],
        name='Call GEX',
        marker_color='#FF4444',
        hovertemplate='Strike: $%{x:.2f}<br>GEX: %{y:,.0f}<extra></extra>'
    ))
    
    # Negative GEX (puts)
    neg_gex = gex_by_strike[gex_by_strike['GEX'] < 0]
    fig.add_trace(go.Bar(
        x=neg_gex['strike'],
        y=neg_gex['GEX'],
        name='Put GEX',
        marker_color='#44FF44',
        hovertemplate='Strike: $%{x:.2f}<br>GEX: %{y:,.0f}<extra></extra>'
    ))
    
    # Current price line
    fig.add_vline(
        x=qqq_price,
        line_dash="dash",
        line_color="#00D9FF",
        annotation_text="Current Price",
        annotation_position="top"
    )
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor='#0E1117',
        paper_bgcolor='#0E1117',
        xaxis_title="Strike Price",
        yaxis_title="GEX",
        height=500,
        showlegend=True,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    # Delta Chart
    st.subheader("Cumulative Delta by Strike")
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=strike_delta['strike'],
        y=strike_delta['cumulative_delta'],
        mode='lines',
        name='Cumulative Delta',
        line=dict(color='#00D9FF', width=3),
        fill='tozeroy',
        hovertemplate='Strike: $%{x:.2f}<br>Cumulative Δ: %{y:,.0f}<extra></extra>'
    ))
    
    # Zero line
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="white",
        annotation_text="Zero Delta"
    )
    
    # Delta Neutral line
    fig.add_vline(
        x=dn_strike,
        line_dash="dot",
        line_color="#FFD700",
        annotation_text="Delta Neutral",
        annotation_position="top"
    )
    
    # Current price
    fig.add_vline(
        x=qqq_price,
        line_dash="dash",
        line_color="#FF4444",
        annotation_text="Current",
        annotation_position="bottom"
    )
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor='#0E1117',
        paper_bgcolor='#0E1117',
        xaxis_title="Strike Price",
        yaxis_title="Cumulative Delta Exposure",
        height=500,
        showlegend=False,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')} | Data: CBOE • {nq_source}")

if st.sidebar.button("🔄 Refresh", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
