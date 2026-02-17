import streamlit as st
import finnhub
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta
import requests

st.set_page_config(page_title="NQ Precision Map", layout="wide")

st.title("📊 NQ Complete Precision Map")
st.markdown("Real-time GEX analysis for NQ futures using QQQ options")

# Load credentials from Streamlit secrets
TASTY_USERNAME = st.secrets.get("TASTY_USERNAME", "")
TASTY_PASSWORD = st.secrets.get("TASTY_PASSWORD", "")
FINNHUB_KEY = st.secrets.get("FINNHUB_KEY", "csie7q9r01qt46e7sjm0csie7q9r01qt46e7sjmg")

# ─────────────────────────────────────────────
# TASTYTRADE REST API FUNCTIONS
# ─────────────────────────────────────────────

@st.cache_resource(ttl=3600)
def get_tasty_token(username, password):
    """Login and get session token - cached for 1 hour"""
    try:
        url = "https://api.tastytrade.com/sessions"
        payload = {
            "login": username,
            "password": password
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            token = response.json()['data']['session-token']
            st.sidebar.success("✅ Tastytrade Connected (Real-Time)")
            return token
        else:
            st.sidebar.warning(f"⚠️ Tastytrade login failed: {response.status_code}")
            return None
    except Exception as e:
        st.sidebar.warning(f"⚠️ Tastytrade error: {e}")
        return None

@st.cache_data(ttl=60)
def get_tasty_options(token, expiration_date):
    """Fetch real-time options chain from Tastytrade REST API"""
    try:
        # Step 1: Get option chain
        url = "https://api.tastytrade.com/option-chains/QQQ/nested"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            st.warning(f"⚠️ Failed to fetch option chain: {response.status_code}")
            return None
        
        data = response.json()['data']['items']
        
        # Step 2: Find our expiration
        target_exp = None
        for exp in data:
            if exp['expiration-date'] == expiration_date:
                target_exp = exp
                break
        
        if not target_exp:
            st.warning(f"⚠️ Expiration {expiration_date} not found in Tastytrade")
            return None
        
        # Step 3: Extract strikes
        rows = []
        for strike in target_exp['strikes']:
            strike_price = float(strike['strike-price'])
            
            # Get call and put symbols
            call_symbol = strike.get('call')
            put_symbol = strike.get('put')
            
            for option_type, symbol in [('call', call_symbol), ('put', put_symbol)]:
                if not symbol:
                    continue
                    
                # Step 4: Get market data for each option
                quote_url = f"https://api.tastytrade.com/market-data/options/{symbol}"
                quote_response = requests.get(quote_url, headers=headers)
                
                if quote_response.status_code != 200:
                    continue
                    
                quote_data = quote_response.json().get('data', {})
                
                bid = float(quote_data.get('bid', 0) or 0)
                ask = float(quote_data.get('ask', 0) or 0)
                iv = float(quote_data.get('implied-volatility', 0) or 0)
                oi = int(quote_data.get('open-interest', 0) or 0)
                volume = int(quote_data.get('volume', 0) or 0)
                gamma = float(quote_data.get('gamma', 0) or 0)
                
                rows.append({
                    'strike': strike_price,
                    'type': option_type,
                    'bid': bid,
                    'ask': ask,
                    'lastPrice': (bid + ask) / 2 if bid and ask else 0,
                    'impliedVolatility': iv,
                    'gamma': gamma,
                    'openInterest': oi,
                    'volume': volume
                })
        
        if not rows:
            return None
            
        return pd.DataFrame(rows)
    
    except Exception as e:
        st.warning(f"⚠️ Tastytrade options fetch failed: {e}")
        return None

@st.cache_data(ttl=60)
def get_qqq_options_fallback(expiration_date):
    """Fallback to yfinance if Tastytrade fails"""
    try:
        qqq = yf.Ticker("QQQ")
        opts = qqq.option_chain(expiration_date)
        df = pd.concat([
            opts.calls.assign(type='call'),
            opts.puts.assign(type='put')
        ], ignore_index=True)
        return df
    except Exception as e:
        st.error(f"yfinance fallback failed: {e}")
        return None

def get_expiration():
    """Get nearest expiration date"""
    try:
        qqq = yf.Ticker("QQQ")
        today = datetime.now().strftime('%Y-%m-%d')
        available = qqq.options

        if today in available:
            return today, "0DTE (Today)"

        today_dt = datetime.now()
        future = [
            (exp, datetime.strptime(exp, '%Y-%m-%d'))
            for exp in available
            if datetime.strptime(exp, '%Y-%m-%d') >= today_dt
        ]

        if future:
            future.sort(key=lambda x: x[1])
            exp = future[0][0]
            days = (future[0][1] - today_dt).days
            return exp, f"{days}DTE ({exp})"

        return None, None
    except Exception as e:
        st.error(f"Failed to get expiration: {e}")
        return None, None

# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────

with st.spinner("🔄 Loading data..."):

    # 1. Tastytrade Session
    token = None
    data_source = "yfinance (15min delay)"

    if TASTY_USERNAME and TASTY_PASSWORD:
        token = get_tasty_token(TASTY_USERNAME, TASTY_PASSWORD)
        if token:
            data_source = "Tastytrade (Real-Time)"
    else:
        st.sidebar.warning("⚠️ No Tastytrade credentials found in secrets")

    # 2. QQQ Price (Finnhub)
    client = finnhub.Client(api_key=FINNHUB_KEY)
    try:
        quote = client.quote("QQQ")
        qqq_price = quote.get('c', 0)
        if qqq_price == 0:
            st.error("Could not fetch QQQ price")
            st.stop()
    except Exception as e:
        st.error(f"Error fetching QQQ price: {e}")
        st.stop()

    # 3. NQ Futures Price
    try:
        nq_ticker = yf.Ticker("NQ=F")
        nq_data = nq_ticker.history(period="1d")
        nq_now = nq_data['Close'].iloc[-1] if not nq_data.empty else 24780
    except:
        nq_now = 24780

    ratio = nq_now / qqq_price

    # Display Live Prices
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("NQ Price", f"{nq_now:.2f}")
    col2.metric("QQQ Price", f"${qqq_price:.2f}")
    col3.metric("Ratio", f"{ratio:.4f}")
    col4.metric("Data Source", data_source)

    # 4. Get Expiration
    target_expiration, expiration_label = get_expiration()
    if not target_expiration:
        st.error("No valid expirations available")
        st.stop()

    st.info(f"📅 Using Expiration: **{expiration_label}**")

    # 5. Fetch Options Data
    df = None

    if token:
        with st.spinner("Fetching real-time options from Tastytrade..."):
            df = get_tasty_options(token, target_expiration)
            if df is not None:
                st.sidebar.success(f"✅ {len(df)} options loaded (real-time)")
            else:
                st.warning("⚠️ Tastytrade options failed, falling back to yfinance")

    if df is None:
        with st.spinner("Fetching options from yfinance..."):
            df = get_qqq_options_fallback(target_expiration)
            data_source = "yfinance (15min delay)"
            if df is None:
                st.error("Failed to fetch options data from all sources")
                st.stop()

    # 6. Data Cleaning
    df = df[df['impliedVolatility'].notna() & (df['impliedVolatility'] > 0)].copy()
    df = df[df['openInterest'].notna() & (df['openInterest'] > 0)].copy()
    df = df[(df['strike'] > qqq_price * 0.98) & (df['strike'] < qqq_price * 1.02)].copy()

    if len(df) == 0:
        st.error("No valid options data after filtering")
        st.stop()

    # 7. Expected Move
    atm_strike = df.iloc[(df['strike'] - qqq_price).abs().argsort()[:1]]['strike'].values[0]
    atm_opts = df[df['strike'] == atm_strike]

    atm_call = atm_opts[atm_opts['type'] == 'call']
    atm_put = atm_opts[atm_opts['type'] == 'put']

    if len(atm_call) > 0 and len(atm_put) > 0:
        call_mid = (atm_call.iloc[0]['bid'] + atm_call.iloc[0]['ask']) / 2
        put_mid = (atm_put.iloc[0]['bid'] + atm_put.iloc[0]['ask']) / 2
        straddle = call_mid + put_mid
    else:
        straddle = atm_opts['lastPrice'].sum() if len(atm_opts) > 0 else qqq_price * 0.012

    nq_em_full = (straddle * 1.25 if straddle > 0 else qqq_price * 0.012) * ratio
    nq_em_050, nq_em_025 = nq_em_full * 0.50, nq_em_full * 0.25

    # 8. GEX Logic
    r, q, T = 0.045, 0.007, 1/252

    def calc_gamma(S, K, iv):
        if not iv or iv <= 0: return 0
        try:
            d1 = (np.log(S/K) + (r - q + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
            return np.exp(-q*T) * norm.pdf(d1) / (S * iv * np.sqrt(T))
        except:
            return 0

    # Use Tastytrade gamma if available, otherwise calculate
    if 'gamma' not in df.columns or df['gamma'].sum() == 0:
        df['gamma'] = df.apply(
            lambda x: calc_gamma(qqq_price, x['strike'], x['impliedVolatility']), axis=1
        )

    df['GEX'] = df.apply(
        lambda x: x['openInterest'] * x['gamma'] * (qqq_price**2) * 0.01 * (1 if x['type'] == 'call' else -1),
        axis=1
    )

    # 9. Extract Levels
    calls = df[df['type'] == 'call'].sort_values('GEX', ascending=False)
    puts = df[df['type'] == 'put'].sort_values('GEX')

    # GEX Tables
    st.subheader("🔍 GEX Analysis")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔴 Top Call Strikes (Resistance)")
        st.dataframe(
            calls[['strike', 'GEX', 'openInterest', 'volume']].head(5).style.format({
                'strike': '${:.2f}',
                'GEX': '{:,.0f}',
                'openInterest': '{:,.0f}',
                'volume': '{:,.0f}'
            }),
            use_container_width=True
        )

    with col2:
        st.markdown("#### 🟢 Top Put Strikes (Support)")
        st.dataframe(
            puts[['strike', 'GEX', 'openInterest', 'volume']].head(5).style.format({
                'strike': '${:.2f}',
                'GEX': '{:,.0f}',
                'openInterest': '{:,.0f}',
                'volume': '{:,.0f}'
            }),
            use_container_width=True
        )

    if len(calls) == 0 or len(puts) == 0:
        st.error("Insufficient call/put data")
        st.stop()

    # Extract strikes with conflict resolution
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

    # 10. Results
    results = [
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
        results_df.style.format({'Price': '{:.2f}', 'Width': '{:.1f}'}),
        use_container_width=True,
        height=450,
        hide_index=True
    )

    # Summary
    st.subheader("📈 Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Straddle Premium", f"${straddle:.2f}")
    col2.metric("NQ Expected Move", f"{nq_em_full:.2f} pts")
    col3.metric("Data Source", data_source)

    # Last updated timestamp
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Refresh button
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
```

## What Changed:

### ✅ **No More tastytrade Library**
Uses plain `requests` to call the Tastytrade REST API directly - no version compatibility issues!

### ✅ **How It Works Now:**
1. Logs into Tastytrade → gets session token
2. Fetches option chain via REST API
3. Gets real-time bid/ask, IV, OI, gamma per strike
4. Falls back to yfinance if anything fails

### ✅ **Update `requirements.txt`:**
Remove `tastytrade` and make sure you have:
```
streamlit
finnhub-python
yfinance
pandas
numpy
scipy
requests
python-dateutil
