import streamlit as st
import finnhub
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta
from tastytrade import Session
from tastytrade.instruments import Option
from tastytrade.streamer import DXLinkStreamer

st.set_page_config(page_title="NQ Precision Map", layout="wide")

st.title("📊 NQ Complete Precision Map")
st.markdown("Real-time GEX analysis for NQ futures using QQQ options")

# Load credentials from Streamlit secrets
TASTY_USERNAME = st.secrets.get("TASTY_USERNAME", "")
TASTY_PASSWORD = st.secrets.get("TASTY_PASSWORD", "")
FINNHUB_KEY = st.secrets.get("FINNHUB_KEY", "csie7q9r01qt46e7sjm0csie7q9r01qt46e7sjmg")

@st.cache_resource(ttl=3600)
def get_tasty_session(username, password):
    """Create and cache Tastytrade session (refreshes every hour)"""
    try:
        session = Session(username, password)
        return session
    except Exception as e:
        st.error(f"❌ Tastytrade login failed: {e}")
        return None

@st.cache_data(ttl=60)
def get_realtime_options(_session, expiration_date):
    """Fetch real-time options chain from Tastytrade"""
    try:
        # Get all QQQ options for the expiration
        options = Option.get_options(
            _session,
            "QQQ",
            expiration_date=expiration_date
        )
        
        if not options:
            return None
        
        # Get option symbols for streaming
        option_symbols = [opt.streamer_symbol for opt in options]
        
        # Fetch quotes for all options
        import asyncio
        
        async def fetch_quotes():
            quotes = {}
            async with DXLinkStreamer(_session) as streamer:
                await streamer.subscribe(EventType.QUOTE, option_symbols)
                await streamer.subscribe(EventType.GREEKS, option_symbols)
                
                quote_data = {}
                greek_data = {}
                
                # Collect data for all symbols
                timeout = datetime.now() + timedelta(seconds=15)
                while datetime.now() < timeout:
                    try:
                        event = await asyncio.wait_for(streamer.get_event(EventType.QUOTE), timeout=2.0)
                        quote_data[event.event_symbol] = event
                    except asyncio.TimeoutError:
                        pass
                    
                    try:
                        event = await asyncio.wait_for(streamer.get_event(EventType.GREEKS), timeout=2.0)
                        greek_data[event.event_symbol] = event
                    except asyncio.TimeoutError:
                        break
                
                return quote_data, greek_data
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        quote_data, greek_data = loop.run_until_complete(fetch_quotes())
        loop.close()
        
        # Build DataFrame
        rows = []
        for opt in options:
            sym = opt.streamer_symbol
            quote = quote_data.get(sym)
            greek = greek_data.get(sym)
            
            if not quote:
                continue
            
            bid = quote.bid_price if quote.bid_price else 0
            ask = quote.ask_price if quote.ask_price else 0
            iv = greek.volatility if greek and greek.volatility else 0
            gamma = greek.gamma if greek and greek.gamma else 0
            
            rows.append({
                'strike': float(opt.strike_price),
                'type': 'call' if opt.option_type.value == 'C' else 'put',
                'bid': bid,
                'ask': ask,
                'lastPrice': (bid + ask) / 2 if bid and ask else 0,
                'impliedVolatility': iv,
                'gamma': gamma,
                'openInterest': opt.shares_per_contract or 0,
                'volume': 0  # Volume not available via streaming
            })
        
        df = pd.DataFrame(rows)
        return df
    
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
        return df, "yfinance (15min delay)"
    except Exception as e:
        return None, str(e)

def get_expiration():
    """Get nearest expiration date"""
    qqq = yf.Ticker("QQQ")
    today = datetime.now().strftime('%Y-%m-%d')
    available = qqq.options
    
    if today in available:
        return today, "0DTE (Today)"
    
    today_dt = datetime.now()
    future = [(exp, datetime.strptime(exp, '%Y-%m-%d')) 
               for exp in available 
               if datetime.strptime(exp, '%Y-%m-%d') >= today_dt]
    
    if future:
        future.sort(key=lambda x: x[1])
        exp = future[0][0]
        days = (future[0][1] - today_dt).days
        return exp, f"{days}DTE ({exp})"
    
    return None, None

with st.spinner("🔄 Loading data..."):

    # 1. Tastytrade Session
    session = None
    data_source = "yfinance (15min delay)"
    
    if TASTY_USERNAME and TASTY_PASSWORD:
        session = get_tasty_session(TASTY_USERNAME, TASTY_PASSWORD)
        if session:
            st.sidebar.success("✅ Tastytrade Connected")
            data_source = "Tastytrade (Real-Time)"
        else:
            st.sidebar.warning("⚠️ Tastytrade failed, using yfinance")
    else:
        st.sidebar.warning("⚠️ No Tastytrade credentials, using yfinance")

    # 2. Price Anchor (Finnhub)
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
        if not nq_data.empty:
            nq_now = nq_data['Close'].iloc[-1]
        else:
            nq_now = 24780
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
    
    if session:
        df = get_realtime_options(session, target_expiration)
        if df is not None:
            st.sidebar.success("✅ Real-time options loaded")
    
    # Fallback to yfinance if needed
    if df is None:
        st.warning("⚠️ Falling back to yfinance (15min delay)")
        df, error = get_qqq_options_fallback(target_expiration)
        if df is None:
            st.error(f"Failed to fetch options: {error}")
            st.stop()

    # 6. Data Cleaning
    df = df[df['volume'].notna() | (df['openInterest'] > 0)].copy()
    df = df[df['impliedVolatility'].notna() & (df['impliedVolatility'] > 0)].copy()
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
        df['gamma'] = df.apply(lambda x: calc_gamma(qqq_price, x['strike'], x['impliedVolatility']), axis=1)
    
    df['GEX'] = df.apply(lambda x: x['openInterest'] * x['gamma'] * (qqq_price**2) * 0.01 * (1 if x['type'] == 'call' else -1), axis=1)

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
        ("Target Res",    (p_wall_strike * ratio) + 35, 3.0, "🎯"),
        ("Primary Wall",   p_wall_strike * ratio,       5.0, "🔴"),
        ("Primary Floor",  p_floor_strike * ratio,      5.0, "🟢"),
        ("Target Supp",   (p_floor_strike * ratio) - 35, 3.0, "🎯"),
        ("Secondary Wall", s_wall_strike * ratio,       3.0, "🟠"),
        ("Secondary Flr",  s_floor_strike * ratio,      3.0, "🟡"),
        ("Gamma Flip",     g_flip_strike * ratio,       10.0, "⚡"),
        ("Upper 0.50 Dev", nq_now + nq_em_050,          5.0, "📊"),
        ("Upper 0.25 Dev", nq_now + nq_em_025,          3.0, "📊"),
        ("Lower 0.25 Dev", nq_now - nq_em_025,          3.0, "📊"),
        ("Lower 0.50 Dev", nq_now - nq_em_050,          5.0, "📊")
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

# Refresh button
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
