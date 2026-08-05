import os

import streamlit as st


def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value not in (None, ""):
            return value
    except Exception:
        pass
    return os.getenv(name, default)
