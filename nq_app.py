import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import finnhub
import yfinance as yf
import plotly.graph_objects as go

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
st.markdown("**Multi-Timeframe GEX & Delta Analysis** • Powered by CBOE Data")

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

@st.cache_data(ttl=300)
def get_market_overview(finnhub_key):
    """Get VIX, futures, yields - SAFE VERSION"""
    client = finnhub.Client(api_key=finnhub_key)
    data = {}
    
    symbols = {
        'vix': '^VIX',
        'es': 'ES=F',
        'ym': 'YM=F',
        'rty': 'RTY=F',
        '10y': '^TNX',
        'dxy': 'DX-Y.NYB'
    }
    
    for key, symbol in symbols.items():
        try:
            quote = client.quote(symbol)
            data[key] = {
                'price': quote.get('c', 0) or 0,
                'change': quote.get('d', 0) or 0,
                'change_pct': quote.get('dp', 0) or 0
            }
        except Exception as e:
            data[key] = {'price': 0, 'change': 0, 'change_pct': 0}
    
    return data

@st.cache_data(ttl=3600)
def get_economic_calendar(finnhub_key):
    """Get today's economic events"""
    client = finnhub.Client(api_key=finnhub_key)
    today = datetime.now().date()
    
    try:
        calendar = client.economic_calendar()
        
        today_events = [
            event for event in calendar.get('economicCalendar', [])
            if event.get('time', '').startswith(str(today))
        ]
        
        today_events.sort(key=lambda x: x.get('time', ''))
        
        return today_events[:10]
    except:
        return []

@st.cache_data(ttl=600)
def get_market_news(finnhub_key):
    """Get latest market news"""
    client = finnhub.Client(api_key=finnhub_key)
    
    try:
        news = client.general_news('general', min_id=0)
        major_sources = ['Bloomberg', 'CNBC', 'Reuters', 'WSJ', 'MarketWatch']
        filtered = [
            n for n in news[:50]
            if any(source.lower() in n.get('source', '').lower() for source in major_sources)
        ]
        return filtered[:10]
    except:
        return []

@st.cache_data(ttl=300)
def get_fear_greed_index():
    """Get Fear & Greed Index"""
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            score = data.get('fear_and_greed', {}).get('score', 50)
            rating = data.get('fear_and_greed', {}).get('rating', 'Neutral')
            return {'score': score, 'rating': rating}
    except:
        pass
    return {'score': 50, 'rating': 'Neutral'}

@st.cache_data(ttl=300)
def get_top_movers(finnhub_key):
    """Get top gainers and losers"""
    client = finnhub.Client(api_key=finnhub_key)
    
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'AMD', 
               'NFLX', 'DIS', 'BABA', 'JPM', 'BAC', 'XOM', 'CVX']
    
    movers = []
    try:
        for ticker in tickers:
            quote = client.quote(ticker)
            movers.append({
                'symbol': ticker,
                'price': quote.get('c', 0),
                'change': quote.get('d', 0),
                'change_pct': quote.get('dp', 0)
            })
        
        movers.sort(key=lambda x: abs(x['change_pct']), reverse=True)
        
        gainers = [m for m in movers if m['change_pct'] > 0][:5]
        losers = [m for m in movers if m['change_pct'] < 0][:5]
        
        return {'gainers': gainers, 'losers': losers}
    except:
        return {'gainers': [], 'losers': []}

def get_expirations_by_type(df):
    """Get nearest 0DTE, Weekly, and Monthly expirations"""
    today = datetime.now().date()
    expirations = sorted(df['expiration'].dropna().unique())
    
    dte_0 = None
    weekly = None
    monthly = None
    
    for exp in expirations:
        exp_date = exp.date() if isinstance(exp, datetime) else exp
        if exp_date < today:
            continue
        
        days = (exp_date - today).days
        
        if days == 0 and dte_0 is None:
            dte_0 = exp
        
        if 1 <= days <= 7 and weekly is None and exp_date.weekday() == 4:
            weekly = exp
        
        if days >= 14 and monthly is None:
            monthly = exp
    
    if dte_0 is None and len(expirations) > 0:
        for exp in expirations:
            exp_date = exp.date() if isinstance(exp, datetime) else exp
            if exp_date >= today:
                dte_0 = exp
                break
    
    if weekly is None and len(expirations) > 1:
        for exp in expirations:
            exp_date = exp.date() if isinstance(exp, datetime) else exp
            if exp_date > today and exp != dte_0:
                weekly = exp
                break
    
    if monthly is None and len(expirations) > 0:
        monthly = expirations[-1]
    
    return dte_0, weekly, monthly

