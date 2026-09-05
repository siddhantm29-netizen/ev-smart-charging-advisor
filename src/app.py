"""
app.py — Streamlit multi-page app combining the forecast chart,
recommendation panel, and charging-station map, with an EN/DE language switch.

Run:
    streamlit run src/app.py
"""

from __future__ import annotations

import streamlit as st

from i18n import LANGUAGES, t
from views import charging_map, forecast, home, recommendation

st.set_page_config(page_title="EV Smart-Charging Advisor", page_icon="🔌", layout="wide")

if "lang" not in st.session_state:
    st.session_state.lang = "en"

with st.sidebar:
    # key="lang" binds directly to st.session_state so the language switch
    # takes effect on the same rerun it's clicked (no one-click lag).
    st.radio(
        "🌐",
        options=list(LANGUAGES.keys()),
        format_func=lambda code: LANGUAGES[code],
        horizontal=True,
        key="lang",
    )

lang = st.session_state.lang

pages = [
    st.Page(lambda: home.render(lang),           title=t("nav_home", lang),           icon="🏠",  url_path="home", default=True),
    st.Page(lambda: forecast.render(lang),        title=t("nav_forecast", lang),        icon="📈",  url_path="forecast"),
    st.Page(lambda: recommendation.render(lang),  title=t("nav_recommendation", lang),  icon="💡",  url_path="recommendation"),
    st.Page(lambda: charging_map.render(lang),    title=t("nav_map", lang),             icon="🗺️", url_path="map"),
]
st.navigation(pages).run()
