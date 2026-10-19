"""Pure gamma / delta exposure math for the dashboard.

Nothing in here touches Streamlit or the network, so it can be unit tested
directly with synthetic option chains.

Conventions
-----------
* Dollar gamma exposure (GEX) of one contract, per 1% move of the underlying:

      GEX = gamma * open_interest * 100 * spot**2 * 0.01 * sign

  where ``sign`` is +1 for calls and -1 for puts. That sign is the standard
  "dealers are long calls and short puts" simplification. It is an assumption
  about who holds the other side of the open interest, not an observed fact.

* Gamma Flip: the underlying price at which the TOTAL dealer gamma across the
  chain changes sign. It is found by repricing every contract's gamma with
  Black Scholes at a grid of hypothetical spot prices (keeping each contract's
  own IV and time to expiry) and locating the zero crossing nearest spot.

* Delta Neutral: the underlying price at which the open interest weighted
  delta of all calls exactly offsets that of all puts. Again found by
  repricing deltas across a spot grid. Net open interest delta rises
  monotonically with spot, so there is at most one crossing.
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
CONTRACT_MULTIPLIER = 100.0
MINUTES_PER_YEAR = 365.0 * 24.0 * 60.0
DEFAULT_RATE = 0.04
DEFAULT_DIVIDEND_YIELD = 0.0
# Floor so contracts in their final minutes do not produce infinite gamma.
MIN_MINUTES_TO_EXPIRY = 5.0

# Roots whose standard monthly (third Friday) contracts settle at the open
# (AM settlement). Their P / W variants (NDXP, SPXW) settle at the close.
AM_SETTLED_ROOTS = {"NDX", "SPX", "RUT", "XSP_AM"}

_SQRT_2PI = np.sqrt(2.0 * np.pi)


# ---------------------------------------------------------------------------
# Time handling (everything in US Eastern, never server local time)
# ---------------------------------------------------------------------------

def now_et() -> datetime:
    return datetime.now(ET)


def today_et() -> date:
    return now_et().date()


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        ts = pd.Timestamp(value)
        return None if pd.isna(ts) else ts.date()
    except Exception:
        return None


def is_third_friday(d: date) -> bool:
    return d.weekday() == 4 and 15 <= d.day <= 21


def settlement_time_et(exp_date, root: str = "", settlement: str = "") -> datetime | None:
    """When an option stops carrying gamma, in ET.

    Equity / ETF options (QQQ) and PM settled index options (NDXP, SPXW)
    expire at the 16:00 ET close. Standard AM settled index monthlies stop
    trading the day before but settle on the opening print; treating them as
    expiring at 09:30 on expiration day is the right gamma horizon.
    """
    d = _as_date(exp_date)
    if d is None:
        return None
    settle = str(settlement or "").strip().upper()
    root_u = str(root or "").strip().upper()
    am = settle in {"A", "AM"} or (settle == "" and root_u in AM_SETTLED_ROOTS and is_third_friday(d))
    t = dt_time(9, 30) if am else dt_time(16, 0)
    return datetime.combine(d, t, tzinfo=ET)


def time_to_expiry_years(df: pd.DataFrame, now: datetime | None = None, min_minutes: float = MIN_MINUTES_TO_EXPIRY) -> np.ndarray:
    """Years to expiry for each row. Already expired rows get 0.0."""
    if df is None or len(df) == 0:
        return np.zeros(0)
    now = now or now_et()
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    exp = df["expiration"] if "expiration" in df.columns else pd.Series([None] * len(df), index=df.index)
    roots = df["root"] if "root" in df.columns else pd.Series([""] * len(df), index=df.index)
    settles = df["settlement"] if "settlement" in df.columns else pd.Series([""] * len(df), index=df.index)

    cache: dict = {}
    out = np.zeros(len(df), dtype=float)
    for i, (e, r, s) in enumerate(zip(exp.tolist(), roots.fillna("").tolist(), settles.fillna("").tolist())):
        key = (_as_date(e), str(r).upper(), str(s).upper())
        if key not in cache:
            settle_dt = settlement_time_et(key[0], key[1], key[2]) if key[0] else None
            if settle_dt is None:
                cache[key] = 0.0
            else:
                minutes = (settle_dt - now).total_seconds() / 60.0
                cache[key] = 0.0 if minutes <= 0 else max(minutes, min_minutes) / MINUTES_PER_YEAR
        out[i] = cache[key]
    return out


def dte_days(exp_date, today: date | None = None) -> int:
    d = _as_date(exp_date)
    if d is None:
        return 0
    return max(0, (d - (today or today_et())).days)


# ---------------------------------------------------------------------------
# Black Scholes pieces (vectorized, no scipy dependency)
# ---------------------------------------------------------------------------

def _norm_cdf(x):
    # Abramowitz & Stegun 7.1.26 via erf, max abs error ~1.5e-7.
    x = np.asarray(x, dtype=float)
    z = np.abs(x) / np.sqrt(2.0)
    t = 1.0 / (1.0 + 0.3275911 * z)
    poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
    erf = 1.0 - poly * np.exp(-z * z)
    return 0.5 * (1.0 + np.sign(x) * erf)


def _norm_pdf(x):
    x = np.asarray(x, dtype=float)
    return np.exp(-0.5 * x * x) / _SQRT_2PI


def _d1(S, K, T, sigma, r, q):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (np.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * np.sqrt(T))


def bs_gamma(S, K, T, sigma, r=DEFAULT_RATE, q=DEFAULT_DIVIDEND_YIELD):
    S = np.asarray(S, dtype=float)
    K = np.asarray(K, dtype=float)
    T = np.asarray(T, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    valid = (S > 0) & (K > 0) & (T > 0) & (sigma > 0)
    d1 = _d1(np.where(valid, S, 1.0), np.where(valid, K, 1.0), np.where(valid, T, 1.0), np.where(valid, sigma, 1.0), r, q)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = np.exp(-q * T) * _norm_pdf(d1) / (S * sigma * np.sqrt(T))
    return np.where(valid, np.nan_to_num(g, nan=0.0, posinf=0.0, neginf=0.0), 0.0)


def bs_delta(S, K, T, sigma, is_call, r=DEFAULT_RATE, q=DEFAULT_DIVIDEND_YIELD):
    S = np.asarray(S, dtype=float)
    K = np.asarray(K, dtype=float)
    T = np.asarray(T, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    is_call = np.asarray(is_call, dtype=bool)
    valid = (S > 0) & (K > 0) & (T > 0) & (sigma > 0)
    d1 = _d1(np.where(valid, S, 1.0), np.where(valid, K, 1.0), np.where(valid, T, 1.0), np.where(valid, sigma, 1.0), r, q)
    disc = np.exp(-q * np.where(valid, T, 0.0))
    nd1 = _norm_cdf(d1)
    delta = np.where(is_call, disc * nd1, disc * (nd1 - 1.0))
    # Expired / invalid: intrinsic delta.
    intrinsic = np.where(is_call, (S > K).astype(float), -(S < K).astype(float))
    return np.where(valid, delta, intrinsic)


# ---------------------------------------------------------------------------
# Chain preparation
# ---------------------------------------------------------------------------

def is_call_mask(df: pd.DataFrame) -> np.ndarray:
    return df["type"].astype(str).str.lower().eq("call").to_numpy()


def fill_missing_iv(df: pd.DataFrame) -> pd.DataFrame:
    """Impute IV for rows where the feed sent 0 or nothing.

    Interpolates across strikes inside the same expiration and option type,
    falls back to the other option type of the same expiration, then to the
    chain median. Rows are kept rather than dropped, so their open interest
    still counts toward exposure.
    """
    out = df.copy()
    if out.empty:
        out["iv_imputed"] = False
        return out
    iv = pd.to_numeric(out.get("iv", 0.0), errors="coerce").fillna(0.0)
    iv = iv.where((iv > 0.01) & (iv < 5.0), np.nan)
    out["iv"] = iv
    out["iv_imputed"] = iv.isna()
    if not out["iv_imputed"].any():
        return out

    def _interp(group, key_cols):
        g = group.sort_values("strike")
        known = g[g["iv"].notna()]
        if len(known) == 0:
            return g["iv"]
        if len(known) == 1:
            return g["iv"].fillna(float(known["iv"].iloc[0]))
        filled = np.interp(g["strike"].to_numpy(dtype=float), known["strike"].to_numpy(dtype=float), known["iv"].to_numpy(dtype=float))
        return pd.Series(np.where(g["iv"].isna(), filled, g["iv"]), index=g.index)

    exp_key = out["expiration"].astype(str)
    type_key = out["type"].astype(str)
    for _, idx in out.groupby([exp_key, type_key]).groups.items():
        out.loc[idx, "iv"] = _interp(out.loc[idx], None)
    for _, idx in out.groupby(exp_key).groups.items():
        sub = out.loc[idx]
        if sub["iv"].isna().any() and sub["iv"].notna().any():
            out.loc[idx, "iv"] = _interp(sub, None)
    median_iv = float(out["iv"].median()) if out["iv"].notna().any() else 0.20
    out["iv"] = out["iv"].fillna(median_iv)
    return out


def prepare_chain(df: pd.DataFrame, spot: float, now: datetime | None = None,
                  r: float = DEFAULT_RATE, q: float = DEFAULT_DIVIDEND_YIELD) -> pd.DataFrame:
    """Add T, imputed IV, gamma at current spot and dollar GEX columns.

    * ``gamma_feed`` keeps whatever the data source sent.
    * ``gamma`` is recomputed at the current (live) spot so per strike bars
      and the gamma profile agree, and so a 15 minute delayed chain is not
      using greeks computed at a stale underlying price.
    * Expired contracts (T == 0) are removed.
    """
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=list(getattr(df, "columns", [])) + ["T", "GEX"])
    out = df.copy()
    for col in ("open_interest", "volume", "strike"):
        out[col] = pd.to_numeric(out.get(col, 0.0), errors="coerce").fillna(0.0)
    out["T"] = time_to_expiry_years(out, now=now)
    out = out[out["T"] > 0].copy()
    if out.empty:
        out["GEX"] = []
        return out
    out = fill_missing_iv(out)
    if "gamma" in out.columns:
        out["gamma_feed"] = pd.to_numeric(out["gamma"], errors="coerce").fillna(0.0)
    if "delta" in out.columns:
        out["delta_feed"] = pd.to_numeric(out["delta"], errors="coerce").fillna(0.0)
    calls = is_call_mask(out)
    K = out["strike"].to_numpy(dtype=float)
    T = out["T"].to_numpy(dtype=float)
    sig = out["iv"].to_numpy(dtype=float)
    out["gamma"] = bs_gamma(spot, K, T, sig, r, q)
    out["delta"] = bs_delta(spot, K, T, sig, calls, r, q)
    out["GEX"] = signed_gex(out["gamma"].to_numpy(), out["open_interest"].to_numpy(), spot, calls)
    out["GEX_VOL"] = signed_gex(out["gamma"].to_numpy(), out["volume"].to_numpy(), spot, calls)
    return out


def signed_gex(gamma, quantity, spot, is_call, multiplier: float = CONTRACT_MULTIPLIER):
    """Dollar gamma per 1% move, signed by the dealer convention."""
    sign = np.where(np.asarray(is_call, dtype=bool), 1.0, -1.0)
    return np.asarray(gamma, dtype=float) * np.asarray(quantity, dtype=float) * multiplier * (float(spot) ** 2) * 0.01 * sign


def rescale_chain(df: pd.DataFrame, k: float, label: str) -> pd.DataFrame:
    """Express a chain on one underlying in units of another (S_target = k * S_source).

    Used to fold NDX options into QQQ strike space. Dollar exposure is
    preserved exactly: each source contract becomes 1/k "target unit"
    contracts, strikes and prices scale by k, BS gamma scales by 1/k
    (gamma is homogeneous of degree -1), delta and IV are unchanged.
    """
    if df is None or len(df) == 0 or not k or k <= 0:
        return df
    out = df.copy()
    for col in ("strike", "bid", "ask", "last", "mark"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0) * k
    for col in ("open_interest", "volume"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0) / k
    if "gamma" in out.columns:
        out["gamma"] = pd.to_numeric(out["gamma"], errors="coerce").fillna(0.0) / k
    out["underlying"] = label
    return out


# ---------------------------------------------------------------------------
# Profiles across hypothetical spot prices
# ---------------------------------------------------------------------------

def build_spot_grid(spot: float, pct: float = 0.08, points: int = 321) -> np.ndarray:
    spot = float(spot)
    return np.linspace(spot * (1.0 - pct), spot * (1.0 + pct), int(points))


def _profile(df: pd.DataFrame, grid: np.ndarray, kind: str, weight_col: str,
             r: float, q: float, chunk: int = 4000) -> np.ndarray:
    grid = np.asarray(grid, dtype=float)
    total = np.zeros(len(grid))
    if df is None or len(df) == 0:
        return total
    K = df["strike"].to_numpy(dtype=float)
    T = df["T"].to_numpy(dtype=float)
    sig = df["iv"].to_numpy(dtype=float)
    w = pd.to_numeric(df[weight_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    calls = is_call_mask(df)
    keep = (w > 0) & (T > 0) & (sig > 0) & (K > 0)
    K, T, sig, w, calls = K[keep], T[keep], sig[keep], w[keep], calls[keep]
    S = grid[None, :]
    for start in range(0, len(K), chunk):
        sl = slice(start, start + chunk)
        Kc, Tc, sc, wc, cc = K[sl, None], T[sl, None], sig[sl, None], w[sl, None], calls[sl, None]
        if kind == "gamma":
            g = bs_gamma(S, Kc, Tc, sc, r, q)
            sign = np.where(cc, 1.0, -1.0)
            total += (g * wc * CONTRACT_MULTIPLIER * sign).sum(axis=0) * (grid ** 2) * 0.01
        else:
            d = bs_delta(S, Kc, Tc, sc, np.broadcast_to(cc, (len(Kc), len(grid))), r, q)
            total += (d * wc * CONTRACT_MULTIPLIER).sum(axis=0)
    return total


def gamma_profile(df, grid, weight_col="open_interest", r=DEFAULT_RATE, q=DEFAULT_DIVIDEND_YIELD):
    """Total signed dealer GEX ($ per 1% move) at each hypothetical spot."""
    return _profile(df, grid, "gamma", weight_col, r, q)


def net_delta_profile(df, grid, weight_col="open_interest", r=DEFAULT_RATE, q=DEFAULT_DIVIDEND_YIELD):
    """Open interest weighted call delta plus put delta (shares) at each spot."""
    return _profile(df, grid, "delta", weight_col, r, q)


def zero_crossings(grid, values) -> list[float]:
    grid = np.asarray(grid, dtype=float)
    v = np.asarray(values, dtype=float)
    out = []
    for i in range(1, len(v)):
        a, b = v[i - 1], v[i]
        if a == 0.0:
            out.append(float(grid[i - 1]))
        elif a * b < 0:
            out.append(float(grid[i - 1] + (0.0 - a) * (grid[i] - grid[i - 1]) / (b - a)))
    if len(v) and v[-1] == 0.0:
        out.append(float(grid[-1]))
    return sorted(set(out))


def nearest_zero_crossing(grid, values, ref: float):
    crossings = zero_crossings(grid, values)
    if not crossings:
        return None
    return min(crossings, key=lambda x: abs(x - float(ref)))


def solve_level(df, spot, kind: str, weight_col="open_interest", pcts=(0.08, 0.20),
                points=321, r=DEFAULT_RATE, q=DEFAULT_DIVIDEND_YIELD) -> dict:
    """Find the gamma flip ("gamma") or delta neutral ("delta") level.

    Searches a +/-8% grid first, then +/-20%. If no crossing exists in the
    wider grid either, returns the grid point with the smallest absolute
    value and ``in_range=False`` so the UI can say so honestly.
    """
    fn = gamma_profile if kind == "gamma" else net_delta_profile
    last_grid, last_vals = None, None
    for pct in pcts:
        grid = build_spot_grid(spot, pct, points)
        vals = fn(df, grid, weight_col, r, q)
        last_grid, last_vals = grid, vals
        x = nearest_zero_crossing(grid, vals, spot)
        if x is not None:
            return {"level": float(x), "in_range": True, "search_pct": pct, "grid": grid, "values": vals}
    if last_grid is None or len(last_grid) == 0:
        return {"level": float(spot), "in_range": False, "search_pct": None, "grid": np.array([]), "values": np.array([])}
    idx = int(np.argmin(np.abs(last_vals)))
    return {"level": float(last_grid[idx]), "in_range": False, "search_pct": pcts[-1], "grid": last_grid, "values": last_vals}
