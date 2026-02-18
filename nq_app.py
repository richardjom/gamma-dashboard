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
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# THEME TOGGLE (STORED IN SESSION STATE)
# ─────────────────────────────────────────────
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

# Theme-specific colors
if st.session_state.theme == 'dark':
    BG_COLOR = "#0E1117"
    CARD_BG = "#1E1E1E"
    TEXT_COLOR = "#FFF"
    ACCENT_COLOR = "#00D9FF"
    BORDER_COLOR = "#333"
else:
    BG_COLOR = "#FFFFFF"
    CARD_BG = "#F0F2F6"
    TEXT_COLOR = "#000"
    ACCENT_COLOR = "#0066CC"
    BORDER_COLOR = "#DDD"

# Custom CSS with theme support
st.markdown(f"""
<style>
    .main {{
        background-color: {BG_COLOR};
    }}
    .stMetric {{
        background-color: {CARD_BG};
        padding: 15px;
        border-radius: 10px;
        border: 1px solid {BORDER_COLOR};
    }}
    .stMetric label {{
        color: #888;
        font-size: 14px;
    }}
    .stMetric [data-testid="stMetricValue"] {{
        font-size: 28px;
        color: {ACCENT_COLOR};
    }}
    h1 {{
        color: {ACCENT_COLOR};
        font-weight: 700;
    }}
    h2, h3 {{
        color: {TEXT_COLOR};
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 24px;
        background-color: {CARD_BG};
        padding: 10px;
        border-radius: 10px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent;
        color: #888;
        font-weight: 600;
        padding: 10px 20px;
        border-radius: 5px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {ACCENT_COLOR};
        color: #000;
    }}
    .quick-glance {{
        background: linear-gradient(135deg, {CARD_BG} 0%, {BORDER_COLOR} 100%);
        padding: 25px;
        border-radius: 15px;
        border: 2px solid {ACCENT_COLOR};
        margin-bottom: 20px;
    }}
    .sentiment-meter {{
        height: 30px;
        background: linear-gradient(90deg, #FF4444 0%, #FFAA00 50%, #44FF44 100%);
        border-radius: 15px;
        position: relative;
    }}
    .sentiment-marker {{
        position: absolute;
        width: 4px;
        height: 40px;
        background: #000;
        top: -5px;
        border-radius: 2px;
    }}
    .keyboard-hint {{
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: {CARD_BG};
        padding: 10px;
        border-radius: 8px;
        font-size: 12px;
        color: #888;
        border: 1px solid {BORDER_COLOR};
    }}
</style>
""", unsafe_allow_html=True)

# Keyboard shortcuts hint
st.markdown("""
<div class="keyboard-hint">
⌨️ Shortcuts: R=Refresh | 1-6=Tabs | T=Theme
</div>
""", unsafe_allow_html=True)

st.title("📊 NQ Precision Map")
st.markdown("**Multi-Timeframe GEX & Delta Analysis** • Powered by CBOE Data")

FINNHUB_KEY = "csie7q9r01qt46e7sjm0csie7q9r01qt46e7sjmg"

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.header("⚙️ Settings")

# Theme toggle button
if st.sidebar.button("🎨 Toggle Theme", on_click=toggle_theme):
    st.rerun()

manual_override = st.sidebar.checkbox("✏️ Manual NQ Override")

# Auto-refresh toggle
auto_refresh = st.sidebar.checkbox("🔄 Auto-Refresh (60s)", value=True)
if auto_refresh:
    refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 30, 300, 60)