def calculate_delta_neutral(df, qqq_price):
    """Calculate Delta Neutral Level"""
    df_calc = df.copy()
    
    calls = df_calc[df_calc['type'] == 'call'].copy()
    calls['delta_notional'] = calls['open_interest'] * calls['delta'] * 100 * qqq_price
    
    puts = df_calc[df_calc['type'] == 'put'].copy()
    puts['delta_notional'] = puts['open_interest'] * puts['delta'] * 100 * qqq_price * -1
    
    all_delta = pd.concat([calls, puts])
    strike_delta = all_delta.groupby('strike')['delta_notional'].sum().reset_index()
    strike_delta = strike_delta.sort_values('strike')
    strike_delta['cumulative_delta'] = strike_delta['delta_notional'].cumsum()
    
    min_idx = strike_delta['cumulative_delta'].abs().idxmin()
    dn_strike = strike_delta.loc[min_idx, 'strike']
    
    df_calc['delta_exposure'] = df_calc.apply(
        lambda x: x['open_interest'] * x['delta'] * 100 * (1 if x['type'] == 'call' else -1),
        axis=1
    )
    
    return dn_strike, strike_delta, df_calc

def process_expiration(df_raw, target_exp, qqq_price, ratio, nq_now):
    """Process single expiration and return all analysis"""
    df = df_raw[df_raw['expiration'] == target_exp].copy()
    df = df[df['open_interest'] > 0].copy()
    df = df[df['iv'] > 0].copy()
    df = df[(df['strike'] > qqq_price * 0.98) & (df['strike'] < qqq_price * 1.02)].copy()
    
    if len(df) == 0:
        return None
    
    # Calculate DN
    dn_strike, strike_delta, df = calculate_delta_neutral(df, qqq_price)
    dn_nq = dn_strike * ratio
    
    # Net Delta
    total_call_delta = df[df['type'] == 'call']['delta_exposure'].sum()
    total_put_delta = df[df['type'] == 'put']['delta_exposure'].sum()
    net_delta = total_call_delta + total_put_delta
    
    # Expected Move
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
    
    # GEX
    df['GEX'] = df.apply(
        lambda x: x['open_interest'] * x['gamma'] * (qqq_price ** 2) * 0.01 *
        (1 if x['type'] == 'call' else -1),
        axis=1
    )
    
    # Levels - FIXED LOGIC
    calls = df[df['type'] == 'call'].sort_values('GEX', ascending=False)
    puts = df[df['type'] == 'put'].sort_values('GEX', ascending=True)
    
    p_wall_strike = calls.iloc[0]['strike'] if len(calls) > 0 else qqq_price
    p_floor_strike = puts.iloc[0]['strike'] if len(puts) > 0 else qqq_price
    
    if p_floor_strike == p_wall_strike and len(puts) > 1:
        p_floor_strike = puts.iloc[1]['strike']
    
    # Secondary Wall - must be ABOVE primary wall
    s_wall_strike = p_wall_strike
    for i in range(1, len(calls)):
        candidate = calls.iloc[i]['strike']
        if candidate > p_wall_strike:
            s_wall_strike = candidate
            break
    
    # Secondary Floor - must be BELOW primary floor
    s_floor_strike = p_floor_strike
    for i in range(1, len(puts)):
        candidate = puts.iloc[i]['strike']
        if (candidate < p_floor_strike and 
            candidate != p_wall_strike and 
            candidate != s_wall_strike):
            s_floor_strike = candidate
            break
    
    g_flip_strike = df.groupby('strike')['GEX'].sum().abs().idxmin()
    
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
    
    return {
        'df': df,
        'dn_strike': dn_strike,
        'dn_nq': dn_nq,
        'g_flip_strike': g_flip_strike,
        'g_flip_nq': g_flip_strike * ratio,
        'net_delta': net_delta,
        'p_wall': p_wall_strike * ratio,
        'p_floor': p_floor_strike * ratio,
        'calls': calls,
        'puts': puts,
        'strike_delta': strike_delta,
        'results': results,
        'straddle': straddle,
        'nq_em_full': nq_em_full,
        'atm_strike': atm_strike
    }

# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────
with st.spinner("🔄 Loading multi-timeframe data..."):

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
        data_weekly = process_expiration(df_raw, exp_weekly, qqq_price, ratio, nq_now)
    
    if exp_monthly and exp_monthly not in [exp_0dte, exp_weekly]:
        data_monthly = process_expiration(df_raw, exp_monthly, qqq_price, ratio, nq_now)

# ─────────────────────────────────────────────
# COMPACT HEADER METRICS
# ─────────────────────────────────────────────
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
    delta_0 = "🟢 Bullish" if data_0dte['net_delta'] > 0 else "🔴 Bearish"
    delta_w = "🟢 Bullish" if data_weekly['net_delta'] > 0 else "🔴 Bearish"
    col5.metric("📊 Net Delta (0DTE)", f"{data_0dte['net_delta']:,.0f}", delta_0)
    col6.metric("📊 Net Delta (Weekly)", f"{data_weekly['net_delta']:,.0f}", delta_w)
elif data_0dte:
    col1, col2, col3 = st.columns(3)
    col1.metric("⚖️ Delta Neutral", f"{data_0dte['dn_nq']:.2f}")
    col2.metric("⚡ Gamma Flip", f"{data_0dte['g_flip_nq']:.2f}")
    delta_sentiment = "🟢 Bullish" if data_0dte['net_delta'] > 0 else "🔴 Bearish"
    col3.metric("📊 Net Delta", f"{data_0dte['net_delta']:,.0f}", delta_sentiment)
elif data_weekly:
    col1, col2, col3 = st.columns(3)
    col1.metric("⚖️ Delta Neutral", f"{data_weekly['dn_nq']:.2f}")
    col2.metric("⚡ Gamma Flip", f"{data_weekly['g_flip_nq']:.2f}")
    delta_sentiment = "🟢 Bullish" if data_weekly['net_delta'] > 0 else "🔴 Bearish"
    col3.metric("📊 Net Delta", f"{data_weekly['net_delta']:,.0f}", delta_sentiment)

st.markdown("---")

# ─────────────────────────────────────────────
# MULTI-TIMEFRAME OVERVIEW
# ─────────────────────────────────────────────
st.subheader("🎯 Multi-Timeframe Key Levels")

overview_data = []

if data_0dte:
    days = (exp_0dte.date() - datetime.now().date()).days
    label = "0DTE" if days == 0 else f"{days}DTE"
    overview_data.append({
        'Timeframe': label,
        'Expiration': exp_0dte.strftime('%Y-%m-%d'),
        'Delta Neutral': data_0dte['dn_nq'],
        'Gamma Flip': data_0dte['g_flip_nq'],
        'Primary Wall': data_0dte['p_wall'],
        'Primary Floor': data_0dte['p_floor'],
        'Net Delta': data_0dte['net_delta']
    })

if data_weekly:
    days = (exp_weekly.date() - datetime.now().date()).days
    label = f"Weekly ({days}D)"
    overview_data.append({
        'Timeframe': label,
        'Expiration': exp_weekly.strftime('%Y-%m-%d'),
        'Delta Neutral': data_weekly['dn_nq'],
        'Gamma Flip': data_weekly['g_flip_nq'],
        'Primary Wall': data_weekly['p_wall'],
        'Primary Floor': data_weekly['p_floor'],
        'Net Delta': data_weekly['net_delta']
    })

if data_monthly:
    days = (exp_monthly.date() - datetime.now().date()).days
    label = f"Monthly ({days}D)"
    overview_data.append({
        'Timeframe': label,
        'Expiration': exp_monthly.strftime('%Y-%m-%d'),
        'Delta Neutral': data_monthly['dn_nq'],
        'Gamma Flip': data_monthly['g_flip_nq'],
        'Primary Wall': data_monthly['p_wall'],
        'Primary Floor': data_monthly['p_floor'],
        'Net Delta': data_monthly['net_delta']
    })

