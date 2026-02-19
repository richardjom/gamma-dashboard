import re
import time
from datetime import datetime, timezone

import feedparser
import finnhub
import pandas as pd
import requests
import streamlit as st
import yfinance as yf


SCHWAB_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
SCHWAB_QUOTES_URL = "https://api.schwabapi.com/marketdata/v1/quotes"
FUTURES_MONTH_CODES = {
    1: "F",
    2: "G",
    3: "H",
    4: "J",
    5: "K",
    6: "M",
    7: "N",
    8: "Q",
    9: "U",
    10: "V",
    11: "X",
    12: "Z",
}


def _get_secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _set_quote_meta(symbol, source, timestamp_ms=None):
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    st.session_state[f"quote_meta::{symbol}"] = {
        "source": source,
        "timestamp_ms": int(timestamp_ms),
    }


def get_quote_age_seconds(symbol):
    meta = st.session_state.get(f"quote_meta::{symbol}", {})
    ts = meta.get("timestamp_ms")
    if not ts:
        return None
    now_ms = int(time.time() * 1000)
    return max(0, int((now_ms - ts) / 1000))


def get_quote_age_label(symbol):
    age = get_quote_age_seconds(symbol)
    if age is None:
        return "N/A"
    if age < 60:
        return f"{age}s"
    mins = age // 60
    secs = age % 60
    return f"{mins}m {secs:02d}s"


def schwab_is_configured():
    return bool(_get_secret("SCHWAB_APP_KEY") and _get_secret("SCHWAB_APP_SECRET"))


def _next_quarterly_contracts(count=3):
    now = datetime.now(timezone.utc)
    quarter_months = [3, 6, 9, 12]
    contracts = []
    year = now.year
    month = now.month
    while len(contracts) < count:
        for q_month in quarter_months:
            if year == now.year and q_month < month:
                continue
            contracts.append((year, q_month))
            if len(contracts) == count:
                break
        year += 1
    return contracts


def _map_futures_symbol(futures_symbol):
    overrides = {
        "NQ=F": _get_secret("SCHWAB_SYMBOL_NQ", ""),
        "ES=F": _get_secret("SCHWAB_SYMBOL_ES", ""),
        "YM=F": _get_secret("SCHWAB_SYMBOL_YM", ""),
        "RTY=F": _get_secret("SCHWAB_SYMBOL_RTY", ""),
        "DX=F": _get_secret("SCHWAB_SYMBOL_DX", ""),
        "GC=F": _get_secret("SCHWAB_SYMBOL_GC", ""),
    }
    if overrides.get(futures_symbol):
        return overrides[futures_symbol]
    defaults = {
        "NQ=F": "/NQ",
        "ES=F": "/ES",
        "YM=F": "/YM",
        "RTY=F": "/RTY",
        "DX=F": "/DX",
        "GC=F": "/GC",
    }
    return defaults.get(futures_symbol, futures_symbol)


def _candidate_schwab_symbols(futures_symbol):
    mapped = _map_futures_symbol(futures_symbol)
    # If user provides explicit contract override, trust it as-is.
    if any(ch.isdigit() for ch in mapped):
        return [mapped]
    candidates = [mapped]
    if not mapped.startswith("/"):
        return candidates

    for year, month in _next_quarterly_contracts(count=4):
        month_code = FUTURES_MONTH_CODES[month]
        yy = str(year)[-2:]
        yyyy = str(year)
        candidates.append(f"{mapped}{month_code}{yy}")
        candidates.append(f"{mapped}{month_code}{yyyy}")

    # Keep order stable but unique.
    seen = set()
    deduped = []
    for sym in candidates:
        if sym in seen:
            continue
        seen.add(sym)
        deduped.append(sym)
    return deduped


def _get_schwab_access_token():
    static_token = _get_secret("SCHWAB_ACCESS_TOKEN")
    if static_token:
        return static_token

    now = time.time()
    cached_token = st.session_state.get("schwab_access_token")
    cached_exp = st.session_state.get("schwab_access_expires_at", 0)
    if cached_token and now < (cached_exp - 30):
        return cached_token

    app_key = _get_secret("SCHWAB_APP_KEY")
    app_secret = _get_secret("SCHWAB_APP_SECRET")
    refresh_token = _get_secret("SCHWAB_REFRESH_TOKEN")
    if not (app_key and app_secret and refresh_token):
        return None

    try:
        response = requests.post(
            SCHWAB_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(app_key, app_secret),
            timeout=10,
        )
        if response.status_code != 200:
            return None
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            return None
        expires_in = int(payload.get("expires_in", 1800))
        st.session_state["schwab_access_token"] = token
        st.session_state["schwab_access_expires_at"] = now + expires_in
        return token
    except Exception:
        return None


