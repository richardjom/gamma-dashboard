"""Daily level snapshots and a simple scorer for how NQ reacted at them.

The point is to measure accuracy instead of guessing it: save the levels the
dashboard produced each morning, then check later whether price respected
them (touched and reversed) or sliced through.

Storage is a plain CSV. On Hugging Face Spaces the local disk is wiped on
restart unless the Space has persistent storage (mounted at /data), so set
LEVEL_LOG_PATH=/data/level_snapshots.csv there, or download the log from the
UI periodically.
"""

from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pandas as pd

from nq_precision import gamma_math as gm

DEFAULT_LOG_PATH = os.path.join("data", "level_snapshots.csv")

LOG_COLUMNS = [
    "saved_at_et",
    "session_date",
    "tag",
    "view",
    "level_name",
    "level_nq",
    "nq_at_save",
    "ratio",
    "underlyings",
    "options_source",
    "flip_model",
]

# Levels worth scoring. Sigma bands and targets are derived from the others.
SCORED_LEVELS = (
    "Gamma Flip",
    "Delta Neutral",
    "Primary Wall",
    "Primary Floor",
    "Secondary Wall",
    "Secondary Floor",
)


def log_path(configured: str | None = None) -> str:
    return configured or os.environ.get("LEVEL_LOG_PATH") or DEFAULT_LOG_PATH


def snapshot_rows(data: dict, view: str, nq_now: float, ratio: float, tag: str = "auto",
                  now: datetime | None = None) -> list[dict]:
    if not data:
        return []
    now = now or gm.now_et()
    meta = data.get("data_meta", {}) or {}
    rows = []
    for name, value, *_ in data.get("results", []) or []:
        if name not in SCORED_LEVELS:
            continue
        try:
            level = float(value)
        except Exception:
            continue
        if not np.isfinite(level):
            continue
        rows.append(
            {
                "saved_at_et": now.isoformat(timespec="seconds"),
                "session_date": now.date().isoformat(),
                "tag": tag,
                "view": view,
                "level_name": name,
                "level_nq": round(level, 2),
                "nq_at_save": round(float(nq_now), 2),
                "ratio": round(float(ratio), 6),
                "underlyings": "+".join(data.get("underlyings", []) or []),
                "options_source": meta.get("options_source", ""),
                "flip_model": meta.get("flip_model", ""),
            }
        )
    return rows


def read_log(path: str | None = None) -> pd.DataFrame:
    p = log_path(path)
    if not os.path.exists(p):
        return pd.DataFrame(columns=LOG_COLUMNS)
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame(columns=LOG_COLUMNS)


def append_rows(rows: list[dict], path: str | None = None) -> int:
    if not rows:
        return 0
    p = log_path(path)
    folder = os.path.dirname(p)
    if folder:
        os.makedirs(folder, exist_ok=True)
    frame = pd.DataFrame(rows, columns=LOG_COLUMNS)
    write_header = not os.path.exists(p)
    frame.to_csv(p, mode="a", header=write_header, index=False)
    return len(frame)


def has_snapshot(session_date: str, tag: str, view: str, path: str | None = None) -> bool:
    log = read_log(path)
    if log.empty:
        return False
    hit = log[(log["session_date"].astype(str) == str(session_date)) & (log["tag"] == tag) & (log["view"] == view)]
    return not hit.empty


def maybe_auto_snapshot(data: dict, view: str, nq_now: float, ratio: float, path: str | None = None,
                        now: datetime | None = None, earliest="09:45", latest="15:30") -> int:
    """Save one "auto" snapshot per session date and view, during the cash session.

    09:45 ET by default, so the opening print has gone through but the levels
    are still the ones a trader would use for the day.
    """
    now = now or gm.now_et()
    if now.weekday() >= 5:
        return 0
    hhmm = now.strftime("%H:%M")
    if not (earliest <= hhmm <= latest):
        return 0
    if has_snapshot(now.date().isoformat(), "auto", view, path):
        return 0
    return append_rows(snapshot_rows(data, view, nq_now, ratio, tag="auto", now=now), path)


