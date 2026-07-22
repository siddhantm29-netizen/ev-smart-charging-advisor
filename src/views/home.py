"""Home / overview page."""

from __future__ import annotations

import streamlit as st

from app_data import get_smard_df, get_stations_df
from i18n import fmt_datetime, t


def render(lang: str) -> None:
    st.title(t("home_heading", lang))
    st.caption(t("app_tagline", lang))
    st.write(t("home_intro", lang))

    smard_df = get_smard_df()
    stations_df = get_stations_df()

    st.subheader(t("home_stats_heading", lang))
    c1, c2, c3 = st.columns(3)
    c1.metric(t("home_stat_stations", lang), f"{len(stations_df):,}")
    # Month precision (not full dates) so this fits st.metric's width, which
    # doesn't wrap — "2024-07-20 → 2026-07-22" was getting clipped.
    month_fmt = "%m.%Y" if lang == "de" else "%Y-%m"
    date_range = f"{smard_df.index.min():{month_fmt}} → {smard_df.index.max():{month_fmt}}"
    c2.metric(t("home_stat_data_range", lang), date_range)
    c3.metric(t("home_stat_last_updated", lang), fmt_datetime(smard_df.index.max(), lang, with_weekday=False))

    st.divider()
    st.subheader(t("home_pages_heading", lang))
    st.markdown("- " + t("home_page_forecast", lang))
    st.markdown("- " + t("home_page_recommendation", lang))
    st.markdown("- " + t("home_page_map", lang))

    st.divider()
    st.caption(t("home_attribution", lang))
    st.info(t("home_disclaimer", lang))
