"""Recommendation page: alpha-weighted ranked charging windows."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from app_data import get_forecast
from forecast import PALETTE
from i18n import fmt_datetime, fmt_number, fmt_pct, t
from recommend import find_windows, score_windows


def _chart_with_windows(scored_df: pd.DataFrame, windows: list[dict], lang: str) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Renewable share as background area
    fig.add_trace(go.Scatter(
        x=scored_df["timestamp"], y=scored_df["renewable_share_forecast"],
        mode="lines",
        name=t("metric_green_energy", lang),
        line=dict(color="#2ca02c", width=0),
        fill='tozeroy',
        fillcolor="rgba(44, 160, 44, 0.15)",
        hovertemplate="%{y:.1%}<extra></extra>"
    ), secondary_y=True)

    # Price forecast as a solid line
    fig.add_trace(go.Scatter(
        x=scored_df["timestamp"], y=scored_df["price_forecast"],
        mode="lines",
        name=t("forecast_price_chart_title", lang),
        line=dict(color=PALETTE["xgboost"], width=3),
        hovertemplate="%{y:.1f} €/MWh<extra></extra>"
    ), secondary_y=False)

    # Highlight best windows with vertical bands
    for w in windows:
        fig.add_vrect(x0=w["start"], x1=w["end"], fillcolor="#0ca30c", opacity=0.25, line_width=0, layer="below")
        
    fig.update_layout(
        margin=dict(l=10, r=10, t=20, b=10), height=400,
        plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
        hovermode="x unified"
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(title_text=t("forecast_price_axis", lang), gridcolor="#e1e0d9", secondary_y=False)
    fig.update_yaxes(title_text=t("metric_green_energy", lang), tickformat=".0%", showgrid=False, secondary_y=True)
    return fig


def render(lang: str) -> None:
    st.title(t("recommendation_heading", lang))
    st.caption(t("recommendation_intro", lang))

    # Controls
    alpha = st.slider(t("alpha_label", lang), min_value=0.0, max_value=1.0,
                      value=0.5, step=0.05, help=t("alpha_help", lang))
    lcol, rcol = st.columns(2)
    lcol.caption(t("alpha_cost_caption", lang))
    rcol.markdown(f"<div style='text-align:right'>{t('alpha_green_caption', lang)}</div>",
                  unsafe_allow_html=True)
    
    st.divider()

    forecast_df, origin = get_forecast()
    scored_df = score_windows(forecast_df, alpha=alpha)
    windows   = find_windows(scored_df, top_frac=0.25)

    if windows:
        # Hero metrics for the #1 recommended window
        best = windows[0]
        st.subheader("💡 " + t("metric_best_time", lang) + " (Top 1)")
        
        m1, m2, m3 = st.columns(3)
        time_str = f"{fmt_datetime(best["start"], lang)}"
        m1.metric("Start Time", time_str, f"{best['duration_h']} hours")
        m2.metric(t("metric_avg_price", lang), f"{fmt_number(best['avg_price'], lang, 1)} €", delta="Lowest Cost", delta_color="inverse")
        m3.metric(t("metric_green_energy", lang), fmt_pct(best['avg_renewable_share'], lang), delta="Max Green", delta_color="normal")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Interactive Chart
        st.plotly_chart(_chart_with_windows(scored_df, windows, lang), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader(t("windows_heading", lang))
        
        # Modernized DataFrame display using column config
        table = pd.DataFrame([{
            "Rank": i + 1,
            "Start": w["start"],
            "End": w["end"],
            "Duration (h)": w["duration_h"],
            "Price (€/MWh)": w["avg_price"],
            "Green %": w["avg_renewable_share"],
            "Score": w["avg_score"],
        } for i, w in enumerate(windows)])
        
        st.dataframe(
            table, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Start": st.column_config.DatetimeColumn(format="ddd HH:mm"),
                "End": st.column_config.DatetimeColumn(format="ddd HH:mm"),
                "Price (€/MWh)": st.column_config.NumberColumn(format="%.1f €"),
                "Green %": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=1.5),
                "Score": st.column_config.NumberColumn(format="%.2f")
            }
        )
    else:
        st.info(t("no_windows_msg", lang))
