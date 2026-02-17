import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import re
import finnhub
import yfinance as yf

st.set_page_config(page_title="NQ Precision Map", layout="wide")
st.title("📊 NQ Complete Precision Map")
st.markdown("Real-time GEX analysis for NQ futures using QQQ options via CBOE")

FINNHUB_KEY = "csie7q9r01qt46e7sjm0csie7q9r01qt46e7sjmg"

# ─────────────────────────────────────────────
# SIDEBAR SETTINGS
# ─────────────────────────────────────────────
st.sidebar.header("⚙️ Settings")
manual_override = st.sidebar.checkbox("✏️ Manual NQ Price Override")

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
    """Try multiple sources for NQ price"""
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
            return float(data['Close'].iloc[-1]), "yfinance (1min)"
    except:
        pass

    try:
        client = finnhub.Client(api_key=finnhub_key)
        for symbol in ["NQ=F", "NQ1!", "/NQ"]:
            try:
                quote = client.quote(symbol)
                price = quote.get('c', 0)
                if price and price > 10000:
                    return float(price), f"Finnhub ({symbol})"
            except:
                continue
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
            label = "0DTE (Today)" if days == 0 else f"{days}DTE ({exp.strftime('%Y-%m-%d')})"
            return exp, label
    return None, None

def calculate_delta_neutral(df, qqq_price):
    """Calculate Delta Neutral Level"""
    # Net delta for each strike
    df['delta_exposure'] = df.apply(
        lambda x: x['open_interest'] * x['delta'] * 100 * (1 if x['type'] == 'call' else -1),
        axis=1
    )
    
    # Group by strike and sum delta exposure
    strike_delta = df.groupby('strike')['delta_exposure'].sum().reset_index()
    strike_delta = strike_delta.sort_values('strike')
    
    # Find where cumulative delta crosses zero
    strike_delta['cumulative_delta'] = strike_delta['delta_exposure'].cumsum()
    
    # Delta neutral is where cumulative crosses zero
    zero_cross = strike_delta[strike_delta['cumulative_delta'].abs() == strike_delta['cumulative_delta'].abs().min()]
    
    if len(zero_cross) > 0:
        dn_strike = zero_cross.iloc[0]['strike']
    else:
        # Fallback to strike closest to current price
        dn_strike = qqq_price
    
    return dn_strike, strike_delta

# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────
with st.spinner("🔄 Loading data..."):

    # 1. QQQ Price
    qqq_price = get_qqq_price(FINNHUB_KEY)
    if not qqq_price:
        st.error("Could not fetch QQQ price")
        st.stop()

    # 2. NQ Price
    if manual_override:
        nq_now = st.sidebar.number_input(
            "Enter NQ Price",
            min_value=10000.0,
            max_value=50000.0,
            value=24760.0,
            step=0.25,
            format="%.2f"
        )
        nq_source = "Manual Input ✏️"
        st.sidebar.success(f"Using: {nq_now:.2f}")
    else:
        nq_now, nq_source = get_nq_price_auto(FINNHUB_KEY)
        if not nq_now:
            st.sidebar.warning("⚠️ Auto-fetch failed")
            nq_now = st.sidebar.number_input(
                "Auto-fetch failed. Enter NQ Price:",
                min_value=10000.0,
                max_value=50000.0,
                value=24760.0,
                step=0.25,
                format="%.2f"
            )
            nq_source = "Manual Fallback ⚠️"

    ratio = nq_now / qqq_price if qqq_price > 0 else 0

    # 3. CBOE Options Data
    df_raw, cboe_price = get_cboe_options("QQQ")
    if df_raw is None:
        st.error("Failed to fetch CBOE options data")
        st.stop()

    if qqq_price == 0:
        qqq_price = cboe_price

    # 4. Get Nearest Expiration
    target_exp, exp_label = get_nearest_expiration(df_raw)
    if target_exp is None:
        st.error("No valid expirations found")
        st.stop()

    st.info(f"📅 Using Expiration: **{exp_label}**")

    # 5. Filter to Target Expiration
    df = df_raw[df_raw['expiration'] == target_exp].copy()

    # 6. Data Cleaning
    df = df[df['open_interest'] > 0].copy()
    df = df[df['iv'] > 0].copy()
    df = df[(df['strike'] > qqq_price * 0.98) & (df['strike'] < qqq_price * 1.02)].copy()

    if len(df) == 0:
        st.error("No valid options data after filtering")
        st.stop()

    st.sidebar.success(f"✅ {len(df)} options loaded")

    # 7. Calculate Delta Neutral Level
    dn_strike, strike_delta = calculate_delta_neutral(df, qqq_price)
    dn_nq = dn_strike * ratio

    # 8. Calculate Net Delta Exposure
    total_call_delta = df[df['type'] == 'call']['delta_exposure'].sum()
    total_put_delta = df[df['type'] == 'put']['delta_exposure'].sum()
    net_delta = total_call_delta + total_put_delta

    # Display Delta Metrics
    st.subheader("⚖️ Delta Analysis")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "Delta Neutral (QQQ)",
        f"${dn_strike:.2f}",
        f"{'Above' if qqq_price > dn_strike else 'Below'} current"
    )
    col2.metric(
        "Delta Neutral (NQ)",
        f"{dn_nq:.2f}",
        f"{'Above' if nq_now > dn_nq else 'Below'} current"
    )
    col3.metric(
        "Net Delta Exposure",
        f"{net_delta:,.0f}",
        "Bullish" if net_delta > 0 else "Bearish"
    )
    
    delta_sentiment = "🟢 Bullish" if net_delta > 0 else "🔴 Bearish"
    col4.metric("Positioning", delta_sentiment)

    # 9. Live Prices Display
    st.subheader("📊 Live Prices")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("NQ Price", f"{nq_now:.2f}")
    col2.metric("QQQ Price", f"${qqq_price:.2f}")
    col3.metric("Ratio", f"{ratio:.4f}")
    col4.metric("NQ Source", nq_source)
    col5.metric("Options", "CBOE")

    # 10. Expected Move
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

    # 11. GEX Calculation
    df['GEX'] = df.apply(
        lambda x: x['open_interest'] * x['gamma'] * (qqq_price ** 2) * 0.01 *
        (1 if x['type'] == 'call' else -1),
        axis=1
    )

    # 12. Extract Levels
    calls = df[df['type'] == 'call'].sort_values('GEX', ascending=False)
    puts = df[df['type'] == 'put'].sort_values('GEX')

    # GEX Tables
    st.subheader("🔍 GEX Analysis")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔴 Top Call Strikes (Resistance)")
        st.dataframe(
            calls[['strike', 'GEX', 'delta', 'open_interest', 'volume', 'gamma', 'iv']].head(5).style.format({
                'strike': '${:.2f}',
                'GEX': '{:,.0f}',
                'delta': '{:.4f}',
                'open_interest': '{:,.0f}',
                'volume': '{:,.0f}',
                'gamma': '{:.4f}',
                'iv': '{:.2%}'
            }),
            use_container_width=True
        )

    with col2:
        st.markdown("#### 🟢 Top Put Strikes (Support)")
        st.dataframe(
            puts[['strike', 'GEX', 'delta', 'open_interest', 'volume', 'gamma', 'iv']].head(5).style.format({
                'strike': '${:.2f}',
                'GEX': '{:,.0f}',
                'delta': '{:.4f}',
                'open_interest': '{:,.0f}',
                'volume': '{:,.0f}',
                'gamma': '{:.4f}',
                'iv': '{:.2%}'
            }),
            use_container_width=True
        )

    if len(calls) == 0 or len(puts) == 0:
        st.error("Insufficient call/put data")
        st.stop()

    # 13. Strike Extraction
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

    # 14. Results Assembly
    results = [
        ("Delta Neutral",  dn_nq,                         5.0,  "⚖️"),
        ("Target Res",    (p_wall_strike * ratio) + 35,  3.0,  "🎯"),
        ("Primary Wall",   p_wall_strike * ratio,         5.0,  "🔴"),
        ("Primary Floor",  p_floor_strike * ratio,        5.0,  "🟢"),
        ("Target Supp",   (p_floor_strike * ratio) - 35,  3.0,  "🎯"),
        ("Secondary Wall", s_wall_strike * ratio,         3.0,  "🟠"),
        ("Secondary Flr",  s_floor_strike * ratio,        3.0,  "🟡"),
        ("Gamma Flip",     g_flip_strike * ratio,         10.0, "⚡"),
        ("Upper 0.50 Dev", nq_now + nq_em_050,            5.0,  "📊"),
        ("Upper 0.25 Dev", nq_now + nq_em_025,            3.0,  "📊"),
        ("Lower 0.25 Dev", nq_now - nq_em_025,            3.0,  "📊"),
        ("Lower 0.50 Dev", nq_now - nq_em_050,            5.0,  "📊")
    ]

    st.subheader("🎯 NQ Precision Levels")

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

    # 15. Summary
    st.subheader("📈 Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Straddle Premium", f"${straddle:.2f}")
    col2.metric("NQ Expected Move", f"{nq_em_full:.2f} pts")
    col3.metric("ATM Strike", f"${atm_strike:.2f}")
    col4.metric("Options Loaded", f"{len(df)}")

    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Options: CBOE | NQ: {nq_source}")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
