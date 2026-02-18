import re
from datetime import datetime

import feedparser
import finnhub
import pandas as pd
import requests
import streamlit as st
import yfinance as yf


@st.cache_data(ttl=14400)
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
        pattern = re.compile(r"^(.+)(\d{6})([PC])(\d+)$")

        def parse_option(row):
            match = pattern.search(row["option"])
            if match:
                exp_str = match.group(2)
                option_type = "call" if match.group(3) == "C" else "put"
                strike = int(match.group(4)) / 1000
                exp_date = datetime.strptime("20" + exp_str, "%Y%m%d")
                return pd.Series(
                    {"strike": strike, "type": option_type, "expiration": exp_date}
                )
            return pd.Series({"strike": 0, "type": "unknown", "expiration": None})

        parsed = df.apply(parse_option, axis=1)
        df = pd.concat([df, parsed], axis=1)
        df = df[df["type"] != "unknown"].copy()
        return df, current_price
    except Exception as e:
        st.error(f"CBOE fetch failed: {e}")
        return None, None


@st.cache_data(ttl=10)
def get_nq_price_auto(_finnhub_key):
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/NQ=F"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            if price and price > 10000:
                return float(price), "Yahoo Finance"
    except Exception:
        pass
    try:
        nq = yf.Ticker("NQ=F")
        data = nq.history(period="1d", interval="1m")
        if not data.empty:
            return float(data["Close"].iloc[-1]), "yfinance"
    except Exception:
        pass
    return None, "unavailable"


@st.cache_data(ttl=10)
def get_nq_intraday_data():
    try:
        nq = yf.Ticker("NQ=F")
        data = nq.history(period="1d", interval="5m")
        if not data.empty:
            return data.tail(50)
    except Exception:
        pass
    return None


@st.cache_data(ttl=10)
def get_qqq_price(finnhub_key):
    try:
        client = finnhub.Client(api_key=finnhub_key)
        quote = client.quote("QQQ")
        price = quote.get("c", 0)
        if price > 0:
            return float(price)
    except Exception:
        pass
    return None


@st.cache_data(ttl=600)
def get_market_overview_yahoo():
    data = {}
    symbols = {
        "vix": "^VIX",
        "es": "ES=F",
        "ym": "YM=F",
        "rty": "RTY=F",
        "10y": "^TNX",
        "dxy": "DX=F",
    }

    for key, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")

            if not hist.empty:
                current = hist["Close"].iloc[-1]
                prev_close = hist["Open"].iloc[0]
                change = current - prev_close
                change_pct = (change / prev_close) * 100 if prev_close != 0 else 0

                data[key] = {
                    "price": float(current),
                    "change": float(change),
                    "change_pct": float(change_pct),
                }
            else:
                data[key] = {"price": 0, "change": 0, "change_pct": 0}
        except Exception:
            data[key] = {"price": 0, "change": 0, "change_pct": 0}

    return data


@st.cache_data(ttl=3600)
def get_economic_calendar(finnhub_key):
    client = finnhub.Client(api_key=finnhub_key)
    today = datetime.now().date()

    try:
        calendar = client.economic_calendar()

        today_events = [
            event
            for event in calendar.get("economicCalendar", [])
            if event.get("time", "").startswith(str(today))
        ]

        today_events.sort(key=lambda x: x.get("time", ""))
        return today_events[:10]
    except Exception:
        return []


@st.cache_data(ttl=600)
def get_market_news(finnhub_key):
    client = finnhub.Client(api_key=finnhub_key)

    try:
        news = client.general_news("general", min_id=0)
        major_sources = ["Bloomberg", "CNBC", "Reuters", "WSJ", "MarketWatch"]
        filtered = [
            n
            for n in news[:50]
            if any(source.lower() in n.get("source", "").lower() for source in major_sources)
        ]
        return filtered[:10]
    except Exception:
        return []


@st.cache_data(ttl=86400)
def get_fear_greed_index():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            score = data.get("fear_and_greed", {}).get("score", 50)
            rating = data.get("fear_and_greed", {}).get("rating", "Neutral")
            return {"score": score, "rating": rating}
    except Exception:
        pass
    return {"score": 50, "rating": "Neutral"}


