import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import streamlit as st

from nq_precision.auth_schwab import format_schwab_auth_status, get_schwab_access_token
from nq_precision.config import get_secret


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
QUARTERLY_FUTURES_ROOTS = {
    "NQ=F": "/NQ",
    "ES=F": "/ES",
    "YM=F": "/YM",
    "RTY=F": "/RTY",
}


def _third_friday(year, month):
    first = datetime(year, month, 1)
    first_friday = first + timedelta(days=(4 - first.weekday()) % 7)
    return first_friday + timedelta(days=14)


def active_quarterly_contract(now=None, roll_days=8):
    """Return the active quarterly contract and the date its roll window began."""
    now = now or datetime.now(ZoneInfo("America/New_York"))
    quarter_months = (3, 6, 9, 12)
    year = now.year
    month = next((value for value in quarter_months if value >= now.month), 3)
    if month < now.month:
        year += 1

    roll_start = (_third_friday(year, month) - timedelta(days=roll_days)).date()
    if now.date() >= roll_start:
        index = quarter_months.index(month)
        if index == len(quarter_months) - 1:
            year += 1
            month = quarter_months[0]
        else:
            month = quarter_months[index + 1]

    return year, month, roll_start


def set_quote_meta(symbol, source, timestamp_ms=None, session_state=None):
    state = session_state if session_state is not None else st.session_state
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    state[f"quote_meta::{symbol}"] = {
        "source": source,
        "timestamp_ms": int(timestamp_ms),
    }


def next_quarterly_contracts(count=3, now=None):
    quarter_months = (3, 6, 9, 12)
    year, month, _roll_start = active_quarterly_contract(now=now)
    contracts = [(year, month)]
    while len(contracts) < count:
        index = quarter_months.index(month)
        if index == len(quarter_months) - 1:
            year += 1
            month = quarter_months[0]
        else:
            month = quarter_months[index + 1]
        contracts.append((year, month))
    return contracts


def expected_quarterly_symbol(futures_symbol="NQ=F", now=None):
    root = QUARTERLY_FUTURES_ROOTS.get(futures_symbol, "/NQ")
    year, month, roll_start = active_quarterly_contract(now=now)
    symbol = f"{root}{FUTURES_MONTH_CODES[month]}{str(year)[-2:]}"
    return symbol, roll_start.isoformat()


def map_futures_symbol(futures_symbol, secret_getter=get_secret):
    overrides = {
        "NQ=F": secret_getter("SCHWAB_SYMBOL_NQ", ""),
        "ES=F": secret_getter("SCHWAB_SYMBOL_ES", ""),
        "YM=F": secret_getter("SCHWAB_SYMBOL_YM", ""),
        "RTY=F": secret_getter("SCHWAB_SYMBOL_RTY", ""),
        "DX=F": secret_getter("SCHWAB_SYMBOL_DX", ""),
        "GC=F": secret_getter("SCHWAB_SYMBOL_GC", ""),
        "CL=F": secret_getter("SCHWAB_SYMBOL_CL", ""),
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
        "CL=F": "/CL",
    }
    return defaults.get(futures_symbol, futures_symbol)


