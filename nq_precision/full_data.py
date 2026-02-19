import re
import time
from datetime import datetime, timezone, timedelta
import math
from zoneinfo import ZoneInfo

import feedparser
import finnhub
import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from bs4 import BeautifulSoup


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

# Major companies most likely to move NQ / ES / YM around earnings.
MAJOR_INDEX_IMPACT_TICKERS = {
    # NQ-heavy mega cap / semis / software
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX",
    "ADBE", "INTC", "CSCO", "QCOM", "AMAT", "MU", "TXN", "LRCX", "ADI", "PANW",
    "CRM", "ORCL", "INTU", "NOW", "SNOW", "PLTR",
    # ES / broad market heavyweights
    "BRK.B", "BRK-B", "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "UNH", "LLY",
    "XOM", "CVX", "JNJ", "PG", "HD", "WMT", "COST", "ABBV", "MRK", "KO", "PEP",
    # YM (Dow components)
    "MMM", "AXP", "AMGN", "BA", "CAT", "CRM", "CSCO", "DIS", "DOW", "GS", "HON",
    "IBM", "JNJ", "JPM", "MCD", "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "VZ",
    "V", "WMT",
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
    events = get_economic_calendar_window(finnhub_key, days=1)
    if events.empty:
        return []
    return events.to_dict(orient="records")[:10]


def _parse_event_dt_et(raw_value):
    if not raw_value:
        return None
    s = str(raw_value).strip()
    if not s:
        return None
    et = ZoneInfo("America/New_York")
    dt = None
    # Unix timestamp support.
    try:
        if s.isdigit():
            ts = int(s)
            if ts > 10**12:
                ts = ts / 1000.0
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        dt = None
    try:
        if dt is None:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    if dt is None:
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except Exception:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(et)


def _normalize_impact(impact_raw):
    v = str(impact_raw or "").strip().lower()
    if v in {"high", "3", "h"}:
        return "high"
    if v in {"medium", "med", "2", "m"}:
        return "medium"
    if v in {"low", "1", "l"}:
        return "low"
    return "medium"


def _is_missing_value(v):
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    s = str(v).strip().lower()
    return s in {"", "-", "none", "nan", "null", "n/a"}


def _pick_first_present(row, keys):
    for k in keys:
        if k in row and not _is_missing_value(row.get(k)):
            return row.get(k)
    return None


def _fetch_forexfactory_calendar(start_date, end_date):
    items = []
    et = ZoneInfo("America/New_York")
    urls = [
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
    ]
    data = None
    for url in urls:
        try:
            res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code != 200:
                continue
            payload = res.json()
            if isinstance(payload, list) and payload:
                data = payload
                break
        except Exception:
            continue
    if not isinstance(data, list):
        return items

    for e in data:
        try:
            raw_date = str(e.get("date", "")).strip()
            event_dt = None
            if raw_date:
                parsed = pd.to_datetime(raw_date, errors="coerce", utc=True)
                if not pd.isna(parsed):
                    event_dt = parsed.to_pydatetime().astimezone(et)

            # Keep event even if time parsing fails; don't zero out the whole calendar.
            if event_dt is None:
                date_label = str(e.get("dateLabel", "")).strip()
                if date_label:
                    fallback_day = pd.to_datetime(date_label, errors="coerce")
                    if not pd.isna(fallback_day):
                        event_dt = datetime.combine(
                            fallback_day.date(), datetime.min.time(), tzinfo=et
                        )
            if event_dt is None:
                event_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=et)

            if not (start_date <= event_dt.date() <= end_date):
                continue

            impact_raw = str(e.get("impact", "")).lower()
            if "high" in impact_raw:
                impact = "high"
            elif "medium" in impact_raw or "med" in impact_raw:
                impact = "medium"
            elif "low" in impact_raw:
                impact = "low"
            else:
                impact = "medium"

            actual_val = _pick_first_present(e, ["actual", "actualValue", "actual_value", "act"])
            expected_val = _pick_first_present(e, ["forecast", "consensus", "estimate", "expected"])
            prior_val = _pick_first_present(e, ["previous", "prev", "prior"])
            items.append(
                {
                    "event": e.get("title") or e.get("event") or "Unknown",
                    "country": e.get("country", "US"),
                    "impact": impact,
                    "actual": actual_val,
                    "expected": expected_val,
                    "prior": prior_val,
                    "for_period": e.get("dateLabel") or e.get("reference") or "-",
                    "time_et": event_dt.strftime("%I:%M %p").lstrip("0") if event_dt.time() != datetime.min.time() else "Time TBA",
                    "date_et": event_dt.date().isoformat(),
                    "event_dt_iso": event_dt.isoformat(),
                    "source": "ForexFactory",
                }
            )
        except Exception:
            continue
    return items


