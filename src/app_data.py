"""
app_data.py — cached data/model access shared by all Streamlit views.
Centralising here ensures every page hits the same cache entries.
"""

from __future__ import annotations

import streamlit as st

import map_stations
import recommend
from forecast import load_clean_smard


@st.cache_data(ttl=3600)
def get_smard_df():
    return load_clean_smard()


@st.cache_data(ttl=3600)
def get_stations_df():
    return map_stations.load_stations()


@st.cache_data(ttl=3600)
def get_forecast():
    """Returns (forecast_df, origin). Cached — loading two XGBoost models and
    scoring 48 feature rows is cheap but pointless to repeat within the hour."""
    return recommend.build_forecast()


@st.cache_data(ttl=3600)
def get_backtest_metrics(target_col: str) -> dict:
    import json
    path = recommend.MODELS_DIR / f"backtest_{target_col}_metrics.json"
    with open(path) as f:
        return json.load(f)