def score_levels(log: pd.DataFrame, bars: pd.DataFrame, tolerance_pts: float = 8.0,
                 reaction_pts: float = 25.0, break_pts: float = 15.0, lookahead_bars: int = 12) -> pd.DataFrame:
    """Score each logged level against later NQ price action on its session.

    For each level saved on day D, take the bars after the save time through
    the end of D. The first bar whose range comes within ``tolerance_pts`` of
    the level is the touch. From there, over ``lookahead_bars``:

    * "held": price moved ``reaction_pts`` away from the level on the side it
      approached from before closing ``break_pts`` beyond it.
    * "broke": price closed ``break_pts`` beyond the level first.
    * "unresolved": neither within the window.
    * "untouched": the level was never reached that session.

    Returns one row per logged level with its outcome.
    """
    if log is None or log.empty or bars is None or bars.empty:
        return pd.DataFrame()
    bars = bars.copy()
    if getattr(bars.index, "tz", None) is None:
        bars.index = bars.index.tz_localize("UTC").tz_convert(gm.ET)
    else:
        bars.index = bars.index.tz_convert(gm.ET)
    bars = bars.sort_index()

    out = []
    for _, row in log.iterrows():
        try:
            saved = pd.Timestamp(row["saved_at_et"])
            if saved.tzinfo is None:
                saved = saved.tz_localize(gm.ET)
            level = float(row["level_nq"])
        except Exception:
            continue
        day_end = pd.Timestamp(saved.date().isoformat() + " 16:00", tz=gm.ET)
        window = bars[(bars.index > saved) & (bars.index <= day_end)]
        outcome, touch_time, approach = "untouched", None, None
        if not window.empty:
            near = (window["Low"] <= level + tolerance_pts) & (window["High"] >= level - tolerance_pts)
            if near.any():
                pos = int(np.argmax(near.to_numpy()))
                touch_time = window.index[pos]
                prior_close = float(window["Close"].iloc[pos - 1]) if pos > 0 else float(row.get("nq_at_save", level))
                approach = "from_below" if prior_close < level else "from_above"
                after = window.iloc[pos: pos + 1 + int(lookahead_bars)]
                outcome = "unresolved"
                for _, b in after.iterrows():
                    if approach == "from_below":
                        if float(b["Close"]) >= level + break_pts:
                            outcome = "broke"
                            break
                        if float(b["Low"]) <= level - reaction_pts:
                            outcome = "held"
                            break
                    else:
                        if float(b["Close"]) <= level - break_pts:
                            outcome = "broke"
                            break
                        if float(b["High"]) >= level + reaction_pts:
                            outcome = "held"
                            break
        rec = row.to_dict()
        rec.update({"outcome": outcome, "touch_time_et": touch_time.isoformat() if touch_time is not None else None, "approach": approach})
        out.append(rec)
    return pd.DataFrame(out)


def summarize_scores(scored: pd.DataFrame) -> pd.DataFrame:
    """Hold rate per level type: held / (held + broke). Untouched days excluded."""
    if scored is None or scored.empty:
        return pd.DataFrame()
    g = scored.groupby(["view", "level_name"])["outcome"]
    summary = g.value_counts().unstack(fill_value=0)
    for col in ("held", "broke", "unresolved", "untouched"):
        if col not in summary.columns:
            summary[col] = 0
    resolved = summary["held"] + summary["broke"]
    summary["touch_rate"] = ((summary["held"] + summary["broke"] + summary["unresolved"]) /
                             summary[["held", "broke", "unresolved", "untouched"]].sum(axis=1)).round(3)
    summary["hold_rate"] = (summary["held"] / resolved.where(resolved > 0)).round(3)
    summary["sessions"] = scored.groupby(["view", "level_name"])["session_date"].nunique()
    return summary.reset_index()[["view", "level_name", "sessions", "held", "broke", "unresolved", "untouched", "touch_rate", "hold_rate"]]
