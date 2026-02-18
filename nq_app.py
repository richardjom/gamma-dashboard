import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import finnhub
import yfinance as yf
import plotly.graph_objects as go
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
    .main {
        background-color: #0a0e1a;
        color: #e8eaed;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
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
    }
    
    .stMetric [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #e8eaed;
        font-weight: 600;
    }
    
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
    }
    
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
    
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .badge-bullish {
        background: #16a34a;
        color: #fff;
    }
    
    .badge-bearish {
        background: #dc2626;
        color: #fff;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 NQ PRECISION MAP")
st.markdown("**Multi-Timeframe GEX & Delta Analysis** • Real-time Options Flow")

FINNHUB_KEY = "csie7q9r01qt46e7sjm0csie7q9r01qt46e7sjmg"

# ─────────────────────────────────────────────
# AUTO-REFRESH
# ─────────────────────────────────────────────
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

refresh_interval = 60
time_since_refresh = time.time() - st.session_state.last_refresh

if time_since_refresh >= refresh_interval:
    st.session_state.last_refresh = time.time()
    st.rerun()

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
    
    df['GEX'] = df.apply(
        lambda x: x['open_interest'] * x['gamma'] * (qqq_price ** 2) * 0.01 *
        (1 if x['type'] == 'call' else -1),
        axis=1
    )
    
    # FIXED LEVEL LOGIC
    calls = df[df['type'] == 'call'].sort_values('GEX', ascending=False)
    puts = df[df['type'] == 'put'].sort_values('GEX', ascending=True)
    
    # Primary Wall = highest call GEX above current price
    calls_above = calls[calls['strike'] > qqq_price]
    if len(calls_above) > 0:
        p_wall_strike = calls_above.iloc[0]['strike']
    else:
        p_wall_strike = calls.iloc[0]['strike'] if len(calls) > 0 else qqq_price * 1.01
    
    # Primary Floor = highest put GEX below current price
    puts_below = puts[puts['strike'] < qqq_price]
    if len(puts_below) > 0:
        p_floor_strike = puts_below.iloc[0]['strike']
    else:
        p_floor_strike = puts.iloc[0]['strike'] if len(puts) > 0 else qqq_price * 0.99
    
    # Ensure floor is ALWAYS below wall
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
    
    # Ensure secondary levels don't cross
    if s_floor_strike >= s_wall_strike:
        s_floor_strike = p_floor_strike * 0.995
        s_wall_strike = p_wall_strike * 1.005
    
    g_flip_strike = df.groupby('strike')['GEX'].sum().abs().idxmin()
    
    # Create results for backward compatibility
    results = [
        ("Delta Neutral", dn_nq, 5.0, "⚖️"),
        ("Target Resistance", (p_wall_strike * ratio) + 35, 3.0, "🎯"),
        ("Primary Wall", p_wall_strike * ratio, 5.0, "🔴"),
        ("Primary Floor", p_floor_strike * ratio, 5.0, "🟢"),
        ("Target Support", (p_floor_strike * ratio) - 35, 3.0, "🎯"),
        ("Secondary Wall", s_wall_strike * ratio, 3.0, "🟠"),
        ("Secondary Floor", s_floor_strike * ratio, 3.0, "🟡"),
        ("Gamma Flip", g_flip_strike * ratio, 10.0, "⚡"),
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
        'nq_em_full': nq_em_full,
        'results': results
    }

@st.cache_data(ttl=14400)
def generate_daily_bread(data_0dte, data_weekly, nq_now, market_data, fg, events, news):
    """Generate Bloomberg-style Daily Bread report - updates 2x daily"""
    
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

NQ futures are trading {dn_distance:.0f} points above the Delta Neutral level at {data_0dte['dn_nq']:.2f}, indicating significant overextension. The market is operating in **negative gamma** territory above {data_0dte['g_flip_nq']:.2f}, creating unstable price action.

**Net dealer positioning:** {data_0dte['net_delta']:,.0f} delta ({'short' if data_0dte['net_delta'] < 0 else 'long'})

This configuration historically precedes mean reversion moves. Rallies into {data_0dte['p_wall']:.2f} should face heavy selling pressure."""
        
    elif not above_dn and not above_gf:
        tone = "RANGE-BOUND"
        summary = f"""**STABLE RANGE - POSITIVE GAMMA REGIME**

NQ is trading {abs(dn_distance):.0f} points below Delta Neutral at {data_0dte['dn_nq']:.2f} within **positive gamma** territory. This regime favors range-bound trading between {data_0dte['p_floor']:.2f} support and {data_0dte['p_wall']:.2f} resistance.

**Net dealer positioning:** {data_0dte['net_delta']:,.0f} delta ({'short' if data_0dte['net_delta'] < 0 else 'long'})

Dealers actively stabilize price by buying dips and selling rallies. Mean reversion trades are favored."""
        
    else:
        tone = "NEUTRAL"
        summary = f"""**BALANCED POSITIONING - WATCH FOR CATALYSTS**

NQ is trading near equilibrium around {data_0dte['dn_nq']:.2f} Delta Neutral with relatively balanced positioning. Current gamma regime is **{'negative' if above_gf else 'positive'}**, suggesting **{'volatile' if above_gf else 'stable'}** price action.

**Net dealer positioning:** {data_0dte['net_delta']:,.0f} delta ({'short' if data_0dte['net_delta'] < 0 else 'long'})

Watch for breaks of {data_0dte['g_flip_nq']:.2f} Gamma Flip or {data_0dte['dn_nq']:.2f} Delta Neutral for directional bias."""
    
    report['tone'] = tone
    report['summary'] = summary
    
    # KEY LEVELS
    report['levels'] = f"""**CRITICAL LEVELS:**

• **Delta Neutral:** {data_0dte['dn_nq']:.2f} — Primary gravitational pull
• **Gamma Flip:** {data_0dte['g_flip_nq']:.2f} — Regime change threshold
• **Primary Resistance:** {data_0dte['p_wall']:.2f} — Heaviest call wall
• **Primary Support:** {data_0dte['p_floor']:.2f} — Heaviest put floor
• **Expected Move:** ±{data_0dte['nq_em_full']:.0f} points"""
    
    # MARKET DRIVERS
    vix = market_data.get('vix', {}).get('price', 0)
    vix_change = market_data.get('vix', {}).get('change_pct', 0)
    
    drivers = f"""**MARKET DRIVERS:**

• **VIX:** {vix:.2f} ({vix_change:+.2f}%) — {'Elevated volatility' if vix > 18 else 'Low vol regime'}
• **Fear & Greed:** {fg['score']}/100 ({fg['rating']})"""
    
    if events:
        high_impact = [e for e in events if e.get('impact') == 'high']
        if high_impact:
            drivers += "\n• **High-impact events:** " + ", ".join([e.get('event', 'Unknown')[:40] for e in high_impact[:2]])
    
    report['drivers'] = drivers
    
    # TRADING STRATEGY
    if above_dn and above_gf and abs(dn_distance) > 200:
        strategy = f"""**SHORT BIAS — Fade Strength**

**Entry:** Rallies into {data_0dte['p_wall']:.2f} resistance
**Target:** {data_0dte['dn_nq']:.2f} Delta Neutral
**Stop:** Above {data_0dte['s_wall']:.2f}

**Risk:** Negative gamma creates whipsaw potential. Use tight stops.

**Conservative:** Wait for break below {data_0dte['g_flip_nq']:.2f} Gamma Flip."""
        
    elif not above_dn and not above_gf:
        strategy = f"""**RANGE TRADING — Buy Dips, Sell Rallies**

**Buy Zone:** {data_0dte['p_floor']:.2f} - {data_0dte['s_floor']:.2f}
**Sell Zone:** {data_0dte['p_wall']:.2f} - {data_0dte['s_wall']:.2f}

**Edge:** Positive gamma supports mean reversion.

**Breakout Watch:** Sustained move outside range requires re-evaluation."""
        
    else:
        strategy = f"""**WAIT FOR CONFIRMATION**

Watch {data_0dte['g_flip_nq']:.2f} Gamma Flip for regime shift
Watch {data_0dte['dn_nq']:.2f} Delta Neutral for bias

**Patience required** — let price action develop."""
    
    report['strategy'] = strategy
    
    # WATCH LIST
    watch_items = []
    
    if abs(dn_distance) > 200:
        watch_items.append(f"• **Delta Neutral convergence:** Price {abs(dn_distance):.0f}pts extended")
    
    if above_gf:
        watch_items.append(f"• **Gamma Flip:** Break below {data_0dte['g_flip_nq']:.2f} signals regime shift")
    
    if data_weekly:
        dn_spread = abs(data_0dte['dn_nq'] - data_weekly['dn_nq'])
        if dn_spread > 100:
            watch_items.append(f"• **Timeframe divergence:** {dn_spread:.0f}pt DN spread")
    
    watch_items.append("• **VIX expansion:** Spike above 18 signals vol regime change")
    watch_items.append("• **0DTE expiration:** Levels reset tomorrow")
    
    report['watch_list'] = "\n".join(watch_items)
    
    return report

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
with st.spinner("Loading..."):
    qqq_price = get_qqq_price(FINNHUB_KEY)
    if not qqq_price:
        st.error("Could not fetch QQQ price")
        st.stop()

    nq_now, nq_source = get_nq_price_auto(FINNHUB_KEY)
    if not nq_now:
        nq_now = 24760.0

    ratio = nq_now / qqq_price

    df_raw, cboe_price = get_cboe_options("QQQ")
    if df_raw is None:
        st.error("Failed to fetch options")
        st.stop()

    exp_0dte, exp_weekly, exp_monthly = get_expirations_by_type(df_raw)
    
    data_0dte = process_expiration(df_raw, exp_0dte, qqq_price, ratio, nq_now) if exp_0dte else None
    data_weekly = process_expiration(df_raw, exp_weekly, qqq_price, ratio, nq_now) if exp_weekly and exp_weekly != exp_0dte else None
    data_monthly = process_expiration(df_raw, exp_monthly, qqq_price, ratio, nq_now) if exp_monthly and exp_monthly not in [exp_0dte, exp_weekly] else None
    
    market_data = get_market_overview_yahoo()
    vix_level = market_data.get('vix', {}).get('price', 15)
    fg = get_fear_greed_index()
    sentiment_score = calculate_sentiment_score(data_0dte, nq_now, vix_level, fg['score'])
    
    events = get_economic_calendar(FINNHUB_KEY)
    news = get_market_news(FINNHUB_KEY)

# ═══════════════════════════════════════════════════
# QUICK GLANCE
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
    
    try:
        nq_ticker = yf.Ticker("NQ=F")
        nq_hist = nq_ticker.history(period="1d")
        if not nq_hist.empty:
            nq_prev_close = nq_hist['Open'].iloc[0]
            nq_change = nq_now - nq_prev_close
            nq_change_pct = (nq_change / nq_prev_close) * 100
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
# GRID LAYOUT
# ═══════════════════════════════════════════════════

col_left, col_middle, col_right = st.columns([2, 3, 2])

with col_left:
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
        
        st.dataframe(pd.DataFrame(levels_data), hide_index=True, width='stretch')
    
    st.markdown('</div>', unsafe_allow_html=True)
    
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
            st.dataframe(pd.DataFrame(indicators_data), hide_index=True, width='stretch')
    
    st.markdown('</div>', unsafe_allow_html=True)
    
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

with col_middle:
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
            
            fig.add_hline(y=data_0dte['dn_nq'], line_dash="dot", line_color="#facc15", annotation_text="DN")
            fig.add_hline(y=data_0dte['g_flip_nq'], line_dash="dash", line_color="#a855f7", annotation_text="GF")
            fig.add_hline(y=data_0dte['p_wall'], line_color="#dc2626", annotation_text="Wall")
            fig.add_hline(y=data_0dte['p_floor'], line_color="#16a34a", annotation_text="Floor")
            
            if data_0dte['g_flip_nq'] < nq_data['High'].max():
                fig.add_hrect(y0=data_0dte['g_flip_nq'], y1=nq_data['High'].max(), fillcolor="red", opacity=0.05)
            
            if data_0dte['g_flip_nq'] > nq_data['Low'].min():
                fig.add_hrect(y0=nq_data['Low'].min(), y1=data_0dte['g_flip_nq'], fillcolor="green", opacity=0.05)
            
            fig.update_layout(
                template="plotly_dark",
                height=400,
                showlegend=False,
                hovermode='x unified',
                paper_bgcolor='#0a0e1a',
                plot_bgcolor='#0a0e1a'
            )
            
            fig.update_xaxes(rangeslider_visible=False)
            
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Chart data unavailable")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # DAILY BREAD WITH BLOOMBERG STYLING
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">🍞 Daily Bread</div>', unsafe_allow_html=True)
    
    if data_0dte:
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
        
        # Collapsible sections
        with st.expander("📊 Key Levels", expanded=False):
            st.markdown(daily_bread['levels'])
        
        with st.expander("📈 Market Drivers", expanded=False):
            st.markdown(daily_bread['drivers'])
        
        with st.expander("💼 Trading Strategy", expanded=False):
            st.markdown(daily_bread['strategy'])
        
        with st.expander("🔮 Tomorrow's Watch List", expanded=False):
            st.markdown(daily_bread['watch_list'])
    
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">📅 Today\'s Events</div>', unsafe_allow_html=True)
    
    if events:
        high_impact = [e for e in events if e.get('impact') == 'high']
        if high_impact:
            for event in high_impact[:3]:
                st.markdown(f"<span class='badge badge-bearish'>HIGH</span> {event.get('event', 'Unknown')[:50]}", unsafe_allow_html=True)
        else:
            st.info("Light calendar")
    else:
        st.info("No events")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">📰 Headlines</div>', unsafe_allow_html=True)
    
    if news:
        for article in news[:4]:
            headline = article.get('headline', 'No title')
            if len(headline) > 60:
                headline = headline[:57] + "..."
            st.markdown(f"**{headline}**")
            st.caption(article.get('source', 'Unknown'))
    else:
        st.info("No news")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="koyfin-card"><div class="koyfin-card-header">😱 Fear & Greed</div>', unsafe_allow_html=True)
    
    st.metric("Score", f"{fg['score']}/100", fg['rating'])
    
    if fg['score'] < 30:
        st.success("Extreme Fear")
    elif fg['score'] > 70:
        st.error("Extreme Greed")
    else:
        st.info(fg['rating'])
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} • Auto-refresh: 60s • Daily Bread updates 2x daily")