def exchange_schwab_auth_code(auth_code, redirect_uri):
    app_key = _get_secret("SCHWAB_APP_KEY")
    app_secret = _get_secret("SCHWAB_APP_SECRET")
    if not (app_key and app_secret):
        return None, "Missing SCHWAB_APP_KEY or SCHWAB_APP_SECRET in secrets."
    if not auth_code:
        return None, "Authorization code is required."

    try:
        response = requests.post(
            SCHWAB_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": redirect_uri,
            },
            auth=(app_key, app_secret),
            timeout=15,
        )
        if response.status_code != 200:
            return None, f"Token exchange failed ({response.status_code}): {response.text[:200]}"
        return response.json(), None
    except Exception as e:
        return None, f"Token exchange failed: {e}"


def _extract_quote_price(quote_obj):
    if not isinstance(quote_obj, dict):
        return None
    nested_quote = quote_obj.get("quote", {})
    candidates = [
        nested_quote.get("lastPrice"),
        nested_quote.get("mark"),
        nested_quote.get("closePrice"),
        quote_obj.get("lastPrice"),
        quote_obj.get("mark"),
        quote_obj.get("closePrice"),
    ]
    for value in candidates:
        if value in (None, "", 0):
            continue
        try:
            price = float(value)
            if price > 0:
                return price
        except Exception:
            continue
    return None


def _extract_quote_timestamp_ms(quote_obj):
    if not isinstance(quote_obj, dict):
        return None
    nested = quote_obj.get("quote", {})
    for key in (
        "quoteTime",
        "tradeTime",
        "lastTradeTime",
        "regularMarketTradeTime",
        "timestamp",
    ):
        raw = nested.get(key, quote_obj.get(key))
        if raw in (None, ""):
            continue
        try:
            value = int(float(raw))
            # Normalize seconds/microseconds to milliseconds.
            if value < 10**11:
                value *= 1000
            if value > 10**14:
                value //= 1000
            return value
        except Exception:
            continue
    return None


def _validate_price_range(symbol, price):
    symbol_ranges = {
        "NQ=F": (10000, 50000),
        "ES=F": (1000, 10000),
        "YM=F": (10000, 100000),
        "RTY=F": (500, 5000),
        "DX=F": (50, 200),
        "GC=F": (1000, 5000),
    }
    min_p, max_p = symbol_ranges.get(symbol, (0.01, 1e9))
    return min_p <= price <= max_p


def _validate_stale_quote(timestamp_ms):
    if not timestamp_ms:
        return True
    max_stale_sec = int(_get_secret("SCHWAB_MAX_STALE_SECONDS", 180))
    now_ms = int(time.time() * 1000)
    return (now_ms - timestamp_ms) <= (max_stale_sec * 1000)


def _validate_jump(symbol, price):
    key = f"last_good_price::{symbol}"
    previous = st.session_state.get(key)
    if not previous:
        st.session_state[key] = price
        return True
    if previous <= 0:
        st.session_state[key] = price
        return True
    jump_pct = abs(price - previous) / previous * 100
    max_jump_pct = float(_get_secret("MAX_ONE_TICK_JUMP_PCT", 5.0))
    if jump_pct > max_jump_pct:
        return False
    st.session_state[key] = price
    return True