def _fetch_marketwatch_economic_calendar(start_date, end_date):
    items = []
    et = ZoneInfo("America/New_York")
    urls = [
        "https://www.marketwatch.com/economy-politics/calendar",
        "https://www.marketwatch.com/economy-politics/calendar?mod=mw_latestnews",
    ]
    html_text = ""
    for url in urls:
        try:
            res = requests.get(
                url,
                timeout=12,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            if res.status_code == 200 and res.text:
                html_text = res.text
                break
        except Exception:
            continue
    if not html_text:
        return items

    try:
        soup = BeautifulSoup(html_text, "html.parser")
    except Exception:
        return items

    day_labels = []
    for h in soup.find_all(["h2", "h3", "th", "div"]):
        txt = " ".join((h.get_text(" ", strip=True) or "").split())
        if re.search(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+[A-Za-z]{3}\s+\d{1,2}", txt):
            day_labels.append(txt)
    day_map = {}
    for lbl in day_labels:
        try:
            dt = pd.to_datetime(lbl, errors="coerce")
            if pd.isna(dt):
                continue
            day_map[lbl] = dt.date()
        except Exception:
            continue

    rows = soup.find_all("tr")
    current_day = start_date
    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 3:
            maybe_header = " ".join((tr.get_text(" ", strip=True) or "").split())
            for lbl, d in day_map.items():
                if lbl in maybe_header:
                    current_day = d
                    break
            continue

        cols = [" ".join((td.get_text(" ", strip=True) or "").split()) for td in tds]
        if not any(cols):
            continue
        # Best-effort extraction from varying table layouts.
        time_raw = cols[0] if len(cols) > 0 else "Time TBA"
        event_name = cols[1] if len(cols) > 1 else "Unknown"
        actual = cols[2] if len(cols) > 2 else "-"
        expected = cols[3] if len(cols) > 3 else "-"
        prior = cols[4] if len(cols) > 4 else "-"

        if not event_name or event_name.lower() in {"event", "release"}:
            continue
        if current_day < start_date or current_day > end_date:
            continue

        time_clean = "Time TBA"
        event_dt = datetime.combine(current_day, datetime.min.time(), tzinfo=et)
        try:
            if re.search(r"\d", time_raw):
                parsed_t = pd.to_datetime(time_raw, errors="coerce")
                if not pd.isna(parsed_t):
                    t = parsed_t.to_pydatetime().time()
                    event_dt = datetime.combine(current_day, t, tzinfo=et)
                    time_clean = event_dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            pass

        impact = "medium"
        lower_name = event_name.lower()
        if any(k in lower_name for k in ["fomc", "cpi", "ppi", "nfp", "payroll", "fed", "powell", "rate decision"]):
            impact = "high"
        elif any(k in lower_name for k in ["claims", "housing", "pmi", "durable"]):
            impact = "medium"
        else:
            impact = "low"

        items.append(
            {
                "event": event_name,
                "country": "US",
                "impact": impact,
                "actual": actual,
                "expected": expected,
                "prior": prior,
                "for_period": "-",
                "time_et": time_clean,
                "date_et": current_day.isoformat(),
                "event_dt_iso": event_dt.isoformat(),
                "source": "MarketWatch",
            }
        )
    return items


def _fetch_finviz_economic_calendar(start_date, end_date):
    items = []
    et = ZoneInfo("America/New_York")
    url = "https://finviz.com/calendar.ashx"
    try:
        res = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://finviz.com/",
            },
        )
        if res.status_code != 200 or not res.text:
            return items
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception:
        return items

    # Finviz calendar rows include date marker rows and event rows.
    rows = soup.find_all("tr")
    current_day = None

    for tr in rows:
        tds = tr.find_all("td")
        if not tds:
            continue
        cols = [" ".join((td.get_text(" ", strip=True) or "").split()) for td in tds]
        if not any(cols):
            continue

        # Date marker rows often like "Wednesday February 19, 2026"
        first_text = cols[0]
        if len(cols) <= 3:
            parsed_day = pd.to_datetime(first_text, errors="coerce")
            if not pd.isna(parsed_day):
                current_day = parsed_day.date()
                continue

        if current_day is None:
            # Try detecting day from any leading date cell
            maybe_date = pd.to_datetime(first_text, errors="coerce")
            if not pd.isna(maybe_date):
                current_day = maybe_date.date()

        if current_day is None:
            continue
        if current_day < start_date or current_day > end_date:
            continue

        # Heuristic mapping for typical Finviz columns:
        # Time | Country | Impact | Event | Actual | Forecast | Previous
        # Some layouts omit country and/or reorder slightly.
        time_raw = cols[0] if len(cols) > 0 else "Time TBA"
        country = cols[1] if len(cols) > 1 else "US"
        impact_raw = cols[2] if len(cols) > 2 else ""
        event_name = cols[3] if len(cols) > 3 else (cols[2] if len(cols) > 2 else "Unknown")
        actual = cols[4] if len(cols) > 4 else "-"
        expected = cols[5] if len(cols) > 5 else "-"
        prior = cols[6] if len(cols) > 6 else "-"

        if not event_name or event_name.lower() in {"event", "release", "calendar"}:
            continue

        impact = "medium"
        impact_check = impact_raw.lower()
        if "high" in impact_check or impact_check.count("bull") >= 3:
            impact = "high"
        elif "low" in impact_check or impact_check.count("bull") == 1:
            impact = "low"

        event_dt = datetime.combine(current_day, datetime.min.time(), tzinfo=et)
        time_et = "Time TBA"
        try:
            parsed_t = pd.to_datetime(time_raw, errors="coerce")
            if not pd.isna(parsed_t):
                tt = parsed_t.to_pydatetime().time()
                event_dt = datetime.combine(current_day, tt, tzinfo=et)
                time_et = event_dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            pass

        items.append(
            {
                "event": event_name,
                "country": country if country else "US",
                "impact": impact,
                "actual": actual,
                "expected": expected,
                "prior": prior,
                "for_period": "-",
                "time_et": time_et,
                "date_et": current_day.isoformat(),
                "event_dt_iso": event_dt.isoformat(),
                "source": "Finviz",
            }
        )

    return items


