---
title: Gamma Dashboard
emoji: 📈
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: "1.49.0"
app_file: app.py
pinned: false
---

# Gamma Dashboard

Quick setup and run instructions

1. Create/activate virtualenv (already created as `.venv`):

```bash
cd /Users/bobert/Documents/Gamma
source .venv/bin/activate
```

2. Install dependencies (if needed):

```bash
pip install -r requirements.txt
```

3. Configure API secrets (optional but recommended for real-time Schwab futures):

Create `/Users/bobert/Documents/Gamma/.streamlit/secrets.toml`:

```toml
FINNHUB_KEY = "..."
SCHWAB_APP_KEY = "..."
SCHWAB_APP_SECRET = "..."
SCHWAB_REFRESH_TOKEN = "..."
# Optional short-lived token for local testing only:
# SCHWAB_ACCESS_TOKEN = "..."
# Optional tuning:
# SCHWAB_MAX_STALE_SECONDS = 180
# MAX_ONE_TICK_JUMP_PCT = 5
# MAX_CROSS_SOURCE_DEVIATION_PCT = 3
# Optional overrides if your Schwab symbols differ:
# SCHWAB_SYMBOL_NQ = "/NQZ26"  # Optional; stale quarterly overrides auto-roll forward.
# SCHWAB_SYMBOL_ES = "/ESH26"
# SCHWAB_SYMBOL_GC = "/GCG26"
```

4. Run the app:

```bash
streamlit run nq_app.py
```

Notes:
- `.venv` is gitignored. Use the `requirements.txt` for reproducible installs.
- For Hugging Face Spaces, set the same names in Space `Settings -> Variables and secrets`.
- Do not deploy with only `SCHWAB_ACCESS_TOKEN`; it expires quickly and will lead to quote failures once Schwab returns `401`.

## How the gamma levels are calculated

All of this lives in `nq_precision/gamma_math.py` (pure functions, unit tested).

- **Gamma Flip**: every contract's gamma is repriced with Black Scholes at a grid of hypothetical
  prices (its own IV, time to its ET settlement), summed, and the zero crossing nearest spot is the
  flip. If there is no crossing within ±20% the dashboard says so instead of inventing a level.
- **Delta Neutral**: the price where open interest weighted call delta and put delta balance,
  found the same way.
- **GEX** = gamma × open interest × 100 × spot² × 0.01, in dollars per 1% move. Calls are positive
  and puts negative, which assumes dealers are long calls and short puts. That is a convention, not
  observed positioning.
- Exposure math always uses the **full chain** for the selected expiration. The strike window and
  liquidity filters only choose which strikes can be walls and floors.
- **Gamma universe**: by default NDX/NDXP options are folded in with QQQ. Each NDX contract is
  rescaled by QQQ spot / NDX spot so its dollar gamma and dollar delta are preserved exactly.
- **All expirations** view aggregates every expiration out to 45 DTE.
- **Volume gamma** repeats the math with today's volume instead of open interest, because open
  interest only updates overnight.
- All dates and expiries use US Eastern time, so a UTC server no longer rolls "today" at 8pm ET or
  counts contracts that expired at the 4pm close.
- CBOE data is stamped with CBOE's own as of time and shown as `delayed`, not `fresh`.

Optional settings (secrets or environment variables):

```toml
# RISK_FREE_RATE = 0.04
# UNDERLYING_DIVIDEND_YIELD = 0.006
# DELAYED_CONFIDENCE_MULTIPLIER = 0.85
# SESSION_CLOSED_CONFIDENCE_MULTIPLIER = 0.90
# OPTIONS_MAX_DTE_FETCH = 60
# LEVEL_LOG_PATH = "/data/level_snapshots.csv"
```

## Level accuracy log

The dashboard saves one snapshot of the 0DTE and all expirations levels each session after
09:45 ET (`nq_precision/level_log.py`). The **Level accuracy log** panel scores them against NQ
5 minute bars: a level is touched when price trades within 8 points, and it **held** if price then
moved 25 points away before closing 15 points through it within an hour. Hold rate per level type
is the number to watch over time.

On Hugging Face Spaces the disk resets on restart. Enable persistent storage and set
`LEVEL_LOG_PATH=/data/level_snapshots.csv`, or download the CSV from the panel regularly.

## Tests

```bash
python -m pytest -q
```

## Deploy to Hugging Face Space via GitHub Actions

This repo includes `.github/workflows/sync.yml` to mirror `main` to your Hugging Face Space.

1. In GitHub repo settings, add Actions secret:
   - `HF_TOKEN`: a Hugging Face User Access Token with write access to your Space.
2. Push changes to `main`.
3. In GitHub, verify workflow **Sync to Hugging Face** passes.

Your Space should target `app.py` (already included in this repo).