def _get_schwab_quotes(symbols):
    token = _get_schwab_access_token()
    if not token:
        return {}
    try:
        response = requests.get(
            SCHWAB_QUOTES_URL,
            params={"symbols": ",".join(symbols), "fields": "quote"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if response.status_code == 401:
            st.session_state.pop("schwab_access_token", None)
            st.session_state.pop("schwab_access_expires_at", None)
            return {}
        if response.status_code != 200:
            return {}
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _get_schwab_futures_price(futures_symbol):
    candidates = _candidate_schwab_symbols(futures_symbol)
    quotes = _get_schwab_quotes(candidates)
    if not quotes:
        return None, "Schwab unavailable"

    lookup_keys = []
    for sym in candidates:
        lookup_keys.extend([sym, sym.lstrip("/")])
    lookup_keys.append(futures_symbol)

    for key in lookup_keys:
        if key in quotes:
            price = _extract_quote_price(quotes[key])
            ts = _extract_quote_timestamp_ms(quotes[key])
            if price and _validate_price_range(futures_symbol, price) and _validate_stale_quote(ts):
                if _validate_jump(futures_symbol, price):
                    _set_quote_meta(futures_symbol, f"Schwab ({key})", ts or int(time.time() * 1000))
                    return price, f"Schwab ({key})"

    for quote_key, value in quotes.items():
        price = _extract_quote_price(value)
        ts = _extract_quote_timestamp_ms(value)
        if price and _validate_price_range(futures_symbol, price) and _validate_stale_quote(ts):
            if _validate_jump(futures_symbol, price):
                _set_quote_meta(
                    futures_symbol,
                    f"Schwab ({quote_key})",
                    ts or int(time.time() * 1000),
                )
                return price, f"Schwab ({quote_key})"
    return None, "Schwab unavailable"


def _get_yahoo_chart_price(symbol, min_price=0):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            if price and price > min_price:
                _set_quote_meta(symbol, "Yahoo Finance")
                return float(price)
    except Exception:
        pass
    return None


def _schwab_cross_source_ok(yahoo_symbol, schwab_price):
    yahoo_price = _get_yahoo_chart_price(yahoo_symbol, min_price=0)
    if not yahoo_price:
        return True
    allowed_dev_pct = float(_get_secret("MAX_CROSS_SOURCE_DEVIATION_PCT", 3.0))
    deviation = abs(schwab_price - yahoo_price) / yahoo_price * 100
    return deviation <= allowed_dev_pct


def get_runtime_health():
    checks = []
    app_key = _get_secret("SCHWAB_APP_KEY")
    app_secret = _get_secret("SCHWAB_APP_SECRET")
    refresh = _get_secret("SCHWAB_REFRESH_TOKEN")
    redirect = _get_secret("SCHWAB_REDIRECT_URI")
    checks.append(("SCHWAB_APP_KEY", bool(app_key), "Present" if app_key else "Missing"))
    checks.append(("SCHWAB_APP_SECRET", bool(app_secret), "Present" if app_secret else "Missing"))
    checks.append(
        ("SCHWAB_REFRESH_TOKEN", bool(refresh), "Present" if refresh else "Missing (OAuth required)")
    )
    checks.append(
        ("SCHWAB_REDIRECT_URI", bool(redirect), redirect if redirect else "Missing")
    )
    token = _get_schwab_access_token() if (app_key and app_secret and refresh) else None
    checks.append(("Schwab token refresh", bool(token), "OK" if token else "Failed/unavailable"))
    return checks


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
    schwab_price, schwab_source = _get_schwab_futures_price("NQ=F")
    if schwab_price and schwab_price > 10000 and _schwab_cross_source_ok("NQ=F", schwab_price):
        return float(schwab_price), schwab_source

    yahoo_price = _get_yahoo_chart_price("NQ=F", min_price=10000)
    if yahoo_price:
        return float(yahoo_price), "Yahoo Finance"

    try:
        nq = yf.Ticker("NQ=F")
        data = nq.history(period="1d", interval="1m")
        if not data.empty:
            _set_quote_meta("NQ=F", "yfinance")
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


@st.cache_data(ttl=30)
def get_market_overview_yahoo():
    data = {}
    symbols = {
        "vix": "^VIX",
        "es": "ES=F",
        "ym": "YM=F",
        "rty": "RTY=F",
        "gc": "GC=F",
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
                    "source": "Yahoo Finance",
                }
                _set_quote_meta(symbol, "Yahoo Finance")
            else:
                data[key] = {
                    "price": 0,
                    "change": 0,
                    "change_pct": 0,
                    "source": "unavailable",
                }
        except Exception:
            data[key] = {"price": 0, "change": 0, "change_pct": 0, "source": "unavailable"}

    # Prefer Schwab real-time futures quotes when configured.
    for key, symbol in {
        "es": "ES=F",
        "ym": "YM=F",
        "rty": "RTY=F",
        "dxy": "DX=F",
        "gc": "GC=F",
    }.items():
        schwab_price, source = _get_schwab_futures_price(symbol)
        if schwab_price:
            data[key]["price"] = float(schwab_price)
            data[key]["source"] = source

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


NASDAQ_100_CORE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX",
    "AMD", "ADBE", "PEP", "CSCO", "INTC", "INTU", "QCOM", "AMGN", "TXN", "CMCSA",
    "AMAT", "BKNG", "SBUX", "GILD", "ISRG", "ADP", "ADI", "LRCX", "PYPL", "MU",
    "PANW", "MELI", "ASML", "SNPS", "KLAC", "CDNS", "MAR", "ORLY", "CSX", "AEP",
    "MRVL", "FTNT", "ADI", "KDP", "MNST", "WDAY", "NXPI", "TEAM", "CRWD", "ABNB",
]
MAG_7 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]


