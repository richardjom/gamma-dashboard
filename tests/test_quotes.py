import unittest
from datetime import datetime, timezone

from nq_precision.quotes import (
    candidate_schwab_symbols,
    extract_quote_price,
    get_schwab_futures_price,
)


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeRequestsSession:
    def __init__(self, responses):
        self._responses = list(responses)

    def get(self, *args, **kwargs):
        return self._responses.pop(0)


class QuoteModuleTests(unittest.TestCase):
    def test_candidate_symbols_roll_to_current_quarter(self):
        now = datetime(2026, 8, 5, tzinfo=timezone.utc)
        secret_getter = lambda name, default="": default

        candidates = candidate_schwab_symbols("NQ=F", secret_getter=secret_getter, now=now)

        self.assertEqual(candidates[:5], ["/NQ", "/NQU26", "/NQU2026", "/NQZ26", "/NQZ2026"])

    def test_candidate_symbols_preserve_digit_override(self):
        def secret_getter(name, default=""):
            if name == "SCHWAB_SYMBOL_NQ":
                return "/NQM26"
            return default

        candidates = candidate_schwab_symbols("NQ=F", secret_getter=secret_getter)

        self.assertEqual(candidates, ["/NQM26"])

    def test_extract_quote_price_uses_mark_fallback(self):
        quote = {"quote": {"mark": "21876.25"}}

        price = extract_quote_price(quote)

        self.assertEqual(price, 21876.25)

    def test_get_schwab_futures_price_reports_missing_price_reject(self):
        session_state = {}
        requests_session = _FakeRequestsSession(
            [_FakeResponse(200, {"/NQU26": {"quote": {"description": "Nasdaq 100"}}})]
        )

        price, source = get_schwab_futures_price(
            "NQ=F",
            secret_getter=lambda name, default="": "/NQU26" if name == "SCHWAB_SYMBOL_NQ" else default,
            access_token_getter=lambda force_refresh=False: "token",
            auth_status_formatter=lambda default="Failed/unavailable", session_state=None: default,
            session_state=session_state,
            requests_session=requests_session,
        )

        self.assertIsNone(price)
        self.assertIn("quote_rejects missing=1", source)


if __name__ == "__main__":
    unittest.main()