def _fetch_tradingeconomics_calendar(start_date, end_date):
    items = []
    et = ZoneInfo("America/New_York")
    # Public guest access often works for calendar reads.
    url = (
        "https://api.tradingeconomics.com/calendar"
        f"?c=guest:guest&f=json&d1={start_date.isoformat()}&d2={end_date.isoformat()}"
    )
    try:
        res = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code != 200:
            return items
        data = res.json()
        if not isinstance(data, list):
            return items
    except Exception:
        return items

    for e in data:
        try:
            event_dt = (
                _parse_event_dt_et(e.get("Date"))
                or _parse_event_dt_et(e.get("date"))
                or _parse_event_dt_et(e.get("CalendarDate"))
            )
            if event_dt is None:
                event_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=et)
            if not (start_date <= event_dt.date() <= end_date):
                continue

            importance = str(e.get("Importance", "")).strip().lower()
            if "3" in importance or "high" in importance:
                impact = "high"
            elif "2" in importance or "medium" in importance or "med" in importance:
                impact = "medium"
            else:
                impact = "low"

            items.append(
                {
                    "event": e.get("Event") or e.get("event") or "Unknown",
                    "country": e.get("Country") or e.get("country") or "US",
                    "impact": impact,
                    "actual": _pick_first_present(e, ["Actual", "actual"]),
                    "expected": _pick_first_present(e, ["Forecast", "forecast", "Consensus"]),
                    "prior": _pick_first_present(e, ["Previous", "previous"]),
                    "for_period": _pick_first_present(e, ["Reference", "reference", "Period", "period"]) or "-",
                    "time_et": event_dt.strftime("%I:%M %p").lstrip("0") if event_dt.time() != datetime.min.time() else "Time TBA",
                    "date_et": event_dt.date().isoformat(),
                    "event_dt_iso": event_dt.isoformat(),
                    "source": "TradingEconomics",
                }
            )
        except Exception:
            continue
    return items


def _fetch_fmp_economic_calendar(start_date, end_date):
    items = []
    et = ZoneInfo("America/New_York")
    api_key = _get_secret("FMP_API_KEY", "demo")
    url = (
        "https://financialmodelingprep.com/api/v3/economic_calendar"
        f"?from={start_date.isoformat()}&to={end_date.isoformat()}&apikey={api_key}"
    )
    try:
        res = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code != 200:
            return items
        data = res.json()
        if not isinstance(data, list):
            return items
    except Exception:
        return items

    for e in data:
        try:
            event_dt = (
                _parse_event_dt_et(e.get("date"))
                or _parse_event_dt_et(e.get("datetime"))
                or _parse_event_dt_et(e.get("time"))
            )
            if event_dt is None:
                event_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=et)
            if not (start_date <= event_dt.date() <= end_date):
                continue

            impact_raw = str(e.get("impact", "")).lower()
            if "high" in impact_raw:
                impact = "high"
            elif "medium" in impact_raw or "med" in impact_raw:
                impact = "medium"
            else:
                impact = "low"

            items.append(
                {
                    "event": e.get("event") or e.get("name") or "Unknown",
                    "country": e.get("country") or "US",
                    "impact": impact,
                    "actual": _pick_first_present(e, ["actual"]),
                    "expected": _pick_first_present(e, ["estimate", "forecast", "consensus"]),
                    "prior": _pick_first_present(e, ["previous", "prior"]),
                    "for_period": _pick_first_present(e, ["period", "reference"]) or "-",
                    "time_et": event_dt.strftime("%I:%M %p").lstrip("0") if event_dt.time() != datetime.min.time() else "Time TBA",
                    "date_et": event_dt.date().isoformat(),
                    "event_dt_iso": event_dt.isoformat(),
                    "source": "FMP",
                }
            )
        except Exception:
            continue
    return items


