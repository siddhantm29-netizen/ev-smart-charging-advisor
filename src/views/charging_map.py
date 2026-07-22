"""Charging map page: all stations, filterable by region (dropdown) and
connector type (Plotly legend toggle, built into the figure)."""

from __future__ import annotations

import streamlit as st

from app_data import get_stations_df
from i18n import t
from map_stations import CONNECTOR_CATEGORIES, build_map

_CATEGORY_KEYS = {
    "DC fast (CCS)": "connector_dc_ccs",
    "DC fast (CHAdeMO)": "connector_dc_chademo",
    "AC Type 2": "connector_ac_type2",
    "Other": "connector_other",
}


def render(lang: str) -> None:
    st.title(t("map_heading", lang))
    st.caption(t("map_intro", lang))

    df = get_stations_df()
    regions = [t("region_all_option", lang)] + sorted(df["Bundesland"].dropna().unique().tolist())
    selected = st.selectbox(t("region_label", lang), regions)
    region = None if selected == t("region_all_option", lang) else selected

    shown_df = df if region is None else df[df["Bundesland"] == region]
    st.caption(t("map_stats", lang, n=len(shown_df)) + " — " + t("connector_legend_note", lang))

    category_labels = {c: t(_CATEGORY_KEYS[c], lang) for c in CONNECTOR_CATEGORIES}
    category_labels["_legend_title"] = t("connector_type_label", lang)
    fig = build_map(df, region=region, category_labels=category_labels)
    # map_stations sets an English-only title; the caption above already
    # shows this info translated, so drop the figure's own title.
    fig.update_layout(title="", margin=dict(l=0, r=0, t=10, b=0), height=650)
    st.plotly_chart(fig, use_container_width=True)
