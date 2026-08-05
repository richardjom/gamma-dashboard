import time
from urllib.parse import parse_qs, unquote, urlparse

import requests
import streamlit as st

from nq_precision.config import get_secret


SCHWAB_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"


def set_schwab_auth_status(status, detail="", session_state=None):
    state = session_state if session_state is not None else st.session_state
    state["schwab_auth_status"] = status
    if detail:
        state["schwab_auth_status_detail"] = detail
    else:
        state.pop("schwab_auth_status_detail", None)


def format_schwab_auth_status(default="Failed/unavailable", session_state=None):
    state = session_state if session_state is not None else st.session_state
    status = str(state.get("schwab_auth_status", "") or "").strip()
    detail = str(state.get("schwab_auth_status_detail", "") or "").strip()
    if status and detail:
        return f"{status}: {detail}"
    if status:
        return status
    return default


def schwab_is_configured(secret_getter=get_secret):
    return bool(
        secret_getter("SCHWAB_APP_KEY")
        and secret_getter("SCHWAB_APP_SECRET")
        and (secret_getter("SCHWAB_REFRESH_TOKEN") or secret_getter("SCHWAB_ACCESS_TOKEN"))
    )


def get_schwab_access_token(
    force_refresh=False,
    secret_getter=get_secret,
    session_state=None,
    requests_session=requests,
    now=None,
):
    state = session_state if session_state is not None else st.session_state
    static_token = secret_getter("SCHWAB_ACCESS_TOKEN")
    if static_token and not force_refresh:
        set_schwab_auth_status(
            "using_static_access_token",
            "SCHWAB_ACCESS_TOKEN is set; if quotes start failing with 401, rotate it or provide SCHWAB_REFRESH_TOKEN.",
            session_state=state,
        )
        return static_token

    now = time.time() if now is None else now
    cached_token = state.get("schwab_access_token")
    cached_exp = state.get("schwab_access_expires_at", 0)
    if cached_token and now < (cached_exp - 30) and not force_refresh:
        set_schwab_auth_status("using_cached_access_token", session_state=state)
        return cached_token

    app_key = secret_getter("SCHWAB_APP_KEY")
    app_secret = secret_getter("SCHWAB_APP_SECRET")
    refresh_token = secret_getter("SCHWAB_REFRESH_TOKEN")
    if not (app_key and app_secret and refresh_token):
        missing = [
            name
            for name, value in (
                ("SCHWAB_APP_KEY", app_key),
                ("SCHWAB_APP_SECRET", app_secret),
                ("SCHWAB_REFRESH_TOKEN", refresh_token),
            )
            if not value
        ]
        set_schwab_auth_status("missing_schwab_oauth_secret", ", ".join(missing), session_state=state)
        return None

    try:
        response = requests_session.post(
            SCHWAB_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(app_key, app_secret),
            timeout=10,
        )
        if response.status_code != 200:
            hint = ""
            if response.status_code in (400, 401):
                hint = "Refresh token expired/invalid, or app key/secret do not match the token."
            set_schwab_auth_status(f"refresh_http_{response.status_code}", hint, session_state=state)
            return None
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            set_schwab_auth_status("refresh_payload_missing_access_token", session_state=state)
            return None
        expires_in = int(payload.get("expires_in", 1800))
        state["schwab_access_token"] = token
        state["schwab_access_expires_at"] = now + expires_in
        set_schwab_auth_status("refresh_ok", f"expires_in={expires_in}s", session_state=state)
        return token
    except Exception as exc:
        set_schwab_auth_status("refresh_exception", str(exc)[:160], session_state=state)
        return None


def exchange_schwab_auth_code(auth_code, redirect_uri, secret_getter=get_secret, requests_session=requests):
    app_key = secret_getter("SCHWAB_APP_KEY")
    app_secret = secret_getter("SCHWAB_APP_SECRET")
    if not (app_key and app_secret):
        return None, "Missing SCHWAB_APP_KEY or SCHWAB_APP_SECRET in secrets."
    if not auth_code:
        return None, "Authorization code is required."

    code_input = str(auth_code).strip()
    if code_input.startswith("http://") or code_input.startswith("https://"):
        try:
            parsed = urlparse(code_input)
            code_input = parse_qs(parsed.query).get("code", [code_input])[0]
        except Exception:
            pass
    elif "code=" in code_input:
        try:
            parsed = urlparse(code_input)
            code_input = parse_qs(parsed.query).get("code", [code_input])[0]
        except Exception:
            code_input = code_input.split("code=", 1)[-1]
            if "&" in code_input:
                code_input = code_input.split("&", 1)[0]

    code_input = unquote(code_input).strip()
    if "&" in code_input:
        code_input = code_input.split("&", 1)[0].strip()

    try:
        response = requests_session.post(
            SCHWAB_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code_input,
                "redirect_uri": redirect_uri,
            },
            auth=(app_key, app_secret),
            timeout=15,
        )
        if response.status_code != 200:
            return None, f"Token exchange failed ({response.status_code}): {response.text[:200]}"
        return response.json(), None
    except Exception as exc:
        return None, f"Token exchange failed: {exc}"