@st.cache_data(ttl=30)
def get_economic_calendar_window(finnhub_key, days=3):
    client = finnhub.Client(api_key=finnhub_key)
    et = ZoneInfo("America/New_York")
    start = datetime.now(et).date()
    end = start + timedelta(days=max(1, int(days)))
    items = []

    try:
        try:
            calendar = client.economic_calendar(_from=str(start), to=str(end))
        except Exception:
            calendar = client.economic_calendar()
        if isinstance(calendar, dict):
            events = (
                calendar.get("economicCalendar")
                or calendar.get("calendar")
                or calendar.get("events")
                or []
            )
        elif isinstance(calendar, list):
            events = calendar
        else:
            events = []
    except Exception:
        events = []

    for e in events:
        try:
            # Try multiple potential fields from different providers/shapes.
            event_dt = (
                _parse_event_dt_et(e.get("time"))
                or _parse_event_dt_et(e.get("datetime"))
                or _parse_event_dt_et(e.get("dateTime"))
                or _parse_event_dt_et(e.get("releaseDate"))
            )
            if event_dt is None:
                date_raw = str(e.get("date", "")).strip()
                if date_raw:
                    parsed = pd.to_datetime(date_raw, errors="coerce")
                    if not pd.isna(parsed):
                        event_dt = parsed.to_pydatetime()
                        if event_dt.tzinfo is None:
                            event_dt = event_dt.replace(tzinfo=et)
                        else:
                            event_dt = event_dt.astimezone(et)
                else:
                    event_dt = None
            if event_dt is None:
                # Keep item with fallback date when provider omits or mangles time.
                event_dt = datetime.combine(start, datetime.min.time(), tzinfo=et)
            if not (start <= event_dt.date() <= end):
                continue
            actual_val = _pick_first_present(e, ["actual", "actualValue", "actual_value", "act"])
            expected_val = _pick_first_present(e, ["estimate", "forecast", "consensus", "expected"])
            prior_val = _pick_first_present(e, ["prev", "previous", "prior"])
            items.append(
                {
                    "event": e.get("event") or e.get("indicator") or e.get("name") or "Unknown",
                    "country": e.get("country", "US"),
                    "impact": _normalize_impact(e.get("impact")),
                    "actual": actual_val,
                    "expected": expected_val,
                    "prior": prior_val,
                    "for_period": e.get("period") if e.get("period") is not None else e.get("for"),
                    "time_et": event_dt.strftime("%I:%M %p").lstrip("0") if event_dt.time() != datetime.min.time() else "Time TBA",
                    "date_et": event_dt.date().isoformat(),
                    "event_dt_iso": event_dt.isoformat(),
                    "source": "Finnhub",
                }
            )
        except Exception:
            continue

    # Fallback source (ForexFactory weekly feed) to prevent empty calendar.
    try:
        ff_items = _fetch_forexfactory_calendar(start, end)
        items.extend(ff_items)
    except Exception:
        pass
    try:
        te_items = _fetch_tradingeconomics_calendar(start, end)
        items.extend(te_items)
    except Exception:
        pass
    try:
        fmp_items = _fetch_fmp_economic_calendar(start, end)
        items.extend(fmp_items)
    except Exception:
        pass
    try:
        mw_items = _fetch_marketwatch_economic_calendar(start, end)
        items.extend(mw_items)
    except Exception:
        pass
    try:
        fv_items = _fetch_finviz_economic_calendar(start, end)
        items.extend(fv_items)
    except Exception:
        pass

    # Rescue pass: if strict parsing/filtering produced no rows, keep raw Finnhub events
    # as best-effort records so UI does not show an empty window.
    if not items:
        try:
            raw_calendar = client.economic_calendar()
            raw_events = []
            if isinstance(raw_calendar, dict):
                raw_events = (
                    raw_calendar.get("economicCalendar")
                    or raw_calendar.get("calendar")
                    or raw_calendar.get("events")
                    or []
                )
            elif isinstance(raw_calendar, list):
                raw_events = raw_calendar
            for e in raw_events[:250]:
                event_name = e.get("event") or e.get("indicator") or e.get("name") or "Unknown"
                if not event_name:
                    continue
                items.append(
                    {
                        "event": event_name,
                        "country": e.get("country", "US"),
                        "impact": _normalize_impact(e.get("impact")),
                        "actual": _pick_first_present(e, ["actual", "actualValue", "actual_value", "act"]),
                        "expected": _pick_first_present(e, ["estimate", "forecast", "consensus", "expected"]),
                        "prior": _pick_first_present(e, ["prev", "previous", "prior"]),
                        "for_period": e.get("period") if e.get("period") is not None else e.get("for"),
                        "time_et": "Time TBA",
                        "date_et": start.isoformat(),
                        "event_dt_iso": datetime.combine(start, datetime.min.time(), tzinfo=et).isoformat(),
                        "source": "Finnhub",
                    }
                )
        except Exception:
            pass

    raw_source_counts = {}
    for it in items:
        src = it.get("source", "Unknown")
        raw_source_counts[src] = raw_source_counts.get(src, 0) + 1
    st.session_state["econ_source_counts_raw"] = raw_source_counts

    df = pd.DataFrame(items)
    if df.empty:
        st.session_state["econ_source_counts_final"] = {}
        return pd.DataFrame(
            columns=[
                "event",
                "country",
                "impact",
                "actual",
                "expected",
                "prior",
                "for_period",
                "time_et",
                "date_et",
                "event_dt_iso",
            ]
        )

    # Keep the best row per event key: prefer rows that have actual/expected/prior populated.
    source_rank = {
        "Finviz": 0,
        "TradingEconomics": 1,
        "FMP": 2,
        "Finnhub": 3,
        "ForexFactory": 4,
        "MarketWatch": 5,
    }
    if "source" not in df.columns:
        df["source"] = "Unknown"
    df["source_rank"] = df["source"].map(lambda s: source_rank.get(s, 99))
    df["has_actual"] = df["actual"].map(lambda v: 0 if _is_missing_value(v) else 1)
    df["has_expected"] = df["expected"].map(lambda v: 0 if _is_missing_value(v) else 1)
    df["has_prior"] = df["prior"].map(lambda v: 0 if _is_missing_value(v) else 1)
    df["quality_score"] = (df["has_actual"] * 4) + (df["has_expected"] * 2) + df["has_prior"]

    df = df.sort_values(
        ["date_et", "event_dt_iso", "event", "country", "quality_score", "source_rank"],
        ascending=[True, True, True, True, False, True],
    )
    df = df.drop_duplicates(subset=["date_et", "time_et", "event", "country"], keep="first")
    df = df.drop(columns=["source_rank", "has_actual", "has_expected", "has_prior", "quality_score"], errors="ignore")
    df = df.sort_values(["date_et", "event_dt_iso", "event"])
    st.session_state["econ_source_counts_final"] = (
        df["source"].value_counts(dropna=False).to_dict() if "source" in df.columns else {}
    )
    return df.reset_index(drop=True)


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
    dn_strike = None
    for i in range(1, len(strike_delta)):
        prev_val = float(strike_delta.iloc[i - 1]["cumulative_delta"])
        curr_val = float(strike_delta.iloc[i]["cumulative_delta"])
        if prev_val == 0:
            dn_strike = float(strike_delta.iloc[i - 1]["strike"])
            break
        if curr_val == 0:
            dn_strike = float(strike_delta.iloc[i]["strike"])
            break
        if prev_val * curr_val < 0:
            x0 = float(strike_delta.iloc[i - 1]["strike"])
            x1 = float(strike_delta.iloc[i]["strike"])
            if curr_val != prev_val:
                dn_strike = x0 + (0 - prev_val) * (x1 - x0) / (curr_val - prev_val)
            else:
                dn_strike = x0
            break
    if dn_strike is None:
        min_idx = strike_delta["cumulative_delta"].abs().idxmin()
        dn_strike = float(strike_delta.loc[min_idx, "strike"])

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
    et_tz = ZoneInfo("America/New_York")
    feeds = {
        "Reuters Business": "http://feeds.reuters.com/reuters/businessNews",
        "Reuters World": "http://feeds.reuters.com/reuters/worldNews",
        "Reuters Markets": "http://feeds.reuters.com/news/wealth",
        "MarketWatch Top Stories": "http://feeds.marketwatch.com/marketwatch/topstories",
        "MarketWatch Market Pulse": "http://feeds.marketwatch.com/marketwatch/marketpulse/",
        "CNBC Top News": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "CNBC Finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "WSJ Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    }

    all_news = []
    seen = set()

    for source_name, feed_url in feeds.items():
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:12]:
                try:
                    headline = entry.get("title", "No title").strip()
                    link = entry.get("link", "#")
                    dedupe_key = (source_name, headline)
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)

                    published_struct = entry.get("published_parsed") or entry.get("updated_parsed")
                    published_dt = None
                    if published_struct:
                        try:
                            published_dt = datetime(
                                published_struct.tm_year,
                                published_struct.tm_mon,
                                published_struct.tm_mday,
                                published_struct.tm_hour,
                                published_struct.tm_min,
                                published_struct.tm_sec,
                                tzinfo=timezone.utc,
                            ).astimezone(et_tz)
                        except Exception:
                            published_dt = None

                    pub_date = (
                        published_dt.strftime("%a, %b %d %Y %I:%M %p ET")
                        if published_dt
                        else "Time unavailable (ET)"
                    )
                    all_news.append(
                        {
                            "headline": headline,
                            "source": source_name,
                            "link": link,
                            "published": pub_date,
                            "published_ts": int(published_dt.timestamp()) if published_dt else 0,
                            "summary": entry.get("summary", "")[:200],
                        }
                    )
                except Exception:
                    continue

        except Exception:
            continue

    all_news.sort(key=lambda x: x.get("published_ts", 0), reverse=True)
    return all_news[:60]


