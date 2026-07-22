"""Forecast page: next-48h price and renewable-share charts, plus the
backtest comparison against the naive benchmarks (Phase 3)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_data import get_backtest_metrics, get_forecast
from forecast import PALETTE
from i18n import fmt_datetime, t


def _line_chart(df: pd.DataFrame, y_col: str, title: str, y_axis: str, color: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df[y_col], mode="lines",
        line=dict(color=color, width=2.2),
    ))
    if y_col == "price_forecast":
        fig.add_hline(y=0, line_color="#c3c2b7", line_width=1)
    fig.update_layout(
        title=title, yaxis_title=y_axis,
        margin=dict(l=10, r=10, t=40, b=10), height=320,
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e1e0d9")
    return fig


def render(lang: str) -> None:
    st.title(t("forecast_heading", lang))
    st.caption(t("forecast_intro", lang))

    forecast_df, origin = get_forecast()
    st.caption(t("forecast_asof", lang, time=fmt_datetime(origin, lang, with_weekday=False)))

    st.plotly_chart(
        _line_chart(forecast_df, "price_forecast", t("forecast_price_chart_title", lang),
                    t("forecast_price_axis", lang), PALETTE["xgboost"]),
        use_container_width=True,
    )
    st.plotly_chart(
        _line_chart(forecast_df, "renewable_share_forecast", t("forecast_renewable_chart_title", lang),
                    t("forecast_renewable_axis", lang), PALETTE["seasonal_naive_168h"]),
        use_container_width=True,
    )

    with st.expander(t("forecast_model_note_heading", lang), expanded=False):
        st.write(t("forecast_model_note_body", lang))

    st.subheader(t("forecast_backtest_heading", lang))
    price_metrics = get_backtest_metrics("price_eur_mwh")
    renewable_metrics = get_backtest_metrics("renewable_share")

    rows = []
    for key, label_key in (
        ("persistence_naive", "method_persistence"),
        ("seasonal_naive_168h", "method_seasonal"),
        ("prophet", "method_prophet"),
        ("xgboost", "method_xgboost"),
    ):
        if key in price_metrics:
            rows.append({
                t("forecast_backtest_col_method", lang): t(label_key, lang),
                t("forecast_backtest_col_price_mae", lang): round(price_metrics[key]["mae"], 1),
                t("forecast_backtest_col_renewable_mae", lang): round(renewable_metrics[key]["mae"], 3),
            })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
