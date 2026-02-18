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
# Optional tuning:
# SCHWAB_MAX_STALE_SECONDS = 180
# MAX_ONE_TICK_JUMP_PCT = 5
# MAX_CROSS_SOURCE_DEVIATION_PCT = 3
# Optional overrides if your Schwab symbols differ:
# SCHWAB_SYMBOL_NQ = "/NQH26"
# SCHWAB_SYMBOL_ES = "/ESH26"
```

4. Run the app:

```bash
streamlit run nq_app.py
```

Notes:
- `.venv` is gitignored. Use the `requirements.txt` for reproducible installs.