def _earnings_time_bucket(value):
    if value is None:
        return "Time TBA"
    s = str(value).strip().lower()
    if s in {"bmo", "before", "beforeopen", "before open"}:
        return "Before Open"
    if s in {"amc", "after", "afterclose", "after close"}:
        return "After Close"
    return "Time TBA"


def _extract_earnings_whispers_calendar():
    # Best-effort scraper; may return [] if markup changes or blocked.
    url = "https://www.earningswhispers.com/calendar"
    rows = []
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code != 200:
            return rows
        soup = BeautifulSoup(res.text, "html.parser")
        # Common fallback: any ticker-like anchors/cards.
        for node in soup.select("[data-symbol], a[href*='/stocks/']")[:120]:
            sym = (node.get("data-symbol") or node.get_text(" ", strip=True) or "").upper()
            sym = re.sub(r"[^A-Z.]", "", sym)
            if not (1 <= len(sym) <= 6):
                continue
            rows.append(
                {
                    "symbol": sym,
                    "date": datetime.now().date().isoformat(),
                    "time": "Time TBA",
                    "eps_estimate": None,
                    "eps_actual": None,
                    "revenue_estimate": None,
                    "revenue_actual": None,
                    "source": "EarningsWhispers",
                }
            )
    except Exception:
        return []
    dedup = {(r["symbol"], r["date"], r["time"]): r for r in rows}
    return list(dedup.values())[:50]