def candidate_schwab_symbols(futures_symbol, secret_getter=get_secret, now=None):
    mapped = map_futures_symbol(futures_symbol, secret_getter=secret_getter)
    if any(ch.isdigit() for ch in mapped):
        expected_root = QUARTERLY_FUTURES_ROOTS.get(futures_symbol)
        match = re.fullmatch(r"(/[A-Z]+)([HMUZ])(\d{2}|\d{4})", mapped.upper())
        if expected_root and match and match.group(1) == expected_root:
            expected_year, expected_month, _roll_start = active_quarterly_contract(now=now)
            configured_year = int(match.group(3))
            if configured_year < 100:
                configured_year += 2000
            configured_month = next(
                month for month in (3, 6, 9, 12) if FUTURES_MONTH_CODES[month] == match.group(2)
            )
            if (configured_year, configured_month) < (expected_year, expected_month):
                expected_code = FUTURES_MONTH_CODES[expected_month]
                expected_short = f"{expected_root}{expected_code}{str(expected_year)[-2:]}"
                expected_long = f"{expected_root}{expected_code}{expected_year}"
                return [expected_short, expected_long, mapped]
        return [mapped]
    candidates = [mapped]
    if not mapped.startswith("/"):
        return candidates

    dated_candidates = []
    for year, month in next_quarterly_contracts(count=4, now=now):
        month_code = FUTURES_MONTH_CODES[month]
        yy = str(year)[-2:]
        yyyy = str(year)
        dated_candidates.append(f"{mapped}{month_code}{yy}")
        dated_candidates.append(f"{mapped}{month_code}{yyyy}")

    # Prefer an explicit dated contract for quarterly index futures so the selected
    # source proves which expiry is live. Preserve generic-first behavior elsewhere.
    if futures_symbol in QUARTERLY_FUTURES_ROOTS:
        candidates = dated_candidates + candidates
    else:
        candidates.extend(dated_candidates)

    seen = set()
    deduped = []
    for sym in candidates:
        if sym in seen:
            continue
        seen.add(sym)
        deduped.append(sym)
    return deduped


def extract_quote_price(quote_obj):
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


def extract_quote_timestamp_ms(quote_obj):
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
            if value < 10**11:
                value *= 1000
            if value > 10**14:
                value //= 1000
            return value
        except Exception:
            continue
    return None


def validate_price_range(symbol, price):
    symbol_ranges = {
        "NQ=F": (10000, 50000),
        "ES=F": (1000, 10000),
        "YM=F": (10000, 100000),
        "RTY=F": (500, 5000),
        "DX=F": (50, 200),
        "GC=F": (1000, 5000),
        "CL=F": (20, 200),
    }
    min_p, max_p = symbol_ranges.get(symbol, (0.01, 1e9))
    return min_p <= price <= max_p


def validate_stale_quote(timestamp_ms, secret_getter=get_secret, now_ms=None):
    if not timestamp_ms:
        return True
    max_stale_sec = int(secret_getter("SCHWAB_MAX_STALE_SECONDS", 180))
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    return (now_ms - timestamp_ms) <= (max_stale_sec * 1000)


def validate_jump(symbol, price, session_state=None, secret_getter=get_secret):
    state = session_state if session_state is not None else st.session_state
    key = f"last_good_price::{symbol}"
    previous = state.get(key)
    if not previous:
        state[key] = price
        return True
    if previous <= 0:
        state[key] = price
        return True
    jump_pct = abs(price - previous) / previous * 100
    max_jump_pct = float(secret_getter("MAX_ONE_TICK_JUMP_PCT", 5.0))
    if jump_pct > max_jump_pct:
        return False
    state[key] = price
    return True