@st.cache_data(ttl=3600)
def _get_market_caps(symbols):
    market_caps = {}
    for sym in symbols:
        try:
            fi = yf.Ticker(sym).fast_info
            cap = fi.get("market_cap")
            if cap and cap > 0:
                market_caps[sym] = float(cap)
        except Exception:
            continue
    return market_caps


@st.cache_data(ttl=120)
def get_nasdaq_heatmap_data(universe="Nasdaq 100", size_mode="Market Cap", timeframe="5D", custom_symbols=""):
    custom = [s.strip().upper() for s in custom_symbols.split(",") if s.strip()]
    if universe == "Magnificent 7":
        symbols = MAG_7
    elif universe == "Custom Watchlist":
        symbols = custom
    else:
        symbols = NASDAQ_100_CORE

    if not symbols:
        return pd.DataFrame(columns=["symbol", "sector", "price", "change_pct", "size"])

    sector_map = {
        "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "AMD": "Technology",
        "AVGO": "Technology",
        "ADBE": "Technology", "CSCO": "Technology", "INTC": "Technology", "INTU": "Technology",
        "QCOM": "Technology", "AMAT": "Technology", "ADI": "Technology", "LRCX": "Technology",
        "MU": "Technology", "ADP": "Technology",
        "AMZN": "Consumer", "TSLA": "Consumer", "COST": "Consumer", "BKNG": "Consumer",
        "SBUX": "Consumer", "PYPL": "Financials",
        "GOOGL": "Communication", "META": "Communication", "NFLX": "Communication", "CMCSA": "Communication",
        "PEP": "Consumer Staples",
        "AMGN": "Healthcare", "GILD": "Healthcare", "ISRG": "Healthcare",
        "TXN": "Technology",
    }
    period_map = {"1D": "2d", "5D": "7d", "1M": "1mo"}
    period = period_map.get(timeframe, "7d")

    try:
        raw = yf.download(
            tickers=symbols,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
    except Exception:
        return pd.DataFrame(columns=["symbol", "sector", "price", "change_pct", "size"])

    market_caps = _get_market_caps(tuple(symbols)) if size_mode == "Market Cap" else {}
    rows = []
    for sym in symbols:
        try:
            if not isinstance(raw.columns, pd.MultiIndex):
                continue
            if sym not in raw.columns.get_level_values(0):
                continue
            sdata = raw[sym].dropna(how="all")
            if sdata.empty or "Close" not in sdata:
                continue
            close = sdata["Close"].dropna()
            if len(close) < 2:
                continue
            last = float(close.iloc[-1])
            prev = float(close.iloc[-2])
            if prev == 0:
                continue
            change_pct = ((last - prev) / prev) * 100.0
            volume = 1.0
            if "Volume" in sdata and not sdata["Volume"].dropna().empty:
                volume = float(max(1.0, sdata["Volume"].dropna().iloc[-1]))
            liquidity_size = max(1.0, (last * volume) / 1_000_000.0)
            if size_mode == "Equal Weight":
                size = 1.0
            elif size_mode == "Volume":
                size = liquidity_size
            else:
                cap = market_caps.get(sym, 0.0)
                size = max(1.0, cap / 1_000_000_000.0) if cap > 0 else liquidity_size
            rows.append(
                {
                    "symbol": sym,
                    "sector": sector_map.get(sym, "Misc"),
                    "price": last,
                    "change_pct": change_pct,
                    "size": size,
                }
            )
        except Exception:
            continue

    if not rows:
        return pd.DataFrame(columns=["symbol", "sector", "price", "change_pct", "size"])

    return pd.DataFrame(rows)


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
    schwab_price, schwab_source = _get_schwab_futures_price(symbol)
    if schwab_price and schwab_price > 100 and _schwab_cross_source_ok(symbol, schwab_price):
        return float(schwab_price), schwab_source

    yahoo_price = _get_yahoo_chart_price(symbol, min_price=100)
    if yahoo_price:
        return float(yahoo_price), "Yahoo Finance"

    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            _set_quote_meta(symbol, "yfinance")
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