def _extract_earnings_hub_calendar():
    # Best-effort scraper; may return [] if markup changes or blocked.
    candidates = [
        "https://www.earningshub.com/calendar",
        "https://earningshub.com/calendar",
    ]
    rows = []
    for url in candidates:
        try:
            res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            for node in soup.select("[data-symbol], a[href*='ticker'], a[href*='/stock/']")[:120]:
                sym = (node.get("data-symbol") or node.get_text(" ", strip=True) or "").upper()
                sym = re.sub(r"[^A-Z.]", "", sym)
                if not (1 <= len(sym) <= 6):
                    continue
                rows.append(
                    {
                        "symbol": sym,
                        "date": datetime.now().date().isoformat(),
                        "time": "Time TBA",
                        "eps_estimate": None,
                        "eps_actual": None,
                        "revenue_estimate": None,
                        "revenue_actual": None,
                        "source": "EarningsHub",
                    }
                )
            if rows:
                break
        except Exception:
            continue
    dedup = {(r["symbol"], r["date"], r["time"]): r for r in rows}
    return list(dedup.values())[:50]


@st.cache_data(ttl=600)
def get_earnings_calendar_multi(finnhub_key, days=5, major_only=True):
    et = ZoneInfo("America/New_York")
    start_date = datetime.now(et).date()
    end_date = (datetime.now(et) + pd.Timedelta(days=days)).date()
    rows = []

    # Source 1: Finnhub earnings calendar
    try:
        client = finnhub.Client(api_key=finnhub_key)
        cal = client.earnings_calendar(_from=str(start_date), to=str(end_date), symbol="", international=False)
        for e in cal.get("earningsCalendar", []):
            sym = (e.get("symbol") or "").upper().strip()
            if not sym:
                continue
            rows.append(
                {
                    "symbol": sym,
                    "date": str(e.get("date", ""))[:10],
                    "time": _earnings_time_bucket(e.get("hour") or e.get("time")),
                    "eps_estimate": e.get("epsEstimate"),
                    "eps_actual": e.get("epsActual"),
                    "revenue_estimate": e.get("revenueEstimate"),
                    "revenue_actual": e.get("revenueActual"),
                    "source": "Finnhub",
                }
            )
    except Exception:
        pass

    # Source 2: EarningsWhispers (best effort)
    try:
        rows.extend(_extract_earnings_whispers_calendar())
    except Exception:
        pass

    # Source 3: EarningsHub (best effort)
    try:
        rows.extend(_extract_earnings_hub_calendar())
    except Exception:
        pass

    if not rows:
        return pd.DataFrame(columns=[
            "symbol", "date", "time", "eps_estimate", "eps_actual", "revenue_estimate", "revenue_actual", "source"
        ])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date", "symbol"])
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
    df["time"] = df["time"].fillna("Time TBA")
    if major_only:
        df = df[df["symbol"].isin(MAJOR_INDEX_IMPACT_TICKERS)].copy()
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "date",
                    "time",
                    "eps_estimate",
                    "eps_actual",
                    "revenue_estimate",
                    "revenue_actual",
                    "source",
                ]
            )

    # Prefer Finnhub when duplicates exist.
    source_rank = {"Finnhub": 0, "EarningsWhispers": 1, "EarningsHub": 2}
    df["source_rank"] = df["source"].map(lambda s: source_rank.get(s, 99))
    df = (
        df.sort_values(["date", "symbol", "source_rank"])
        .drop_duplicates(subset=["date", "symbol"], keep="first")
        .sort_values(["date", "time", "symbol"])
    )
    df = df.drop(columns=["source_rank"], errors="ignore")
    return df.reset_index(drop=True)