@st.cache_data(ttl=900)
def get_top_movers(finnhub_key):
    client = finnhub.Client(api_key=finnhub_key)
    tickers = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "NVDA",
        "TSLA",
        "META",
        "AMD",
        "NFLX",
        "DIS",
        "BABA",
        "JPM",
        "BAC",
        "XOM",
        "CVX",
    ]

    movers = []
    try:
        for ticker in tickers:
            quote = client.quote(ticker)
            movers.append(
                {
                    "symbol": ticker,
                    "price": quote.get("c", 0),
                    "change": quote.get("d", 0),
                    "change_pct": quote.get("dp", 0),
                }
            )

        movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        gainers = [m for m in movers if m["change_pct"] > 0][:5]
        losers = [m for m in movers if m["change_pct"] < 0][:5]

        return {"gainers": gainers, "losers": losers}
    except Exception:
        return {"gainers": [], "losers": []}


def get_expirations_by_type(df):
    today = datetime.now().date()
    expirations = sorted(df["expiration"].dropna().unique())

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

    calls = df_calc[df_calc["type"] == "call"].copy()
    calls["delta_notional"] = calls["open_interest"] * calls["delta"] * 100 * qqq_price

    puts = df_calc[df_calc["type"] == "put"].copy()
    puts["delta_notional"] = (
        puts["open_interest"] * puts["delta"] * 100 * qqq_price * -1
    )

    all_delta = pd.concat([calls, puts])
    strike_delta = all_delta.groupby("strike")["delta_notional"].sum().reset_index()
    strike_delta = strike_delta.sort_values("strike")
    strike_delta["cumulative_delta"] = strike_delta["delta_notional"].cumsum()

    min_idx = strike_delta["cumulative_delta"].abs().idxmin()
    dn_strike = strike_delta.loc[min_idx, "strike"]

    df_calc["delta_exposure"] = df_calc.apply(
        lambda x: x["open_interest"] * x["delta"] * 100 * (1 if x["type"] == "call" else -1),
        axis=1,
    )

    return dn_strike, strike_delta, df_calc


def calculate_sentiment_score(data_0dte, nq_now, vix_level, fg_score):
    score = 50

    if data_0dte:
        dn_distance = nq_now - data_0dte["dn_nq"]
        gf_distance = nq_now - data_0dte["g_flip_nq"]

        if abs(dn_distance) > 200:
            if dn_distance > 0:
                score -= 15
            else:
                score += 15

        if gf_distance > 0:
            score -= 10
        else:
            score += 10

        if data_0dte["net_delta"] > 0:
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


