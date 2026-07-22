"""
app.py — Phase 6 of the roadmap: Streamlit app combining the forecast chart,
recommendation panel, and charging-station map into one multi-page app, with
a German/English language switch (this project's subject is the German
electricity market, so both are first-class rather than English-only).

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
    # key="lang" binds directly to st.session_state.lang, which Streamlit
    # syncs *before* the script re-runs on a click — unlike reading
    # st.session_state.lang to build this widget's own label (or passing
    # index=) and assigning the return value back afterwards, which lags
    # one click behind (the label/other language-dependent bits below would
    # render using the *previous* language on the very rerun where the user
    # just switched). The "🌐" label sidesteps needing translation at all
    # for the one piece of UI that can't know the language yet.
    st.radio(
        "🌐",
        options=list(LANGUAGES.keys()),
        format_func=lambda code: LANGUAGES[code],
        horizontal=True,
        key="lang",
    )

lang = st.session_state.lang

pages = [
    st.Page(lambda: home.render(lang), title=t("nav_home", lang), icon="🏠", url_path="home", default=True),
    st.Page(lambda: forecast.render(lang), title=t("nav_forecast", lang), icon="📈", url_path="forecast"),
    st.Page(lambda: recommendation.render(lang), title=t("nav_recommendation", lang), icon="💡", url_path="recommendation"),
    st.Page(lambda: charging_map.render(lang), title=t("nav_map", lang), icon="🗺️", url_path="map"),
]
nav = st.navigation(pages)
nav.run()