# ─────────────────────────────────────────────
# AUTO-REFRESH COUNTDOWN
# ─────────────────────────────────────────────
if auto_refresh:
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    time_since_refresh = time.time() - st.session_state.last_refresh
    time_until_refresh = max(0, refresh_interval - int(time_since_refresh))
    
    if time_until_refresh == 0:
        st.session_state.last_refresh = time.time()
        st.rerun()
    
    st.sidebar.markdown(f"**Next refresh in:** {time_until_refresh}s")
    placeholder = st.sidebar.empty()
    placeholder.progress((refresh_interval - time_until_refresh) / refresh_interval)

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
    score = 50  # Start neutral
    
    if data_0dte:
        dn_distance = nq_now - data_0dte['dn_nq']
        gf_distance = nq_now - data_0dte['g_flip_nq']
        
        # Delta Neutral positioning (-20 to +20)
        if abs(dn_distance) > 200:
            if dn_distance > 0:
                score -= 15  # Overextended bearish
            else:
                score += 15  # Oversold bullish
        
        # Gamma regime (-15 to +15)
        if gf_distance > 0:
            score -= 10  # Negative gamma = bearish
        else:
            score += 10  # Positive gamma = bullish
        
        # Net Delta (-10 to +10)
        if data_0dte['net_delta'] > 0:
            score += 5  # Bullish positioning
        else:
            score -= 5  # Bearish positioning
    
    # VIX level (-10 to +10)
    if vix_level > 20:
        score -= 10  # High fear
    elif vix_level < 15:
        score += 5  # Low fear
    
    # Fear & Greed (-10 to +10)
    if fg_score < 30:
        score += 10  # Extreme fear = contrarian buy
    elif fg_score > 70:
        score -= 10  # Extreme greed = contrarian sell
    
    return max(0, min(100, score))

def process_expiration(df_raw, target_exp, qqq_price, ratio, nq_now):
    """Process single expiration and return all analysis - FIXED LEVEL LOGIC"""
    df = df_raw[df_raw['expiration'] == target_exp].copy()
    df = df[df['open_interest'] > 0].copy()
    df = df[df['iv'] > 0].copy()
    df = df[(df['strike'] > qqq_price * 0.98) & (df['strike'] < qqq_price * 1.02)].copy()
    
    if len(df) == 0:
        return None
    
    # Calculate Delta Neutral
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
    
    # FIXED LEVEL LOGIC - Ensures proper ordering
    calls = df[df['type'] == 'call'].sort_values('GEX', ascending=False)
    puts = df[df['type'] == 'put'].sort_values('GEX', ascending=True)
    
    # Primary Wall = highest call GEX ABOVE current price
    calls_above = calls[calls['strike'] > qqq_price]
    if len(calls_above) > 0:
        p_wall_strike = calls_above.iloc[0]['strike']
    else:
        p_wall_strike = calls.iloc[0]['strike'] if len(calls) > 0 else qqq_price * 1.01
    
    # Primary Floor = highest put GEX BELOW current price
    puts_below = puts[puts['strike'] < qqq_price]
    if len(puts_below) > 0:
        p_floor_strike = puts_below.iloc[0]['strike']
    else:
        p_floor_strike = puts.iloc[0]['strike'] if len(puts) > 0 else qqq_price * 0.99
    
    # CRITICAL: Ensure floor is ALWAYS below wall
    if p_floor_strike >= p_wall_strike:
        p_floor_strike = min(puts['strike']) if len(puts) > 0 else qqq_price * 0.99
        p_wall_strike = max(calls['strike']) if len(calls) > 0 else qqq_price * 1.01
    
    # Secondary Wall - must be ABOVE primary wall
    s_wall_strike = p_wall_strike
    for i in range(len(calls)):
        candidate = calls.iloc[i]['strike']
        if candidate > p_wall_strike and candidate != p_wall_strike:
            s_wall_strike = candidate
            break
    
    # Secondary Floor - must be BELOW primary floor
    s_floor_strike = p_floor_strike
    for i in range(len(puts)):
        candidate = puts.iloc[i]['strike']
        if candidate < p_floor_strike and candidate != p_floor_strike:
            s_floor_strike = candidate
            break
    
    # Final validation
    if s_floor_strike >= s_wall_strike:
        s_floor_strike = p_floor_strike * 0.995
        s_wall_strike = p_wall_strike * 1.005
    
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
        's_wall': s_wall_strike * ratio,
        's_floor': s_floor_strike * ratio,
        'calls': calls,
        'puts': puts,
        'strike_delta': strike_delta,
        'results': results,
        'straddle': straddle,
        'nq_em_full': nq_em_full,
        'atm_strike': atm_strike
    }
    