@st.cache_data(ttl=600)
def get_earnings_detail(symbol, finnhub_key):
    detail = {
        "symbol": symbol.upper(),
        "name": symbol.upper(),
        "price": None,
        "change": None,
        "change_pct": None,
        "market_cap": None,
        "industry": None,
        "next_earnings": None,
        "history": [],
    }
    sym = detail["symbol"]

    try:
        client = finnhub.Client(api_key=finnhub_key)
        q = client.quote(sym)
        detail["price"] = q.get("c")
        detail["change"] = q.get("d")
        detail["change_pct"] = q.get("dp")
    except Exception:
        pass

    try:
        client = finnhub.Client(api_key=finnhub_key)
        p = client.company_profile2(symbol=sym)
        detail["name"] = p.get("name") or detail["name"]
        detail["market_cap"] = p.get("marketCapitalization")
        detail["industry"] = p.get("finnhubIndustry")
    except Exception:
        pass

    try:
        t = yf.Ticker(sym)
        ed = t.get_earnings_dates(limit=6)
        if ed is not None and not ed.empty:
            idx = ed.index
            if len(idx) > 0:
                next_dt = idx[0]
                try:
                    next_dt = next_dt.tz_convert("America/New_York") if next_dt.tzinfo else next_dt
                except Exception:
                    pass
                detail["next_earnings"] = str(next_dt)
            hist_rows = []
            for _, r in ed.head(6).reset_index().iterrows():
                hist_rows.append(
                    {
                        "date": str(r.iloc[0])[:19],
                        "eps_estimate": r.get("EPS Estimate"),
                        "eps_reported": r.get("Reported EPS"),
                        "surprise_pct": r.get("Surprise(%)"),
                    }
                )
            detail["history"] = hist_rows
    except Exception:
        pass

    return detail