if overview_data:
    overview_df = pd.DataFrame(overview_data)
    st.dataframe(
        overview_df.style.format({
            'Delta Neutral': '{:.2f}',
            'Gamma Flip': '{:.2f}',
            'Primary Wall': '{:.2f}',
            'Primary Floor': '{:.2f}',
            'Net Delta': '{:,.0f}'
        }),
        width='stretch',
        hide_index=True
    )

st.markdown("---")

# ─────────────────────────────────────────────
# DETAILED TABS
# ─────────────────────────────────────────────
tab_names = ["📈 Market Overview"]
if data_0dte: tab_names.append("📊 0DTE Levels")
if data_weekly: tab_names.append("📊 Weekly Levels")
if data_monthly: tab_names.append("📊 Monthly Levels")
tab_names.extend(["📈 GEX Charts", "⚖️ Delta Charts"])

if tab_names:
    tabs = st.tabs(tab_names)
    
    tab_idx = 0
    
    # Market Overview Tab
    with tabs[tab_idx]:
        st.subheader("📈 Market Overview")
        
        with st.spinner("Loading market data..."):
            market_data = get_market_overview(FINNHUB_KEY)
            
            if market_data:
                st.markdown("### Futures & Indices")
                col1, col2, col3, col4 = st.columns(4)
                
                # ES - SAFE ACCESS
                if 'es' in market_data and market_data['es']['price']:
                    es = market_data['es']
                    col1.metric(
                        "S&P 500 (ES)",
                        f"{es['price']:.2f}",
                        f"{es.get('change', 0):+.2f} ({es.get('change_pct', 0):+.2f}%)"
                    )
                else:
                    col1.metric("S&P 500 (ES)", "N/A")
                
                # NQ
                col2.metric(
                    "Nasdaq (NQ)",
                    f"{nq_now:.2f}",
                    nq_source
                )
                
                # YM - SAFE ACCESS
                if 'ym' in market_data and market_data['ym']['price']:
                    ym = market_data['ym']
                    col3.metric(
                        "Dow (YM)",
                        f"{ym['price']:.2f}",
                        f"{ym.get('change', 0):+.2f} ({ym.get('change_pct', 0):+.2f}%)"
                    )
                else:
                    col3.metric("Dow (YM)", "N/A")
                
                # RTY - SAFE ACCESS
                if 'rty' in market_data and market_data['rty']['price']:
                    rty = market_data['rty']
                    col4.metric(
                        "Russell (RTY)",
                        f"{rty['price']:.2f}",
                        f"{rty.get('change', 0):+.2f} ({rty.get('change_pct', 0):+.2f}%)"
                    )
                else:
                    col4.metric("Russell (RTY)", "N/A")
                
                st.markdown("---")
                st.markdown("### Market Indicators")
                col1, col2, col3 = st.columns(3)
                
                # VIX - SAFE ACCESS
                if 'vix' in market_data and market_data['vix']['price']:
                    vix = market_data['vix']
                    col1.metric(
                        "VIX (Volatility)",
                        f"{vix['price']:.2f}",
                        f"{vix.get('change', 0):+.2f} ({vix.get('change_pct', 0):+.2f}%)"
                    )
                else:
                    col1.metric("VIX (Volatility)", "N/A")
                
                # 10Y - SAFE ACCESS
                if '10y' in market_data and market_data['10y']['price']:
                    tnx = market_data['10y']
                    col2.metric(
                        "10Y Treasury",
                        f"{tnx['price']:.2f}%",
                        f"{tnx.get('change', 0):+.2f}"
                    )
                else:
                    col2.metric("10Y Treasury", "N/A")
                
                # DXY - SAFE ACCESS
                if 'dxy' in market_data and market_data['dxy']['price']:
                    dxy = market_data['dxy']
                    col3.metric(
                        "Dollar Index",
                        f"{dxy['price']:.2f}",
                        f"{dxy.get('change', 0):+.2f} ({dxy.get('change_pct', 0):+.2f}%)"
                    )
                else:
                    col3.metric("Dollar Index", "N/A")
            else:
                st.warning("Market data temporarily unavailable")
        
        st.markdown("---")
        
        st.markdown("### Market Sentiment")
        fg = get_fear_greed_index()
        
        col1, col2 = st.columns([1, 3])
        with col1:
            st.metric("Fear & Greed Index", f"{fg['score']:.0f}", fg['rating'])
        
        with col2:
            if fg['score'] < 25:
                st.error(f"**{fg['rating']}** - Extreme fear typically signals buying opportunity")
            elif fg['score'] < 45:
                st.warning(f"**{fg['rating']}** - Cautious sentiment")
            elif fg['score'] < 55:
                st.info(f"**{fg['rating']}** - Balanced market")
            elif fg['score'] < 75:
                st.warning(f"**{fg['rating']}** - Greedy sentiment")
            else:
                st.error(f"**{fg['rating']}** - Extreme greed signals potential top")
        
        st.markdown("---")
        
        st.markdown("### Top Movers")
        movers = get_top_movers(FINNHUB_KEY)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🟢 Top Gainers**")
            if movers['gainers']:
                gainers_df = pd.DataFrame(movers['gainers'])
                st.dataframe(
                    gainers_df[['symbol', 'price', 'change_pct']].style.format({
                        'price': '${:.2f}',
                        'change_pct': '{:+.2f}%'
                    }),
                    width='stretch',
                    hide_index=True
                )
            else:
                st.info("No data available")
        
        with col2:
            st.markdown("**🔴 Top Losers**")
            if movers['losers']:
                losers_df = pd.DataFrame(movers['losers'])
                st.dataframe(
                    losers_df[['symbol', 'price', 'change_pct']].style.format({
                        'price': '${:.2f}',
                        'change_pct': '{:+.2f}%'
                    }),
                    width='stretch',
                    hide_index=True
                )
            else:
                st.info("No data available")
        
        st.markdown("---")
        
        st.markdown("### 📅 Today's Economic Events")
        events = get_economic_calendar(FINNHUB_KEY)
        
        if events:
            events_data = []
            for event in events:
                time_str = event.get('time', '')[:10] if event.get('time') else 'N/A'
                events_data.append({
                    'Time': time_str,
                    'Event': event.get('event', 'Unknown'),
                    'Impact': event.get('impact', 'N/A'),
                    'Country': event.get('country', 'US')
                })
            
            events_df = pd.DataFrame(events_data)
            st.dataframe(events_df, width='stretch', hide_index=True)
        else:
            st.info("No major economic events today")
        
        st.markdown("---")
        
        st.markdown("### 📰 Latest Market News")
        news = get_market_news(FINNHUB_KEY)
        
        if news:
            for article in news[:5]:
                with st.expander(f"**{article.get('headline', 'No title')}** - {article.get('source', 'Unknown')}"):
                    st.markdown(f"*{article.get('summary', 'No summary available')}*")
                    st.markdown(f"[Read more]({article.get('url', '#')})")
                    st.caption(f"Published: {datetime.fromtimestamp(article.get('datetime', 0)).strftime('%Y-%m-%d %H:%M')}")
        else:
            st.info("No news available")
    
    tab_idx += 1
    
    # 0DTE Levels Tab
    if data_0dte:
        with tabs[tab_idx]:
            st.subheader(f"0DTE Analysis - {exp_0dte.strftime('%Y-%m-%d')}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Delta Neutral", f"{data_0dte['dn_nq']:.2f}")
            col2.metric("Gamma Flip", f"{data_0dte['g_flip_nq']:.2f}")
            col3.metric("Net Delta", f"{data_0dte['net_delta']:,.0f}", "🟢 Bull" if data_0dte['net_delta'] > 0 else "🔴 Bear")
            col4.metric("Expected Move", f"±{data_0dte['nq_em_full']:.0f}")
            
            results_df = pd.DataFrame(data_0dte['results'], columns=['Level', 'Price', 'Width', 'Icon'])
            results_df['Price'] = results_df['Price'].round(2)
            st.dataframe(
                results_df[['Icon', 'Level', 'Price', 'Width']].style.format({
                    'Price': '{:.2f}',
                    'Width': '{:.1f}'
                }),
                width='stretch',
                height=500,
                hide_index=True
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🔴 Top Call Strikes**")
                st.dataframe(
                    data_0dte['calls'][['strike', 'GEX', 'delta', 'open_interest', 'volume']].head(5),
                    width='stretch',
                    hide_index=True
                )
            with col2:
                st.markdown("**🟢 Top Put Strikes**")
                st.dataframe(
                    data_0dte['puts'][['strike', 'GEX', 'delta', 'open_interest', 'volume']].head(5),
                    width='stretch',
                    hide_index=True
                )
        
        tab_idx += 1
    
    # Weekly Levels Tab
    if data_weekly:
        with tabs[tab_idx]:
            st.subheader(f"Weekly Analysis - {exp_weekly.strftime('%Y-%m-%d')}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Delta Neutral", f"{data_weekly['dn_nq']:.2f}")
            col2.metric("Gamma Flip", f"{data_weekly['g_flip_nq']:.2f}")
            col3.metric("Net Delta", f"{data_weekly['net_delta']:,.0f}", "🟢 Bull" if data_weekly['net_delta'] > 0 else "🔴 Bear")
            col4.metric("Expected Move", f"±{data_weekly['nq_em_full']:.0f}")
            
            results_df = pd.DataFrame(data_weekly['results'], columns=['Level', 'Price', 'Width', 'Icon'])
            results_df['Price'] = results_df['Price'].round(2)
            st.dataframe(
                results_df[['Icon', 'Level', 'Price', 'Width']].style.format({
                    'Price': '{:.2f}',
                    'Width': '{:.1f}'
                }),
                width='stretch',
                height=500,
                hide_index=True
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🔴 Top Call Strikes**")
                st.dataframe(
                    data_weekly['calls'][['strike', 'GEX', 'delta', 'open_interest', 'volume']].head(5),
                    width='stretch',
                    hide_index=True
                )
            with col2:
                st.markdown("**🟢 Top Put Strikes**")
                st.dataframe(
                    data_weekly['puts'][['strike', 'GEX', 'delta', 'open_interest', 'volume']].head(5),
                    width='stretch',
                    hide_index=True
                )
        
        tab_idx += 1
    
    # Monthly Levels Tab
    if data_monthly:
        with tabs[tab_idx]:
            st.subheader(f"Monthly Analysis - {exp_monthly.strftime('%Y-%m-%d')}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Delta Neutral", f"{data_monthly['dn_nq']:.2f}")
            col2.metric("Gamma Flip", f"{data_monthly['g_flip_nq']:.2f}")
            col3.metric("Net Delta", f"{data_monthly['net_delta']:,.0f}", "🟢 Bull" if data_monthly['net_delta'] > 0 else "🔴 Bear")
            col4.metric("Expected Move", f"±{data_monthly['nq_em_full']:.0f}")
            
            results_df = pd.DataFrame(data_monthly['results'], columns=['Level', 'Price', 'Width', 'Icon'])
            results_df['Price'] = results_df['Price'].round(2)
            st.dataframe(
                results_df[['Icon', 'Level', 'Price', 'Width']].style.format({
                    'Price': '{:.2f}',
                    'Width': '{:.1f}'
                }),
                width='stretch',
                height=500,
                hide_index=True
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🔴 Top Call Strikes**")
                st.dataframe(
                    data_monthly['calls'][['strike', 'GEX', 'delta', 'open_interest', 'volume']].head(5),
                    width='stretch',
                    hide_index=True
                )
            with col2:
                st.markdown("**🟢 Top Put Strikes**")
                st.dataframe(
                    data_monthly['puts'][['strike', 'GEX', 'delta', 'open_interest', 'volume']].head(5),
                    width='stretch',
                    hide_index=True
                )
        
        tab_idx += 1
    
    # GEX Charts Tab
    with tabs[tab_idx]:
        st.subheader("📈 GEX by Strike - All Timeframes")
        
        if data_0dte:
            st.markdown("**0DTE**")
            gex_by_strike = data_0dte['df'].groupby('strike')['GEX'].sum().reset_index()
            fig = go.Figure()
            pos_gex = gex_by_strike[gex_by_strike['GEX'] > 0]
            neg_gex = gex_by_strike[gex_by_strike['GEX'] < 0]
            fig.add_trace(go.Bar(x=pos_gex['strike'], y=pos_gex['GEX'], name='Calls', marker_color='#FF4444'))
            fig.add_trace(go.Bar(x=neg_gex['strike'], y=neg_gex['GEX'], name='Puts', marker_color='#44FF44'))
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#00D9FF", annotation_text="Current")
            fig.update_layout(template="plotly_dark", plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', height=400, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        
        if data_weekly:
            st.markdown("**Weekly**")
            gex_by_strike = data_weekly['df'].groupby('strike')['GEX'].sum().reset_index()
            fig = go.Figure()
            pos_gex = gex_by_strike[gex_by_strike['GEX'] > 0]
            neg_gex = gex_by_strike[gex_by_strike['GEX'] < 0]
            fig.add_trace(go.Bar(x=pos_gex['strike'], y=pos_gex['GEX'], name='Calls', marker_color='#FF4444'))
            fig.add_trace(go.Bar(x=neg_gex['strike'], y=neg_gex['GEX'], name='Puts', marker_color='#44FF44'))
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#00D9FF", annotation_text="Current")
            fig.update_layout(template="plotly_dark", plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', height=400, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        
        if data_monthly:
            st.markdown("**Monthly**")
            gex_by_strike = data_monthly['df'].groupby('strike')['GEX'].sum().reset_index()
            fig = go.Figure()
            pos_gex = gex_by_strike[gex_by_strike['GEX'] > 0]
            neg_gex = gex_by_strike[gex_by_strike['GEX'] < 0]
            fig.add_trace(go.Bar(x=pos_gex['strike'], y=pos_gex['GEX'], name='Calls', marker_color='#FF4444'))
            fig.add_trace(go.Bar(x=neg_gex['strike'], y=neg_gex['GEX'], name='Puts', marker_color='#44FF44'))
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#00D9FF", annotation_text="Current")
            fig.update_layout(template="plotly_dark", plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', height=400, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
    
    tab_idx += 1
    
    # Delta Charts Tab
    with tabs[tab_idx]:
        st.subheader("⚖️ Cumulative Delta - All Timeframes")
        
        if data_0dte:
            st.markdown("**0DTE**")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data_0dte['strike_delta']['strike'],
                y=data_0dte['strike_delta']['cumulative_delta'],
                mode='lines',
                name='Cumulative Delta',
                line=dict(color='#00D9FF', width=3),
                fill='tozeroy'
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="white")
            fig.add_vline(x=data_0dte['dn_strike'], line_dash="dot", line_color="#FFD700", annotation_text="DN")
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#FF4444", annotation_text="Current")
            fig.update_layout(template="plotly_dark", plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        if data_weekly:
            st.markdown("**Weekly**")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data_weekly['strike_delta']['strike'],
                y=data_weekly['strike_delta']['cumulative_delta'],
                mode='lines',
                name='Cumulative Delta',
                line=dict(color='#00D9FF', width=3),
                fill='tozeroy'
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="white")
            fig.add_vline(x=data_weekly['dn_strike'], line_dash="dot", line_color="#FFD700", annotation_text="DN")
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#FF4444", annotation_text="Current")
            fig.update_layout(template="plotly_dark", plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        if data_monthly:
            st.markdown("**Monthly**")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data_monthly['strike_delta']['strike'],
                y=data_monthly['strike_delta']['cumulative_delta'],
                mode='lines',
                name='Cumulative Delta',
                line=dict(color='#00D9FF', width=3),
                fill='tozeroy'
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="white")
            fig.add_vline(x=data_monthly['dn_strike'], line_dash="dot", line_color="#FFD700", annotation_text="DN")
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#FF4444", annotation_text="Current")
            fig.update_layout(template="plotly_dark", plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', height=400)
            st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')} | CBOE • {nq_source}")

if st.sidebar.button("🔄 Refresh", width='stretch'):
    st.cache_data.clear()
    st.rerun()
