import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import finnhub
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="NQ Precision Map",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
# KOYFIN-INSPIRED THEME
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Global Theme */
    .main {
        background-color: #0a0e1a;
        color: #e8eaed;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Card Styling - Koyfin inspired */
    .koyfin-card {
        background: linear-gradient(135deg, #141824 0%, #1a1f2e 100%);
        border: 1px solid #2a3142;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    
    .koyfin-card-header {
        font-size: 13px;
        font-weight: 600;
        color: #8b92a8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 12px;
        border-bottom: 1px solid #2a3142;
        padding-bottom: 8px;
    }
    
    /* Metrics */
    .stMetric {
        background: #141824;
        padding: 12px;
        border-radius: 6px;
        border: 1px solid #2a3142;
    }
    
    .stMetric label {
        color: #8b92a8;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #e8eaed;
        font-weight: 600;
    }
    
    /* Headers */
    h1 {
        color: #e8eaed;
        font-weight: 700;
        font-size: 28px;
        margin-bottom: 24px;
    }
    
    h2 {
        color: #e8eaed;
        font-size: 16px;
        font-weight: 600;
        margin-top: 24px;
        margin-bottom: 16px;
    }
    
    h3 {
        color: #8b92a8;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 12px;
    }
    
    /* Tables */
    .dataframe {
        background: #141824 !important;
        border: 1px solid #2a3142 !important;
        font-size: 12px !important;
    }
    
    .dataframe th {
        background: #1a1f2e !important;
        color: #8b92a8 !important;
        font-weight: 600 !important;
        font-size: 11px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.3px !important;
        padding: 8px !important;
    }
    
    .dataframe td {
        background: #141824 !important;
        color: #e8eaed !important;
        padding: 8px !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #141824;
        padding: 8px;
        border-radius: 6px;
        border: 1px solid #2a3142;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #8b92a8;
        font-weight: 600;
        font-size: 12px;
        padding: 8px 16px;
        border-radius: 4px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #2563eb;
        color: #fff;
    }
    
    /* Quick Glance Dashboard */
    .quick-glance {
        background: linear-gradient(135deg, #1a1f2e 0%, #141824 100%);
        padding: 24px;
        border-radius: 8px;
        border: 1px solid #2a3142;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
    
    .quick-glance-title {
        color: #2563eb;
        font-size: 14px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 16px;
    }
    
    .quick-glance-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 20px;
    }
    
    .quick-glance-item {
        background: #0a0e1a;
        padding: 16px;
        border-radius: 6px;
        border: 1px solid #2a3142;
    }
    
    .quick-glance-label {
        color: #8b92a8;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    
    .quick-glance-value {
        color: #e8eaed;
        font-size: 28px;
        font-weight: 700;
        margin-bottom: 4px;
    }
    
    .quick-glance-subtext {
        color: #6b7280;
        font-size: 11px;
    }
    
    /* Sentiment Meter */
    .sentiment-meter {
        height: 24px;
        background: linear-gradient(90deg, #dc2626 0%, #facc15 50%, #16a34a 100%);
        border-radius: 12px;
        position: relative;
        margin: 12px 0;
    }
    
    .sentiment-marker {
        position: absolute;
        width: 3px;
        height: 32px;
        background: #fff;
        top: -4px;
        border-radius: 2px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.5);
    }
    
    .sentiment-labels {
        display: flex;
        justify-content: space-between;
        font-size: 10px;
        color: #6b7280;
        margin-top: 4px;
    }
    
    /* Price positive/negative */
    .price-up {
        color: #16a34a !important;
    }
    
    .price-down {
        color: #dc2626 !important;
    }
    
    /* Compact table styling */
    .compact-table {
        font-size: 11px;
        line-height: 1.4;
    }
    
    .compact-table th {
        padding: 6px 8px !important;
    }
    
    .compact-table td {
        padding: 6px 8px !important;
    }
    
    /* Status badges */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    
    .badge-bullish {
        background: #16a34a;
        color: #fff;
    }
    
    .badge-bearish {
        background: #dc2626;
        color: #fff;
    }
    
    .badge-neutral {
        background: #6b7280;
        color: #fff;
    }
    
    /* Auto-refresh indicator */
    .refresh-indicator {
        position: fixed;
        top: 16px;
        right: 16px;
        background: #141824;
        padding: 8px 12px;
        border-radius: 6px;
        border: 1px solid #2a3142;
        font-size: 11px;
        color: #8b92a8;
        z-index: 999;
    }
    
    /* Heatmap cell styling */
    .heatmap-cell {
        padding: 8px;
        border-radius: 4px;
        text-align: center;
        font-weight: 600;
        font-size: 11px;
    }
    
    .heatmap-positive {
        background: rgba(22, 163, 74, 0.2);
        color: #16a34a;
    }
    
    .heatmap-negative {
        background: rgba(220, 38, 38, 0.2);
        color: #dc2626;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="refresh-indicator">🔄 Auto-refresh: ON</div>', unsafe_allow_html=True)

st.title("📊 NQ PRECISION MAP")
st.markdown("**Multi-Timeframe GEX & Delta Analysis** • Real-time Options Flow")

FINNHUB_KEY = "csie7q9r01qt46e7sjm0csie7q9r01qt46e7sjmg"

# ─────────────────────────────────────────────
# AUTO-REFRESH LOGIC
# ─────────────────────────────────────────────
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

refresh_interval = 60
time_since_refresh = time.time() - st.session_state.last_refresh

if time_since_refresh >= refresh_interval:
    st.session_state.last_refresh = time.time()
    st.rerun()

# ─────────────────────────────────────────────
# DATA FUNCTIONS (SAME AS BEFORE)
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
def get_nq_intraday_data():
    """Get last 50 candles for chart"""
    try:
        nq = yf.Ticker("NQ=F")
        data = nq.history(period="1d", interval="5m")
        if not data.empty:
            return data.tail(50)
    except:
        pass
    return None

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
def get_market_overview_yahoo():
    """Get market data from Yahoo Finance"""
    data = {}
    
    symbols = {
        'vix': '^VIX',
        'es': 'ES=F',
        'ym': 'YM=F',
        'rty': 'RTY=F',
        '10y': '^TNX',
        'dxy': 'DX=F'
    }
    
    for key, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev_close = hist['Open'].iloc[0]
                change = current - prev_close
                change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
                
                data[key] = {
                    'price': float(current),
                    'change': float(change),
                    'change_pct': float(change_pct)
                }
            else:
                data[key] = {'price': 0, 'change': 0, 'change_pct': 0}
        except:
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

def calculate_sentiment_score(data_0dte, nq_now, vix_level, fg_score):
    """Calculate 0-100 sentiment score"""
    score = 50
    
    if data_0dte:
        dn_distance = nq_now - data_0dte['dn_nq']
        gf_distance = nq_now - data_0dte['g_flip_nq']
        
        if abs(dn_distance) > 200:
            if dn_distance > 0:
                score -= 15
            else:
                score += 15
        
        if gf_distance > 0:
            score -= 10
        else:
            score += 10
        
        if data_0dte['net_delta'] > 0:
            score += 5
        else:
            score -= 5
    
    if vix_level > 20:
        score -= 10
    elif vix_level < 15:
        score += 5
    
    if fg_score < 30:
        score += 10
    elif fg_score > 70:
        score -= 10
    
    return max(0, min(100, score))

def process_expiration(df_raw, target_exp, qqq_price, ratio, nq_now):
    """Process single expiration and return all analysis"""
    df = df_raw[df_raw['expiration'] == target_exp].copy()
    df = df[df['open_interest'] > 0].copy()
    df = df[df['iv'] > 0].copy()
    df = df[(df['strike'] > qqq_price * 0.98) & (df['strike'] < qqq_price * 1.02)].copy()
    
    if len(df) == 0:
        return None
    
    dn_strike, strike_delta, df = calculate_delta_neutral(df, qqq_price)
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
    puts = df[df['type'] == 'put'].sort_values('GEX', ascending=True)
    
    p_wall_strike = calls.iloc[0]['strike'] if len(calls) > 0 else qqq_price
    p_floor_strike = puts.iloc[0]['strike'] if len(puts) > 0 else qqq_price
    
    if p_floor_strike == p_wall_strike and len(puts) > 1:
        p_floor_strike = puts.iloc[1]['strike']
    
    s_wall_strike = p_wall_strike
    for i in range(1, len(calls)):
        candidate = calls.iloc[i]['strike']
        if candidate > p_wall_strike:
            s_wall_strike = candidate
            break
    
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
        ("Target Resistance", (p_wall_strike * ratio) + 35, 3.0, "🎯"),
        ("Primary Wall", p_wall_strike * ratio, 5.0, "🔴"),
        ("Primary Floor", p_floor_strike * ratio, 5.0, "🟢"),
        ("Target Support", (p_floor_strike * ratio) - 35, 3.0, "🎯"),
        ("Secondary Wall", s_wall_strike * ratio, 3.0, "🟠"),
        ("Secondary Floor", s_floor_strike * ratio, 3.0, "🟡"),
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
# LOAD DATA
# ─────────────────────────────────────────────
with st.spinner("Loading market data..."):
    qqq_price = get_qqq_price(FINNHUB_KEY)
    if not qqq_price:
        st.error("Could not fetch QQQ price")
        st.stop()

    nq_now, nq_source = get_nq_price_auto(FINNHUB_KEY)
    if not nq_now:
        nq_now = 24760.0
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
    
    market_data = get_market_overview_yahoo()
    vix_level = market_data.get('vix', {}).get('price', 15)
    fg = get_fear_greed_index()
    sentiment_score = calculate_sentiment_score(data_0dte, nq_now, vix_level, fg['score'])

# ═══════════════════════════════════════════════════
# QUICK GLANCE - KOYFIN STYLE
# ═══════════════════════════════════════════════════
if data_0dte:
    dn_distance = nq_now - data_0dte['dn_nq']
    gf_distance = nq_now - data_0dte['g_flip_nq']
    above_gf = gf_distance > 0
    
    regime = "NEGATIVE GAMMA" if above_gf else "POSITIVE GAMMA"
    regime_emoji = "🔴" if above_gf else "🟢"
    
    if abs(dn_distance) > 200:
        bias = "SHORT" if dn_distance > 0 else "LONG"
        bias_emoji = "⬇️" if dn_distance > 0 else "⬆️"
    else:
        bias = "NEUTRAL"
        bias_emoji = "⚖️"
    
    # NQ change calculation
    try:
        nq_ticker = yf.Ticker("NQ=F")
        nq_hist = nq_ticker.history(period="1d")
        if not nq_hist.empty:
            nq_prev_close = nq_hist['Open'].iloc[0]
            nq_change = nq_now - nq_prev_close
            nq_change_pct = (nq_change / nq_prev_close) * 100 if nq_prev_close != 0 else 0
        else:
            nq_change = 0
            nq_change_pct = 0
    except:
        nq_change = 0
        nq_change_pct = 0
    
    change_color = "#16a34a" if nq_change >= 0 else "#dc2626"
    change_sign = "+" if nq_change >= 0 else ""
    
    st.markdown(f"""
    <div class="quick-glance">
        <div class="quick-glance-title">⚡ MARKET SNAPSHOT</div>
        <div class="quick-glance-grid">
            <div class="quick-glance-item">
                <div class="quick-glance-label">NQ FUTURES</div>
                <div class="quick-glance-value">{nq_now:,.2f}</div>
                <div class="quick-glance-subtext" style="color: {change_color};">{change_sign}{nq_change:.2f} ({change_sign}{nq_change_pct:.2f}%)</div>
            </div>
            <div class="quick-glance-item">
                <div class="quick-glance-label">GAMMA REGIME</div>
                <div class="quick-glance-value" style="font-size: 20px;">{regime_emoji} {regime}</div>
                <div class="quick-glance-subtext">{'Volatile/Unstable' if above_gf else 'Stable/Range-Bound'}</div>
            </div>
            <div class="quick-glance-item">
                <div class="quick-glance-label">TRADING BIAS</div>
                <div class="quick-glance-value" style="font-size: 20px;">{bias_emoji} {bias}</div>
                <div class="quick-glance-subtext">{abs(dn_distance):.0f}pts from Delta Neutral</div>
            </div>
            <div class="quick-glance-item">
                <div class="quick-glance-label">KEY LEVEL</div>
                <div class="quick-glance-value" style="font-size: 22px;">{data_0dte['dn_nq']:.2f}</div>
                <div class="quick-glance-subtext">Delta Neutral</div>
            </div>
        </div>
        
        <div style="margin-top: 20px;">
            <div class="quick-glance-label">MARKET SENTIMENT</div>
            <div class="sentiment-meter">
                <div class="sentiment-marker" style="left: {sentiment_score}%;"></div>
            </div>
            <div class="sentiment-labels">
                <span>BEARISH</span>
                <span>NEUTRAL</span>
                <span>BULLISH</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ═══════════════════════════════════════════════════
# KOYFIN-STYLE GRID LAYOUT
# ═══════════════════════════════════════════════════

col_left, col_middle, col_right = st.columns([2, 3, 2])

# LEFT COLUMN - Key Levels & Market Data
with col_left:
    # Key Levels Card
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">📊 Key Levels (0DTE)</div>', unsafe_allow_html=True)
    
    if data_0dte:
        levels_data = {
            'Level': ['Delta Neutral', 'Gamma Flip', 'Primary Wall', 'Primary Floor'],
            'Price': [
                f"{data_0dte['dn_nq']:.2f}",
                f"{data_0dte['g_flip_nq']:.2f}",
                f"{data_0dte['p_wall']:.2f}",
                f"{data_0dte['p_floor']:.2f}"
            ],
            'Distance': [
                f"{abs(nq_now - data_0dte['dn_nq']):.0f}",
                f"{abs(nq_now - data_0dte['g_flip_nq']):.0f}",
                f"{abs(nq_now - data_0dte['p_wall']):.0f}",
                f"{abs(nq_now - data_0dte['p_floor']):.0f}"
            ]
        }
        
        levels_df = pd.DataFrame(levels_data)
        st.dataframe(levels_df, hide_index=True, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Market Indicators Card
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">📈 Market Indicators</div>', unsafe_allow_html=True)
    
    if market_data:
        indicators_data = []
        
        for key, label in [('vix', 'VIX'), ('10y', '10Y Treasury'), ('dxy', 'Dollar Index')]:
            if key in market_data and market_data[key]['price']:
                price = market_data[key]['price']
                chg = market_data[key].get('change_pct', 0)
                indicators_data.append({
                    'Indicator': label,
                    'Price': f"{price:.2f}{'%' if key == '10y' else ''}",
                    'Change %': f"{chg:+.2f}%"
                })
        
        if indicators_data:
            indicators_df = pd.DataFrame(indicators_data)
            st.dataframe(indicators_df, hide_index=True, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Top Movers
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">📊 Top Movers</div>', unsafe_allow_html=True)
    
    movers = get_top_movers(FINNHUB_KEY)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Gainers**")
        if movers['gainers']:
            for mover in movers['gainers'][:3]:
                st.markdown(f"<span class='badge badge-bullish'>{mover['symbol']}</span> +{mover['change_pct']:.1f}%", unsafe_allow_html=True)
    
    with col2:
        st.markdown("**Losers**")
        if movers['losers']:
            for mover in movers['losers'][:3]:
                st.markdown(f"<span class='badge badge-bearish'>{mover['symbol']}</span> {mover['change_pct']:.1f}%", unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# MIDDLE COLUMN - Chart & Daily Bread
with col_middle:
    # Chart
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">📈 NQ Price Action (5min)</div>', unsafe_allow_html=True)
    
    if data_0dte:
        nq_data = get_nq_intraday_data()
        
        if nq_data is not None and not nq_data.empty:
            fig = go.Figure()
            
            fig.add_trace(go.Candlestick(
                x=nq_data.index,
                open=nq_data['Open'],
                high=nq_data['High'],
                low=nq_data['Low'],
                close=nq_data['Close'],
                name='NQ',
                increasing_line_color='#16a34a',
                decreasing_line_color='#dc2626'
            ))
            
            # Add levels
            fig.add_hline(y=data_0dte['dn_nq'], line_dash="dot", line_color="#facc15", annotation_text="DN", annotation_position="right")
            fig.add_hline(y=data_0dte['g_flip_nq'], line_dash="dash", line_color="#a855f7", annotation_text="GF", annotation_position="right")
            fig.add_hline(y=data_0dte['p_wall'], line_color="#dc2626", annotation_text="Wall", annotation_position="right")
            fig.add_hline(y=data_0dte['p_floor'], line_color="#16a34a", annotation_text="Floor", annotation_position="right")
            
            # Gamma zones
            if data_0dte['g_flip_nq'] < nq_data['High'].max():
                fig.add_hrect(y0=data_0dte['g_flip_nq'], y1=nq_data['High'].max(), fillcolor="red", opacity=0.05)
            
            if data_0dte['g_flip_nq'] > nq_data['Low'].min():
                fig.add_hrect(y0=nq_data['Low'].min(), y1=data_0dte['g_flip_nq'], fillcolor="green", opacity=0.05)
            
            fig.update_layout(
                template="plotly_dark",
                height=400,
                xaxis_title="",
                yaxis_title="Price",
                showlegend=False,
                hovermode='x unified',
                paper_bgcolor='#0a0e1a',
                plot_bgcolor='#0a0e1a'
            )
            
            fig.update_xaxes(rangeslider_visible=False)
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chart data unavailable - check back during market hours")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Daily Bread Summary
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">🍞 Daily Bread Summary</div>', unsafe_allow_html=True)
    
    if data_0dte:
        if above_dn and above_gf and abs(dn_distance) > 200:
            summary = f"**OVEREXTENDED UPSIDE:** NQ trading {dn_distance:.0f}pts above Delta Neutral in negative gamma. High reversion risk to {data_0dte['dn_nq']:.2f}. Fade rallies into {data_0dte['p_wall']:.2f} wall."
            st.warning(summary)
        elif not above_dn and not above_gf:
            summary = f"**RANGE-BOUND:** Positive gamma regime. Price stable between {data_0dte['p_floor']:.2f} floor and {data_0dte['p_wall']:.2f} wall. Mean reversion trades favored."
            st.success(summary)
        else:
            summary = f"**BALANCED:** Price near Delta Neutral equilibrium. Watch {data_0dte['g_flip_nq']:.2f} Gamma Flip for regime shifts."
            st.info(summary)
    
    st.markdown('</div>', unsafe_allow_html=True)

# RIGHT COLUMN - News & Events
with col_right:
    # Economic Calendar
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">📅 Today\'s Events</div>', unsafe_allow_html=True)
    
    events = get_economic_calendar(FINNHUB_KEY)
    
    if events:
        high_impact = [e for e in events if e.get('impact') == 'high']
        
        if high_impact:
            for event in high_impact[:3]:
                time_str = event.get('time', '')[-8:-3] if event.get('time') else 'TBD'
                st.markdown(f"<span class='badge badge-bearish'>HIGH</span> {time_str} • {event.get('event', 'Unknown')}", unsafe_allow_html=True)
        else:
            st.info("No high-impact events today")
    else:
        st.info("Light calendar")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Market News
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">📰 Headlines</div>', unsafe_allow_html=True)
    
    news = get_market_news(FINNHUB_KEY)
    
    if news:
        for article in news[:4]:
            headline = article.get('headline', 'No title')
            source = article.get('source', 'Unknown')
            
            # Truncate headline
            if len(headline) > 60:
                headline = headline[:57] + "..."
            
            st.markdown(f"**{headline}**")
            st.caption(source)
            st.markdown("")
    else:
        st.info("No news available")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Fear & Greed
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">😱 Fear & Greed</div>', unsafe_allow_html=True)
    
    st.metric("Score", f"{fg['score']}/100", fg['rating'])
    
    if fg['score'] < 30:
        st.success("Extreme Fear - Contrarian Buy Signal")
    elif fg['score'] > 70:
        st.error("Extreme Greed - Contrarian Sell Signal")
    else:
        st.info(fg['rating'])
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} • Data: CBOE • {nq_source} • Auto-refresh: 60s")