@st.cache_data(ttl=10)
def get_futures_price(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            if price and price > 100:
                return float(price), "Yahoo Finance"
    except Exception:
        pass
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            return float(data["Close"].iloc[-1]), "yfinance"
    except Exception:
        pass
    return None, "unavailable"


@st.cache_data(ttl=14400)
def process_multi_asset():
    assets_config = {
        "SPY": {"ticker": "SPY", "futures": "ES=F", "name": "S&P 500"},
        "QQQ": {"ticker": "QQQ", "futures": "NQ=F", "name": "Nasdaq"},
        "IWM": {"ticker": "IWM", "futures": "RTY=F", "name": "Russell 2000"},
        "DIA": {"ticker": "DIA", "futures": "YM=F", "name": "Dow Jones"},
    }

    results = {}

    for asset_name, config in assets_config.items():
        try:
            df_raw, etf_price = get_cboe_options(config["ticker"])
            if df_raw is None or etf_price is None:
                continue

            futures_price, source = get_futures_price(config["futures"])
            if futures_price is None:
                continue

            ratio = futures_price / etf_price if etf_price > 0 else 0
            exp_0dte, exp_weekly, _exp_monthly = get_expirations_by_type(df_raw)

            data_0dte = None
            if exp_0dte:
                data_0dte = process_expiration(
                    df_raw, exp_0dte, etf_price, ratio, futures_price
                )

            data_weekly = None
            if exp_weekly and exp_weekly != exp_0dte:
                data_weekly = process_expiration(
                    df_raw, exp_weekly, etf_price, ratio, futures_price
                )

            results[asset_name] = {
                "name": config["name"],
                "ticker": config["ticker"],
                "futures_symbol": config["futures"],
                "etf_price": etf_price,
                "futures_price": futures_price,
                "ratio": ratio,
                "source": source,
                "data_0dte": data_0dte,
                "data_weekly": data_weekly,
            }

        except Exception as e:
            st.warning(f"Could not process {asset_name}: {e}")
            continue

    return results


@st.cache_data(ttl=30)
def get_rss_news():
    feeds = {
        "Reuters Business": "http://feeds.reuters.com/reuters/businessNews",
        "MarketWatch Top Stories": "http://feeds.marketwatch.com/marketwatch/topstories",
        "CNBC Top News": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "WSJ Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    }

    all_news = []

    for source_name, feed_url in feeds.items():
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:5]:
                try:
                    pub_date = entry.get("published", "")
                    all_news.append(
                        {
                            "headline": entry.get("title", "No title"),
                            "source": source_name,
                            "link": entry.get("link", "#"),
                            "published": pub_date,
                            "summary": entry.get("summary", "")[:200],
                        }
                    )
                except Exception:
                    continue

        except Exception:
            continue

    return all_news[:20]


@st.cache_data(ttl=14400)
def process_expiration(df_raw, target_exp, qqq_price, ratio, nq_now):
    df = df_raw[df_raw["expiration"] == target_exp].copy()
    df = df[df["open_interest"] > 0].copy()
    df = df[df["iv"] > 0].copy()
    df = df[(df["strike"] > qqq_price * 0.98) & (df["strike"] < qqq_price * 1.02)].copy()

    if len(df) == 0:
        return None

    dn_strike, strike_delta, df = calculate_delta_neutral(df, qqq_price)
    dn_nq = dn_strike * ratio

    total_call_delta = df[df["type"] == "call"]["delta_exposure"].sum()
    total_put_delta = df[df["type"] == "put"]["delta_exposure"].sum()
    net_delta = total_call_delta + total_put_delta

    atm_strike = df.iloc[(df["strike"] - qqq_price).abs().argsort()[:1]]["strike"].values[0]
    atm_opts = df[df["strike"] == atm_strike]
    atm_call = atm_opts[atm_opts["type"] == "call"]
    atm_put = atm_opts[atm_opts["type"] == "put"]

    if len(atm_call) > 0 and len(atm_put) > 0:
        call_mid = (atm_call.iloc[0]["bid"] + atm_call.iloc[0]["ask"]) / 2
        put_mid = (atm_put.iloc[0]["bid"] + atm_put.iloc[0]["ask"]) / 2
        straddle = call_mid + put_mid
    else:
        straddle = qqq_price * 0.012

    nq_em_full = (straddle * 1.25 if straddle > 0 else qqq_price * 0.012) * ratio
    nq_em_050 = nq_em_full * 0.50
    nq_em_025 = nq_em_full * 0.25

    df["GEX"] = df.apply(
        lambda x: x["open_interest"]
        * x["gamma"]
        * (qqq_price**2)
        * 0.01
        * (1 if x["type"] == "call" else -1),
        axis=1,
    )

    calls = df[df["type"] == "call"].sort_values("GEX", ascending=False)
    puts = df[df["type"] == "put"].sort_values("GEX", ascending=True)

    calls_above = calls[calls["strike"] > qqq_price]
    if len(calls_above) > 0:
        p_wall_strike = calls_above.iloc[0]["strike"]
    else:
        p_wall_strike = calls.iloc[0]["strike"] if len(calls) > 0 else qqq_price * 1.01

    puts_below = puts[puts["strike"] < qqq_price]
    if len(puts_below) > 0:
        p_floor_strike = puts_below.iloc[0]["strike"]
    else:
        p_floor_strike = puts.iloc[0]["strike"] if len(puts) > 0 else qqq_price * 0.99

    if p_floor_strike >= p_wall_strike:
        p_floor_strike = min(puts["strike"]) if len(puts) > 0 else qqq_price * 0.99
        p_wall_strike = max(calls["strike"]) if len(calls) > 0 else qqq_price * 1.01

    s_wall_strike = p_wall_strike
    for i in range(len(calls)):
        candidate = calls.iloc[i]["strike"]
        if candidate > p_wall_strike and candidate != p_wall_strike:
            s_wall_strike = candidate
            break

    s_floor_strike = p_floor_strike
    for i in range(len(puts)):
        candidate = puts.iloc[i]["strike"]
        if candidate < p_floor_strike and candidate != p_floor_strike:
            s_floor_strike = candidate
            break

    if s_floor_strike >= s_wall_strike:
        s_floor_strike = p_floor_strike * 0.995
        s_wall_strike = p_wall_strike * 1.005

    g_flip_strike = df.groupby("strike")["GEX"].sum().abs().idxmin()

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
        ("Lower 0.50σ", nq_now - nq_em_050, 5.0, "📊"),
    ]

    return {
        "df": df,
        "dn_strike": dn_strike,
        "dn_nq": dn_nq,
        "g_flip_strike": g_flip_strike,
        "g_flip_nq": g_flip_strike * ratio,
        "net_delta": net_delta,
        "p_wall": p_wall_strike * ratio,
        "p_floor": p_floor_strike * ratio,
        "s_wall": s_wall_strike * ratio,
        "s_floor": s_floor_strike * ratio,
        "calls": calls,
        "puts": puts,
        "strike_delta": strike_delta,
        "results": results,
        "straddle": straddle,
        "nq_em_full": nq_em_full,
        "atm_strike": atm_strike,
    }