@st.cache_data(ttl=14400)
def generate_daily_bread(data_0dte, data_weekly, nq_now, market_data, fg, events, news):
    """Generate Bloomberg-style Daily Bread - Updates 2x daily (4hr cache)"""
    
    current_hour = datetime.now().hour
    is_morning = current_hour < 12
    
    report = {}
    report['timestamp'] = datetime.now().strftime('%A, %B %d, %Y • %I:%M %p EST')
    report['session'] = "MORNING BRIEF" if is_morning else "MARKET CLOSE SUMMARY"
    
    if not data_0dte:
        return report
    
    dn_distance = nq_now - data_0dte['dn_nq']
    gf_distance = nq_now - data_0dte['g_flip_nq']
    above_dn = dn_distance > 0
    above_gf = gf_distance > 0
    
    # EXECUTIVE SUMMARY
    if above_dn and above_gf and abs(dn_distance) > 200:
        tone = "BEARISH"
        summary = f"""**OVEREXTENDED UPSIDE - MEAN REVERSION LIKELY**

NQ futures are trading {dn_distance:.0f} points above the Delta Neutral level at {data_0dte['dn_nq']:.2f}, indicating significant overextension from dealer hedging levels. The market is operating in **negative gamma** territory above {data_0dte['g_flip_nq']:.2f}, creating unstable price action prone to whipsaws.

**Net dealer positioning:** {data_0dte['net_delta']:,.0f} delta ({'short' if data_0dte['net_delta'] < 0 else 'long'})

This configuration historically precedes mean reversion moves back toward Delta Neutral. Rallies into {data_0dte['p_wall']:.2f} primary resistance wall should face heavy selling pressure from systematic hedging flows."""
        
    elif not above_dn and not above_gf:
        tone = "RANGE-BOUND"
        summary = f"""**STABLE RANGE - POSITIVE GAMMA REGIME**

NQ is trading {abs(dn_distance):.0f} points below Delta Neutral at {data_0dte['dn_nq']:.2f} within **positive gamma** territory. This regime favors range-bound trading between {data_0dte['p_floor']:.2f} support floor and {data_0dte['p_wall']:.2f} resistance wall.

**Net dealer positioning:** {data_0dte['net_delta']:,.0f} delta ({'short' if data_0dte['net_delta'] < 0 else 'long'})

In positive gamma, dealers actively stabilize price action by buying dips and selling rallies. Breakout attempts are less likely to follow through as systematic flows work against momentum. Mean reversion trades are favored."""
        
    else:
        tone = "NEUTRAL"
        summary = f"""**BALANCED POSITIONING - WATCH FOR CATALYSTS**

NQ is trading near equilibrium around the {data_0dte['dn_nq']:.2f} Delta Neutral level with relatively balanced dealer positioning. Current gamma regime is **{'negative' if above_gf else 'positive'}**, suggesting **{'volatile' if above_gf else 'stable'}** price action ahead.

**Net dealer positioning:** {data_0dte['net_delta']:,.0f} delta ({'short' if data_0dte['net_delta'] < 0 else 'long'})

Watch for a decisive break of the {data_0dte['g_flip_nq']:.2f} Gamma Flip or {data_0dte['dn_nq']:.2f} Delta Neutral to establish directional bias. Key resistance at {data_0dte['p_wall']:.2f}, support at {data_0dte['p_floor']:.2f}."""
    
    report['tone'] = tone
    report['summary'] = summary
    
    # KEY LEVELS
    report['levels'] = f"""**CRITICAL LEVELS FOR TODAY:**

- **Delta Neutral:** {data_0dte['dn_nq']:.2f} — Primary gravitational pull
- **Gamma Flip:** {data_0dte['g_flip_nq']:.2f} — Regime change threshold
- **Primary Resistance:** {data_0dte['p_wall']:.2f} — Heaviest call wall
- **Primary Support:** {data_0dte['p_floor']:.2f} — Heaviest put floor
- **Expected Move:** ±{data_0dte['nq_em_full']:.0f} points ({data_0dte['nq_em_full']/nq_now*100:.1f}%)"""
    
    # MARKET DRIVERS
    vix = market_data.get('vix', {}).get('price', 0)
    vix_change = market_data.get('vix', {}).get('change_pct', 0)
    
    drivers = f"""**MARKET DRIVERS:**

- **VIX:** {vix:.2f} ({vix_change:+.2f}%) — {'Elevated volatility' if vix > 18 else 'Low volatility regime'}
- **Fear & Greed:** {fg['score']}/100 ({fg['rating']}) — {'Contrarian buy signal' if fg['score'] < 30 else 'Contrarian sell signal' if fg['score'] > 70 else 'Neutral sentiment'}"""
    
    if events:
        high_impact = [e for e in events if e.get('impact') == 'high']
        if high_impact:
            drivers += "\n• **High-impact events:** " + ", ".join([e.get('event', 'Unknown')[:40] for e in high_impact[:2]])
    
    report['drivers'] = drivers
    
    # TRADING STRATEGY
    if above_dn and above_gf and abs(dn_distance) > 200:
        strategy = f"""**RECOMMENDED APPROACH:**

**Short Bias — Fade Strength**
- Entry: Rallies into {data_0dte['p_wall']:.2f} resistance
- Target: {data_0dte['dn_nq']:.2f} Delta Neutral
- Stop: Above {data_0dte['s_wall']:.2f} (secondary wall)

**Risk Management:** Negative gamma creates whipsaw potential. Use tight stops and scale positions.

**Conservative Alternative:** Wait for break below {data_0dte['g_flip_nq']:.2f} Gamma Flip before establishing short positions."""
        
    elif not above_dn and not above_gf:
        strategy = f"""**RECOMMENDED APPROACH:**

**Range Trading — Buy Dips, Sell Rallies**
- Buy Zone: {data_0dte['p_floor']:.2f} - {data_0dte['s_floor']:.2f}
- Sell Zone: {data_0dte['p_wall']:.2f} - {data_0dte['s_wall']:.2f}
- Neutral: {data_0dte['dn_nq']:.2f}

**Advantage:** Positive gamma regime supports mean reversion. Dealers will stabilize price action.

**Breakout Watch:** Sustained move outside {data_0dte['p_floor']:.2f}-{data_0dte['p_wall']:.2f} range requires re-evaluation."""
        
    else:
        strategy = f"""**RECOMMENDED APPROACH:**

**Wait for Confirmation — No Clear Edge**
- Watch {data_0dte['g_flip_nq']:.2f} Gamma Flip for regime shift
- Watch {data_0dte['dn_nq']:.2f} Delta Neutral for directional bias
- Resistance: {data_0dte['p_wall']:.2f} | Support: {data_0dte['p_floor']:.2f}

**Patience Required:** Let price action develop before committing capital."""
    
    report['strategy'] = strategy
    
    # TOMORROW'S WATCH LIST
    watch_items = []
    
    if abs(dn_distance) > 200:
        watch_items.append(f"• **Delta Neutral convergence:** Price {abs(dn_distance):.0f}pts extended — mean reversion likely")
    
    if above_gf:
        watch_items.append(f"• **Gamma Flip breakdown:** Break below {data_0dte['g_flip_nq']:.2f} signals regime shift to stability")
    
    if data_weekly:
        dn_spread = abs(data_0dte['dn_nq'] - data_weekly['dn_nq'])
        if dn_spread > 100:
            watch_items.append(f"• **Timeframe divergence:** {dn_spread:.0f}pt spread between 0DTE/Weekly DN suggests choppy action")
    
    watch_items.append("• **VIX expansion:** Spike above 18 signals vol regime change")
    watch_items.append("• **Options expiration:** 0DTE levels reset tomorrow — gamma exposure shifts")
    
    report['watch_list'] = "\n".join(watch_items)
    
    return report
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
    
    # Get market data for sentiment
    market_data = get_market_overview_yahoo()
    vix_level = market_data.get('vix', {}).get('price', 15)
    fg = get_fear_greed_index()
    
    # Calculate sentiment score
    sentiment_score = calculate_sentiment_score(data_0dte, nq_now, vix_level, fg['score'])

