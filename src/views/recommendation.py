"""Recommendation page: alpha-weighted ranked charging windows."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_data import get_forecast
from forecast import PALETTE
from i18n import fmt_datetime, fmt_number, fmt_pct, t
from recommend import find_windows, score_windows


def _recommendation_banner(windows: list[dict], origin: pd.Timestamp, lang: str) -> str:
    if not windows:
        return t("no_windows_msg", lang)
    best = windows[0]
    hours_away = (best["start"] - origin).total_seconds() / 3600
    price = fmt_number(best["avg_price"], lang, 0)
    renewable = fmt_pct(best["avg_renewable_share"], lang)
    if hours_away <= 1:
        return t("recommendation_now", lang, end=fmt_datetime(best["end"], lang),
                  duration=best["duration_h"], price=price, renewable=renewable)
    return t("recommendation_wait", lang, hours=round(hours_away), start=fmt_datetime(best["start"], lang),
              duration=best["duration_h"], price=price, renewable=renewable)


def _chart_with_windows(scored_df: pd.DataFrame, windows: list[dict], lang: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=scored_df["timestamp"], y=scored_df["price_forecast"], mode="lines",
                              name=t("forecast_price_chart_title", lang), line=dict(color=PALETTE["xgboost"], width=2)))
    for w in windows:
        fig.add_vrect(x0=w["start"], x1=w["end"], fillcolor="#0ca30c", opacity=0.15, line_width=0)
    fig.update_layout(
        yaxis_title=t("forecast_price_axis", lang),
        margin=dict(l=10, r=10, t=20, b=10), height=350,
        plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e1e0d9")
    return fig


def render(lang: str) -> None:
    st.title(t("recommendation_heading", lang))
    st.caption(t("recommendation_intro", lang))

    alpha = st.slider(t("alpha_label", lang), min_value=0.0, max_value=1.0, value=0.5, step=0.05,
                       help=t("alpha_help", lang))
    lcol, rcol = st.columns(2)
    lcol.caption(t("alpha_cost_caption", lang))
    rcol.markdown(f"<div style='text-align:right'>{t('alpha_green_caption', lang)}</div>", unsafe_allow_html=True)

    forecast_df, origin = get_forecast()
    scored_df = score_windows(forecast_df, alpha=alpha)
    windows = find_windows(scored_df, top_frac=0.25)

    st.markdown(_recommendation_banner(windows, origin, lang))
    st.plotly_chart(_chart_with_windows(scored_df, windows, lang), use_container_width=True)

    st.subheader(t("windows_heading", lang))
    if windows:
        table = pd.DataFrame([{
            t("window_col_rank", lang): i + 1,
            t("window_col_start", lang): fmt_datetime(w["start"], lang),
            t("window_col_end", lang): fmt_datetime(w["end"], lang),
            t("window_col_duration", lang): w["duration_h"],
            t("window_col_price", lang): fmt_number(w["avg_price"], lang, 1),
            t("window_col_renewable", lang): fmt_pct(w["avg_renewable_share"], lang),
            t("window_col_score", lang): fmt_number(w["avg_score"], lang, 2),
        } for i, w in enumerate(windows)])
        st.dataframe(table, hide_index=True, use_container_width=True)
    else:
        st.info(t("no_windows_msg", lang))