@st.cache_data(ttl=14400)
def process_expiration(df_raw, target_exp, qqq_price, ratio, nq_now):
    df = df_raw[df_raw["expiration"] == target_exp].copy()
    df = df[df["open_interest"] > 0].copy()
    df = df[df["iv"] > 0].copy()
    # Use a wider strike window, then filter by liquidity to avoid noisy tails.
    df = df[(df["strike"] > qqq_price * 0.90) & (df["strike"] < qqq_price * 1.10)].copy()
    df["volume"] = df["volume"].fillna(0)
    df["liquidity"] = df["open_interest"] + (0.35 * df["volume"])
    liq_cut = df["liquidity"].quantile(0.25) if len(df) > 8 else 0
    df = df[df["liquidity"] >= liq_cut].copy()

    if len(df) == 0:
        return None

    dn_strike, strike_delta, df = calculate_delta_neutral(df, qqq_price)
    dn_nq = dn_strike * ratio

    total_call_delta = df[df["type"] == "call"]["delta_exposure"].sum()
    total_put_delta = df[df["type"] == "put"]["delta_exposure"].sum()
    net_delta = total_call_delta + total_put_delta

    atm_strike = df.iloc[(df["strike"] - qqq_price).abs().argsort()[:1]]["strike"].values[0]
    atm_opts = df[(df["strike"] >= qqq_price * 0.995) & (df["strike"] <= qqq_price * 1.005)].copy()
    if atm_opts.empty:
        atm_opts = df[df["strike"] == atm_strike]
    atm_call = atm_opts[atm_opts["type"] == "call"]
    atm_put = atm_opts[atm_opts["type"] == "put"]

    if len(atm_call) > 0 and len(atm_put) > 0:
        call_mid = ((atm_call["bid"] + atm_call["ask"]) / 2).replace([float("inf"), -float("inf")], pd.NA).dropna().median()
        put_mid = ((atm_put["bid"] + atm_put["ask"]) / 2).replace([float("inf"), -float("inf")], pd.NA).dropna().median()
        call_mid = float(call_mid) if pd.notna(call_mid) else 0.0
        put_mid = float(put_mid) if pd.notna(put_mid) else 0.0
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

    calls = df[df["type"] == "call"].copy()
    puts = df[df["type"] == "put"].copy()
    call_strikes = (
        calls.groupby("strike", as_index=False)
        .agg(GEX=("GEX", "sum"), OI=("open_interest", "sum"), VOL=("volume", "sum"))
    )
    put_strikes = (
        puts.groupby("strike", as_index=False)
        .agg(GEX=("GEX", "sum"), OI=("open_interest", "sum"), VOL=("volume", "sum"))
    )
    call_strikes["score"] = call_strikes["GEX"].abs() * (1 + call_strikes["OI"].map(lambda v: math.log1p(max(v, 0))))
    put_strikes["score"] = put_strikes["GEX"].abs() * (1 + put_strikes["OI"].map(lambda v: math.log1p(max(v, 0))))
    calls = calls.sort_values("GEX", ascending=False)
    puts = puts.sort_values("GEX", ascending=True)

    calls_above = call_strikes[call_strikes["strike"] > qqq_price].sort_values("score", ascending=False)
    if len(calls_above) > 0:
        p_wall_strike = calls_above.iloc[0]["strike"]
    else:
        p_wall_strike = call_strikes.sort_values("score", ascending=False).iloc[0]["strike"] if len(call_strikes) > 0 else qqq_price * 1.01

    puts_below = put_strikes[put_strikes["strike"] < qqq_price].sort_values("score", ascending=False)
    if len(puts_below) > 0:
        p_floor_strike = puts_below.iloc[0]["strike"]
    else:
        p_floor_strike = put_strikes.sort_values("score", ascending=False).iloc[0]["strike"] if len(put_strikes) > 0 else qqq_price * 0.99

    if p_floor_strike >= p_wall_strike:
        p_floor_strike = min(puts["strike"]) if len(puts) > 0 else qqq_price * 0.99
        p_wall_strike = max(calls["strike"]) if len(calls) > 0 else qqq_price * 1.01

    s_wall_strike = p_wall_strike
    wall_candidates = call_strikes[call_strikes["strike"] > p_wall_strike].sort_values("score", ascending=False)
    if not wall_candidates.empty:
        s_wall_strike = wall_candidates.iloc[0]["strike"]

    s_floor_strike = p_floor_strike
    floor_candidates = put_strikes[put_strikes["strike"] < p_floor_strike].sort_values("score", ascending=False)
    if not floor_candidates.empty:
        s_floor_strike = floor_candidates.iloc[0]["strike"]

    if s_floor_strike >= s_wall_strike:
        s_floor_strike = p_floor_strike * 0.995
        s_wall_strike = p_wall_strike * 1.005

    gex_by_strike = df.groupby("strike", as_index=False)["GEX"].sum().sort_values("strike")
    g_flip_strike = None
    for i in range(1, len(gex_by_strike)):
        prev_val = float(gex_by_strike.iloc[i - 1]["GEX"])
        curr_val = float(gex_by_strike.iloc[i]["GEX"])
        if prev_val == 0:
            g_flip_strike = float(gex_by_strike.iloc[i - 1]["strike"])
            break
        if curr_val == 0:
            g_flip_strike = float(gex_by_strike.iloc[i]["strike"])
            break
        if prev_val * curr_val < 0:
            x0 = float(gex_by_strike.iloc[i - 1]["strike"])
            x1 = float(gex_by_strike.iloc[i]["strike"])
            if curr_val != prev_val:
                g_flip_strike = x0 + (0 - prev_val) * (x1 - x0) / (curr_val - prev_val)
            else:
                g_flip_strike = x0
            break
    if g_flip_strike is None:
        min_idx = gex_by_strike["GEX"].abs().idxmin()
        g_flip_strike = float(gex_by_strike.loc[min_idx, "strike"])

    # Confidence scoring for actionable levels based on nearby liquidity and gamma strength.
    strike_liq = df.groupby("strike")["liquidity"].sum()
    strike_oi = df.groupby("strike")["open_interest"].sum()
    max_liq = max(1.0, float(strike_liq.max())) if not strike_liq.empty else 1.0
    max_oi = max(1.0, float(strike_oi.max())) if not strike_oi.empty else 1.0
    max_abs_gex = max(1.0, float(gex_by_strike["GEX"].abs().max())) if not gex_by_strike.empty else 1.0

    def _nearest_idx(values, x):
        if len(values) == 0:
            return None
        return min(range(len(values)), key=lambda i: abs(values[i] - x))

    gex_strikes = gex_by_strike["strike"].tolist()
    gex_values = gex_by_strike["GEX"].tolist()
    liq_strikes = strike_liq.index.tolist()
    oi_strikes = strike_oi.index.tolist()

    def _level_confidence(strike_val):
        g_i = _nearest_idx(gex_strikes, strike_val)
        l_i = _nearest_idx(liq_strikes, strike_val)
        o_i = _nearest_idx(oi_strikes, strike_val)
        if g_i is None or l_i is None or o_i is None:
            return {"score": 0, "label": "Low"}

        gex_strength = abs(float(gex_values[g_i])) / max_abs_gex
        liq_strength = float(strike_liq.iloc[l_i]) / max_liq
        oi_strength = float(strike_oi.iloc[o_i]) / max_oi

        score = int(round(100 * ((0.45 * liq_strength) + (0.30 * gex_strength) + (0.25 * oi_strength))))
        score = max(0, min(100, score))
        label = "High" if score >= 70 else "Medium" if score >= 45 else "Low"
        return {"score": score, "label": label}

    level_confidence = {
        "Delta Neutral": _level_confidence(dn_strike),
        "Primary Wall": _level_confidence(p_wall_strike),
        "Primary Floor": _level_confidence(p_floor_strike),
        "Secondary Wall": _level_confidence(s_wall_strike),
        "Secondary Floor": _level_confidence(s_floor_strike),
        "Gamma Flip": _level_confidence(g_flip_strike),
    }
    level_confidence["Target Resistance"] = dict(level_confidence["Primary Wall"])
    level_confidence["Target Support"] = dict(level_confidence["Primary Floor"])
    level_confidence["Upper 0.50σ"] = {"score": 40, "label": "Low"}
    level_confidence["Upper 0.25σ"] = {"score": 45, "label": "Medium"}
    level_confidence["Lower 0.25σ"] = {"score": 45, "label": "Medium"}
    level_confidence["Lower 0.50σ"] = {"score": 40, "label": "Low"}

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
        "level_confidence": level_confidence,
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