# ═══════════════════════════════════════════════════
# QUICK GLANCE DASHBOARD (NEW FEATURE #2)
# ═══════════════════════════════════════════════════
if data_0dte:
    dn_distance = nq_now - data_0dte['dn_nq']
    gf_distance = nq_now - data_0dte['g_flip_nq']
    above_gf = gf_distance > 0
    
    # Determine regime and bias
    if above_gf:
        regime = "🔴 NEGATIVE GAMMA"
        regime_desc = "Unstable / Whipsaw Risk"
    else:
        regime = "🟢 POSITIVE GAMMA"
        regime_desc = "Stable / Range-Bound"
    
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
    
    key_level_price = data_0dte['g_flip_nq'] if above_gf else data_0dte['dn_nq']
    key_level_name = "Gamma Flip" if above_gf else "Delta Neutral"
    
    st.markdown(f"""
    <div class="quick-glance">
        <h2 style="margin-top: 0;">🎯 QUICK GLANCE</h2>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 20px;">
            <div>
                <p style="color: #888; margin: 0; font-size: 14px;">CURRENT PRICE</p>
                <p style="font-size: 32px; margin: 5px 0; color: {ACCENT_COLOR}; font-weight: bold;">{nq_now:.2f}</p>
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
    </div>
    """, unsafe_allow_html=True)
    
    # Sentiment Score Meter (NEW FEATURE #11)
    st.markdown("### 📊 Market Sentiment Score")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Sentiment interpretation
        if sentiment_score < 30:
            sentiment_text = "BEARISH"
            sentiment_color = "#FF4444"
        elif sentiment_score < 45:
            sentiment_text = "CAUTIOUS BEARISH"
            sentiment_color = "#FFAA00"
        elif sentiment_score < 55:
            sentiment_text = "NEUTRAL"
            sentiment_color = "#FFFF00"
        elif sentiment_score < 70:
            sentiment_text = "CAUTIOUS BULLISH"
            sentiment_color = "#AAFF00"
        else:
            sentiment_text = "BULLISH"
            sentiment_color = "#44FF44"
        
        st.markdown(f"""
        <div style="position: relative;">
            <div class="sentiment-meter">
                <div class="sentiment-marker" style="left: {sentiment_score}%;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 12px; color: #888;">
                <span>0 (Bearish)</span>
                <span>50 (Neutral)</span>
                <span>100 (Bullish)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.metric("Score", f"{sentiment_score}/100", sentiment_text)

st.markdown("---")

# ═══════════════════════════════════════════════════
# INTERACTIVE CHART WITH LEVELS (NEW FEATURE #3)
# ═══════════════════════════════════════════════════
if data_0dte:
    st.subheader("📈 NQ Price Action with Key Levels")
    
    nq_data = get_nq_intraday_data()
    
    if nq_data is not None and not nq_data.empty:
        fig = go.Figure()
        
        # Candlestick chart
        fig.add_trace(go.Candlestick(
            x=nq_data.index,
            open=nq_data['Open'],
            high=nq_data['High'],
            low=nq_data['Low'],
            close=nq_data['Close'],
            name='NQ',
            increasing_line_color='#44FF44',
            decreasing_line_color='#FF4444'
        ))
        
        # Add key levels as horizontal lines
        levels_to_plot = [
            (data_0dte['dn_nq'], "Delta Neutral", "#FFD700", "dot"),
            (data_0dte['g_flip_nq'], "Gamma Flip", "#FF00FF", "dash"),
            (data_0dte['p_wall'], "Primary Wall", "#FF4444", "solid"),
            (data_0dte['p_floor'], "Primary Floor", "#44FF44", "solid"),
        ]
        
        for level_price, level_name, color, dash in levels_to_plot:
            fig.add_hline(
                y=level_price,
                line_dash=dash,
                line_color=color,
                annotation_text=f"{level_name}: {level_price:.2f}",
                annotation_position="right"
            )
        
        # Shade gamma regime zones
        if data_0dte['g_flip_nq'] < nq_data['High'].max():
            fig.add_hrect(
                y0=data_0dte['g_flip_nq'],
                y1=nq_data['High'].max(),
                fillcolor="red",
                opacity=0.1,
                annotation_text="Negative Gamma Zone",
                annotation_position="top right"
            )
        
        if data_0dte['g_flip_nq'] > nq_data['Low'].min():
            fig.add_hrect(
                y0=nq_data['Low'].min(),
                y1=data_0dte['g_flip_nq'],
                fillcolor="green",
                opacity=0.1,
                annotation_text="Positive Gamma Zone",
                annotation_position="bottom right"
            )
        
        fig.update_layout(
            template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
            height=500,
            xaxis_title="Time (5-min candles)",
            yaxis_title="NQ Price",
            showlegend=False,
            hovermode='x unified'
        )
        
        fig.update_xaxes(rangeslider_visible=False)
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📊 Intraday chart data unavailable - check back during market hours")

st.markdown("---")

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
tab_names.extend(["🍞 Daily Bread", "📈 GEX Charts", "⚖️ Delta Charts"])

if tab_names:
    tabs = st.tabs(tab_names)
    
    tab_idx = 0
    
    # Market Overview Tab
    with tabs[tab_idx]:
        st.subheader("📈 Market Overview")
        
        with st.spinner("Loading market data..."):
            
            if market_data:
                st.markdown("### Futures & Indices")
                col1, col2, col3, col4 = st.columns(4)
                
                if 'es' in market_data and market_data['es']['price']:
                    es = market_data['es']
                    col1.metric(
                        "S&P 500 (ES)",
                        f"{es['price']:.2f}",
                        f"{es.get('change', 0):+.2f} ({es.get('change_pct', 0):+.2f}%)"
                    )
                else:
                    col1.metric("S&P 500 (ES)", "N/A")
                
                # NQ - WITH PERCENTAGE
                try:
                    nq_ticker = yf.Ticker("NQ=F")
                    nq_hist = nq_ticker.history(period="1d")
                    if not nq_hist.empty:
                        nq_prev_close = nq_hist['Open'].iloc[0]
                        nq_change = nq_now - nq_prev_close
                        nq_change_pct = (nq_change / nq_prev_close) * 100 if nq_prev_close != 0 else 0
                        col2.metric(
                            "Nasdaq (NQ)",
                            f"{nq_now:.2f}",
                            f"{nq_change:+.2f} ({nq_change_pct:+.2f}%)"
                        )
                    else:
                        col2.metric("Nasdaq (NQ)", f"{nq_now:.2f}", nq_source)
                except:
                    col2.metric("Nasdaq (NQ)", f"{nq_now:.2f}", nq_source)
                
                if 'ym' in market_data and market_data['ym']['price']:
                    ym = market_data['ym']
                    col3.metric(
                        "Dow (YM)",
                        f"{ym['price']:.2f}",
                        f"{ym.get('change', 0):+.2f} ({ym.get('change_pct', 0):+.2f}%)"
                    )
                else:
                    col3.metric("Dow (YM)", "N/A")
                
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
                
                if 'vix' in market_data and market_data['vix']['price']:
                    vix = market_data['vix']
                    col1.metric(
                        "VIX (Volatility)",
                        f"{vix['price']:.2f}",
                        f"{vix.get('change', 0):+.2f} ({vix.get('change_pct', 0):+.2f}%)"
                    )
                else:
                    col1.metric("VIX (Volatility)", "N/A")
                
                if '10y' in market_data and market_data['10y']['price']:
                    tnx = market_data['10y']
                    col2.metric(
                        "10Y Treasury",
                        f"{tnx['price']:.2f}%",
                        f"{tnx.get('change', 0):+.2f}"
                    )
                else:
                    col2.metric("10Y Treasury", "N/A")
                
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
    
# Daily Bread Tab
    with tabs[tab_idx]:
        st.markdown("# 🍞 DAILY BREAD")
        st.markdown(f"**Your NQ Market Intelligence Report** • {datetime.now().strftime('%A, %B %d, %Y')}")
        
        if data_0dte:
            # Load data for Daily Bread
            events = get_economic_calendar(FINNHUB_KEY)
            news = get_market_news(FINNHUB_KEY)
            
            # Generate Daily Bread report
            daily_bread = generate_daily_bread(data_0dte, data_weekly, nq_now, market_data, fg, events, news)
            
            st.markdown(f"**{daily_bread['session']}**")
            st.caption(daily_bread['timestamp'])
            
            st.markdown("---")
            
            # Executive Summary
            if daily_bread['tone'] == "BEARISH":
                st.error(daily_bread['summary'])
            elif daily_bread['tone'] == "RANGE-BOUND":
                st.success(daily_bread['summary'])
            else:
                st.info(daily_bread['summary'])
            
            # Collapsible sections for detailed analysis
            with st.expander("📊 Key Levels", expanded=False):
                st.markdown(daily_bread['levels'])
            
            with st.expander("📈 Market Drivers", expanded=False):
                st.markdown(daily_bread['drivers'])
            
            with st.expander("💼 Trading Strategy", expanded=False):
                st.markdown(daily_bread['strategy'])
            
            with st.expander("🔮 Tomorrow's Watch List", expanded=False):
                st.markdown(daily_bread['watch_list'])
        
        else:
            st.info("No 0DTE data available for Daily Bread analysis")
        
        st.markdown("---")
        st.caption("⚠️ Daily Bread is generated from live options market data and should not be considered financial advice. Always manage risk appropriately.")
    
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
            fig.update_layout(
                template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
                plot_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                paper_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                height=400,
                showlegend=True
            )
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
            fig.update_layout(
                template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
                plot_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                paper_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                height=400,
                showlegend=True
            )
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
            fig.update_layout(
                template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
                plot_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                paper_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                height=400,
                showlegend=True
            )
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
            fig.add_vline(x=data_0dte['dn_strike'], line_dash="dot", line_color="#FFD700", annotation_text="Delta Neutral")
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#FF4444", annotation_text="Current")
            fig.update_layout(
                template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
                plot_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                paper_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                height=400
            )
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
            fig.add_vline(x=data_weekly['dn_strike'], line_dash="dot", line_color="#FFD700", annotation_text="Delta Neutral")
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#FF4444", annotation_text="Current")
            fig.update_layout(
                template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
                plot_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                paper_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                height=400
            )
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
            fig.add_vline(x=data_monthly['dn_strike'], line_dash="dot", line_color="#FFD700", annotation_text="Delta Neutral")
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#FF4444", annotation_text="Current")
            fig.update_layout(
                template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
                plot_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                paper_bgcolor='#0E1117' if st.session_state.theme == 'dark' else '#FFFFFF',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')} | CBOE • {nq_source}")

# Manual refresh button
if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
    st.session_state.last_refresh = time.time()
    st.cache_data.clear()
    st.rerun()