def get_schwab_quotes_with_status(
    symbols,
    access_token_getter=get_schwab_access_token,
    auth_status_formatter=format_schwab_auth_status,
    session_state=None,
    requests_session=requests,
):
    state = session_state if session_state is not None else st.session_state
    token = access_token_getter()
    if not token:
        return {}, auth_status_formatter("token_unavailable", session_state=state)
    try:
        response = requests_session.get(
            SCHWAB_QUOTES_URL,
            params={"symbols": ",".join(symbols), "fields": "quote"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if response.status_code == 401:
            state.pop("schwab_access_token", None)
            state.pop("schwab_access_expires_at", None)
            retry_token = access_token_getter(force_refresh=True)
            if not retry_token:
                return {}, f"auth_401_refresh_failed; {auth_status_formatter(session_state=state)}"
            response = requests_session.get(
                SCHWAB_QUOTES_URL,
                params={"symbols": ",".join(symbols), "fields": "quote"},
                headers={"Authorization": f"Bearer {retry_token}"},
                timeout=10,
            )
            if response.status_code == 401:
                return {}, "auth_401_after_refresh"
        if response.status_code != 200:
            return {}, f"http_{response.status_code}"
        payload = response.json()
        if not isinstance(payload, dict):
            return {}, "payload_invalid"
        if not payload:
            return {}, "empty_payload"
        return payload, "ok"
    except Exception:
        return {}, "request_exception"


def get_schwab_quotes(symbols, **kwargs):
    quotes, _status = get_schwab_quotes_with_status(symbols, **kwargs)
    return quotes


def get_schwab_futures_price(
    futures_symbol,
    secret_getter=get_secret,
    access_token_getter=get_schwab_access_token,
    auth_status_formatter=format_schwab_auth_status,
    session_state=None,
    requests_session=requests,
):
    state = session_state if session_state is not None else st.session_state
    candidates = candidate_schwab_symbols(futures_symbol, secret_getter=secret_getter)
    quotes, quote_status = get_schwab_quotes_with_status(
        candidates,
        access_token_getter=access_token_getter,
        auth_status_formatter=auth_status_formatter,
        session_state=state,
        requests_session=requests_session,
    )
    if not quotes:
        return None, f"Schwab unavailable ({quote_status})"

    lookup_keys = []
    for sym in candidates:
        lookup_keys.extend([sym, sym.lstrip("/")])
    lookup_keys.append(futures_symbol)

    rejects = {
        "missing_price": 0,
        "range": 0,
        "stale": 0,
        "jump": 0,
    }
    inspected_quote_keys = set()

    for key in lookup_keys:
        if key in quotes:
            inspected_quote_keys.add(key)
            price = extract_quote_price(quotes[key])
            ts = extract_quote_timestamp_ms(quotes[key])
            if not price:
                rejects["missing_price"] += 1
                continue
            if not validate_price_range(futures_symbol, price):
                rejects["range"] += 1
                continue
            if not validate_stale_quote(ts, secret_getter=secret_getter):
                rejects["stale"] += 1
                continue
            if not validate_jump(futures_symbol, price, session_state=state, secret_getter=secret_getter):
                rejects["jump"] += 1
                continue
            set_quote_meta(futures_symbol, f"Schwab ({key})", ts or int(time.time() * 1000), session_state=state)
            return price, f"Schwab ({key})"

    for quote_key, value in quotes.items():
        if quote_key in inspected_quote_keys:
            continue
        price = extract_quote_price(value)
        ts = extract_quote_timestamp_ms(value)
        if not price:
            rejects["missing_price"] += 1
            continue
        if not validate_price_range(futures_symbol, price):
            rejects["range"] += 1
            continue
        if not validate_stale_quote(ts, secret_getter=secret_getter):
            rejects["stale"] += 1
            continue
        if not validate_jump(futures_symbol, price, session_state=state, secret_getter=secret_getter):
            rejects["jump"] += 1
            continue
        set_quote_meta(
            futures_symbol,
            f"Schwab ({quote_key})",
            ts or int(time.time() * 1000),
            session_state=state,
        )
        return price, f"Schwab ({quote_key})"

    detail = (
        f"quote_rejects missing={rejects['missing_price']} "
        f"range={rejects['range']} stale={rejects['stale']} jump={rejects['jump']}"
    )
    return None, f"Schwab unavailable ({detail})"


def get_yahoo_chart_price(symbol, min_price=0, session_state=None, requests_session=requests):
    state = session_state if session_state is not None else st.session_state
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests_session.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            if price and price > min_price:
                set_quote_meta(symbol, "Yahoo Finance", session_state=state)
                return float(price)
    except Exception:
        pass
    return None


def schwab_cross_source_check(yahoo_symbol, schwab_price, secret_getter=get_secret, yahoo_price_getter=get_yahoo_chart_price):
    yahoo_price = yahoo_price_getter(yahoo_symbol, min_price=0)
    if not yahoo_price:
        return True, None, None, None
    allowed_dev_pct = float(secret_getter("MAX_CROSS_SOURCE_DEVIATION_PCT", 3.0))
    deviation = abs(schwab_price - yahoo_price) / yahoo_price * 100
    return deviation <= allowed_dev_pct, float(deviation), float(allowed_dev_pct), float(yahoo_price)


def schwab_cross_source_ok(yahoo_symbol, schwab_price, **kwargs):
    ok, _dev, _allowed, _yahoo = schwab_cross_source_check(yahoo_symbol, schwab_price, **kwargs)
    return ok