@st.cache_data(ttl=14400)
def generate_daily_bread(data_0dte, data_weekly, nq_now, market_data, fg, events, news):
    current_hour = datetime.now().hour
    is_morning = current_hour < 12

    report = {}
    report["timestamp"] = datetime.now().strftime("%A, %B %d, %Y • %I:%M %p EST")
    report["session"] = "MORNING BRIEF" if is_morning else "MARKET CLOSE SUMMARY"

    if not data_0dte:
        return report

    dn_distance = nq_now - data_0dte["dn_nq"]
    gf_distance = nq_now - data_0dte["g_flip_nq"]
    above_dn = dn_distance > 0
    above_gf = gf_distance > 0

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

    report["tone"] = tone
    report["summary"] = summary

    report["levels"] = f"""**CRITICAL LEVELS FOR TODAY:**

- **Delta Neutral:** {data_0dte['dn_nq']:.2f} — Primary gravitational pull
- **Gamma Flip:** {data_0dte['g_flip_nq']:.2f} — Regime change threshold
- **Primary Resistance:** {data_0dte['p_wall']:.2f} — Heaviest call wall
- **Primary Support:** {data_0dte['p_floor']:.2f} — Heaviest put floor
- **Expected Move:** ±{data_0dte['nq_em_full']:.0f} points ({data_0dte['nq_em_full']/nq_now*100:.1f}%)"""

    vix = market_data.get("vix", {}).get("price", 0)
    vix_change = market_data.get("vix", {}).get("change_pct", 0)

    drivers = f"""**MARKET DRIVERS:**

- **VIX:** {vix:.2f} ({vix_change:+.2f}%) — {'Elevated volatility' if vix > 18 else 'Low volatility regime'}
- **Fear & Greed:** {fg['score']}/100 ({fg['rating']}) — {'Contrarian buy signal' if fg['score'] < 30 else 'Contrarian sell signal' if fg['score'] > 70 else 'Neutral sentiment'}"""

    if events:
        high_impact = [e for e in events if e.get("impact") == "high"]
        if high_impact:
            drivers += "\n• **High-impact events:** " + ", ".join(
                [e.get("event", "Unknown")[:40] for e in high_impact[:2]]
            )

    report["drivers"] = drivers

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

    report["strategy"] = strategy

    watch_items = []

    if abs(dn_distance) > 200:
        watch_items.append(
            f"• **Delta Neutral convergence:** Price {abs(dn_distance):.0f}pts extended — mean reversion likely"
        )

    if above_gf:
        watch_items.append(
            f"• **Gamma Flip breakdown:** Break below {data_0dte['g_flip_nq']:.2f} signals regime shift to stability"
        )

    if data_weekly:
        dn_spread = abs(data_0dte["dn_nq"] - data_weekly["dn_nq"])
        if dn_spread > 100:
            watch_items.append(
                f"• **Timeframe divergence:** {dn_spread:.0f}pt spread between 0DTE/Weekly DN suggests choppy action"
            )

    watch_items.append("• **VIX expansion:** Spike above 18 signals vol regime change")
    watch_items.append(
        "• **Options expiration:** 0DTE levels reset tomorrow — gamma exposure shifts"
    )

    report["watch_list"] = "\n".join(watch_items)

    return report
