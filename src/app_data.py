"""
app_data.py — cached data/model access shared by the Streamlit views
(Phase 6). Centralized so every page hits the same cache entries instead of
each view re-loading (and re-caching separately) the same files.
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
    """Returns (forecast_df, origin). Cached since it involves loading two
    XGBoost models and scoring 48 pooled feature rows — cheap, but no
    reason to redo it on every widget interaction within the same hour."""
    return recommend.build_forecast()


@st.cache_data(ttl=3600)
def get_backtest_metrics(target_col: str) -> dict:
    import json
    path = recommend.MODELS_DIR / f"backtest_{target_col}_metrics.json"
    with open(path) as f:
        return json.load(f)
