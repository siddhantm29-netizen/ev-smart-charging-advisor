"""
i18n.py — translation strings and locale-aware formatting for the Streamlit
app (Phase 6). Two languages: English ("en") and German ("de"), matching the
project's subject (the German electricity market) and target audience
(German/EU energy-transition job market, per the project brief).
"""

from __future__ import annotations

import pandas as pd

LANGUAGES = {"en": "English", "de": "Deutsch"}

TRANSLATIONS = {
    "en": {
        "app_title": "EV Smart-Charging Advisor",
        "app_tagline": "The cheapest and greenest times to charge an EV in Germany, from real grid data.",

        "nav_home": "Home",
        "nav_forecast": "Forecast",
        "nav_recommendation": "Recommendation",
        "nav_map": "Charging Map",

        # --- Home ---
        "home_heading": "EV Smart-Charging Advisor",
        "home_intro": (
            "Germany's electricity price and renewable share swing a lot throughout the day, "
            "depending on wind, solar, and demand. This tool pulls real historical grid data from "
            "SMARD (Bundesnetzagentur), forecasts near-term price and renewable share, and turns "
            "that into a plain “charge now / wait until X” recommendation — plus a map of "
            "public charging stations."
        ),
        "home_stats_heading": "This session's data, at a glance",
        "home_stat_stations": "Charging stations mapped",
        "home_stat_data_range": "Grid data range",
        "home_stat_last_updated": "Latest data point",
        "home_pages_heading": "What's in this app",
        "home_page_forecast": "**Forecast** — next 48h price and renewable-share forecast, plus how the model compares to simple benchmarks.",
        "home_page_recommendation": "**Recommendation** — a ranked list of the best charging windows, weighted however you like between cost and green-ness.",
        "home_page_map": "**Charging Map** — every public charging station in Germany, filterable by connector type and region.",
        "home_attribution": "Data: Bundesnetzagentur | SMARD.de (CC BY 4.0) and the Bundesnetzagentur's Ladesäulenregister.",
        "home_disclaimer": (
            "Portfolio project, not financial or operational advice. Forecasts are backtested on a "
            "single 48h window — see the Forecast page for an honest accounting of where the model "
            "does (and doesn't) beat a naive benchmark."
        ),

        # --- Forecast ---
        "forecast_heading": "Price & Renewable-Share Forecast",
        "forecast_intro": "Next 48 hours, forecast from the latest available grid data.",
        "forecast_asof": "As of {time}",
        "forecast_price_chart_title": "Price forecast",
        "forecast_renewable_chart_title": "Renewable share forecast",
        "forecast_price_axis": "EUR/MWh",
        "forecast_renewable_axis": "renewable / load",
        "forecast_model_note_heading": "About this forecast",
        "forecast_model_note_body": (
            "Price is a 50/50 blend of an XGBoost model and a seasonal-naive benchmark (same hour, "
            "same weekday, one week ago). That's not a hedge for show: backtesting on a held-out 48h "
            "window found XGBoost *alone* underperforms the seasonal-naive benchmark on price (-62% "
            "skill), likely because it smooths over sharp, recurring weekly price swings that the "
            "naive benchmark reproduces for free. Renewable share uses XGBoost alone — it was the one "
            "model that beat seasonal-naive there (+15% skill). Full methodology and backtest figures "
            "are in the project README."
        ),
        "forecast_backtest_heading": "How the models compare (48h backtest)",
        "forecast_backtest_col_method": "Method",
        "forecast_backtest_col_price_mae": "Price MAE (EUR/MWh)",
        "forecast_backtest_col_renewable_mae": "Renewable-share MAE",
        "method_persistence": "Persistence naive",
        "method_seasonal": "Seasonal naive (t-168h)",
        "method_prophet": "Prophet",
        "method_xgboost": "XGBoost",

        # --- Recommendation ---
        "recommendation_heading": "Best Charging Windows",
        "recommendation_intro": "Ranked windows over the next 48 hours, balancing cost and green-ness.",
        "alpha_label": "Cost vs. green-ness",
        "alpha_help": "0 = cheapest possible, 1 = greenest possible. Windows are ranked by a blend of the two.",
        "alpha_cost_caption": "Cheapest",
        "alpha_green_caption": "Greenest",
        "recommendation_now": "**Charge now** — good window through {end} ({duration}h, avg {price} EUR/MWh, {renewable} renewable).",
        "recommendation_wait": "**Wait ~{hours}h** — best window starts {start}, runs {duration}h (avg {price} EUR/MWh, {renewable} renewable).",
        "windows_heading": "Ranked windows",
        "window_col_rank": "#",
        "window_col_start": "Start",
        "window_col_end": "End",
        "window_col_duration": "Duration (h)",
        "window_col_price": "Avg. price (EUR/MWh)",
        "window_col_renewable": "Avg. renewable share",
        "window_col_score": "Score",
        "no_windows_msg": "No standout windows in the next 48h — price and renewable share are fairly flat.",

        # --- Map ---
        "map_heading": "Public Charging Stations",
        "map_intro": "All public charging points from the Bundesnetzagentur's Ladesäulenregister.",
        "region_label": "Region",
        "region_all_option": "All Germany",
        "connector_type_label": "Connector type",
        "connector_legend_note": "Click a legend entry to show or hide that connector type.",
        "map_stats": "{n:,} stations shown",
        "connector_dc_ccs": "DC fast (CCS)",
        "connector_dc_chademo": "DC fast (CHAdeMO)",
        "connector_ac_type2": "AC Type 2",
        "connector_other": "Other",
    },
    "de": {
        "app_title": "EV Smart-Charging Advisor",
        "app_tagline": "Die günstigsten und grünsten Zeiten zum Laden eines E-Autos in Deutschland — auf Basis echter Netzdaten.",

        "nav_home": "Startseite",
        "nav_forecast": "Prognose",
        "nav_recommendation": "Empfehlung",
        "nav_map": "Ladekarte",

        # --- Home ---
        "home_heading": "EV Smart-Charging Advisor",
        "home_intro": (
            "Deutschlands Strompreis und Anteil erneuerbarer Energien schwanken im Tagesverlauf stark, "
            "abhängig von Wind, Sonne und Nachfrage. Dieses Tool nutzt reale historische Netzdaten von "
            "SMARD (Bundesnetzagentur), prognostiziert Preis und Erneuerbaren-Anteil für die nahe "
            "Zukunft und übersetzt das in eine einfache Empfehlung „jetzt laden / warten bis X“ — "
            "plus eine Karte öffentlicher Ladestationen."
        ),
        "home_stats_heading": "Die Daten dieser Sitzung auf einen Blick",
        "home_stat_stations": "Kartierte Ladestationen",
        "home_stat_data_range": "Zeitraum der Netzdaten",
        "home_stat_last_updated": "Aktuellster Datenpunkt",
        "home_pages_heading": "Was diese App bietet",
        "home_page_forecast": "**Prognose** — Preis- und Erneuerbaren-Anteil-Prognose für die nächsten 48h sowie ein Vergleich mit einfachen Benchmarks.",
        "home_page_recommendation": "**Empfehlung** — eine Rangliste der besten Ladefenster, gewichtbar zwischen Kosten und Grünheit.",
        "home_page_map": "**Ladekarte** — alle öffentlichen Ladestationen in Deutschland, filterbar nach Steckertyp und Region.",
        "home_attribution": "Daten: Bundesnetzagentur | SMARD.de (CC BY 4.0) sowie das Ladesäulenregister der Bundesnetzagentur.",
        "home_disclaimer": (
            "Portfolio-Projekt, keine finanzielle oder betriebliche Beratung. Die Prognosen wurden nur "
            "auf einem einzelnen 48h-Fenster zurückgetestet — siehe die Prognose-Seite für eine ehrliche "
            "Einordnung, wo das Modell einen naiven Vergleichswert schlägt (und wo nicht)."
        ),

        # --- Forecast ---
        "forecast_heading": "Preis- und Erneuerbaren-Anteil-Prognose",
        "forecast_intro": "Nächste 48 Stunden, prognostiziert aus den aktuellsten verfügbaren Netzdaten.",
        "forecast_asof": "Stand: {time}",
        "forecast_price_chart_title": "Preisprognose",
        "forecast_renewable_chart_title": "Prognose Erneuerbaren-Anteil",
        "forecast_price_axis": "EUR/MWh",
        "forecast_renewable_axis": "Erneuerbare / Last",
        "forecast_model_note_heading": "Über diese Prognose",
        "forecast_model_note_body": (
            "Der Preis ist eine 50/50-Mischung aus einem XGBoost-Modell und einem saisonalen Vergleichswert "
            "(gleiche Stunde, gleicher Wochentag, vor einer Woche). Das ist keine reine Vorsichtsmaßnahme: "
            "Ein Backtest auf einem zurückgehaltenen 48h-Fenster ergab, dass XGBoost *allein* beim Preis "
            "schlechter abschneidet als der saisonale Vergleichswert (-62% Skill) — vermutlich, weil es "
            "starke, wiederkehrende wöchentliche Preisschwankungen glättet, die der naive Vergleichswert "
            "kostenlos reproduziert. Der Erneuerbaren-Anteil nutzt ausschließlich XGBoost — hier war es das "
            "einzige Modell, das den saisonalen Vergleichswert schlug (+15% Skill). Vollständige Methodik "
            "und Backtest-Abbildungen im README des Projekts."
        ),
        "forecast_backtest_heading": "Modellvergleich (48h-Backtest)",
        "forecast_backtest_col_method": "Methode",
        "forecast_backtest_col_price_mae": "Preis-MAE (EUR/MWh)",
        "forecast_backtest_col_renewable_mae": "Erneuerbaren-Anteil-MAE",
        "method_persistence": "Naiv (Persistenz)",
        "method_seasonal": "Saisonal-naiv (t-168h)",
        "method_prophet": "Prophet",
        "method_xgboost": "XGBoost",

        # --- Recommendation ---
        "recommendation_heading": "Beste Ladefenster",
        "recommendation_intro": "Rangliste der Ladefenster für die nächsten 48 Stunden, abgewogen zwischen Kosten und Grünheit.",
        "alpha_label": "Kosten vs. Grünheit",
        "alpha_help": "0 = so günstig wie möglich, 1 = so grün wie möglich. Die Fenster werden nach einer Mischung aus beidem bewertet.",
        "alpha_cost_caption": "Günstigste",
        "alpha_green_caption": "Grünste",
        "recommendation_now": "**Jetzt laden** — gutes Fenster bis {end} ({duration}h, ø {price} EUR/MWh, {renewable} erneuerbar).",
        "recommendation_wait": "**Ca. {hours}h warten** — bestes Fenster beginnt {start}, dauert {duration}h (ø {price} EUR/MWh, {renewable} erneuerbar).",
        "windows_heading": "Rangliste der Fenster",
        "window_col_rank": "#",
        "window_col_start": "Start",
        "window_col_end": "Ende",
        "window_col_duration": "Dauer (h)",
        "window_col_price": "Ø Preis (EUR/MWh)",
        "window_col_renewable": "Ø Erneuerbaren-Anteil",
        "window_col_score": "Score",
        "no_windows_msg": "Keine herausragenden Fenster in den nächsten 48h — Preis und Erneuerbaren-Anteil sind recht flach.",

        # --- Map ---
        "map_heading": "Öffentliche Ladestationen",
        "map_intro": "Alle öffentlichen Ladepunkte aus dem Ladesäulenregister der Bundesnetzagentur.",
        "region_label": "Region",
        "region_all_option": "Ganz Deutschland",
        "connector_type_label": "Steckertyp",
        "connector_legend_note": "Klicken Sie auf einen Legendeneintrag, um den jeweiligen Steckertyp ein- oder auszublenden.",
        "map_stats": "{n:,} Stationen angezeigt",
        "connector_dc_ccs": "DC-Schnellladen (CCS)",
        "connector_dc_chademo": "DC-Schnellladen (CHAdeMO)",
        "connector_ac_type2": "AC Typ 2",
        "connector_other": "Sonstige",
    },
}


def t(key: str, lang: str, **kwargs) -> str:
    """Look up a translated string, falling back to English then the raw key
    if missing, and apply .format(**kwargs) if any are given."""
    text = TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS["en"].get(key) or key
    return text.format(**kwargs) if kwargs else text


def fmt_number(value: float, lang: str, decimals: int = 1) -> str:
    """German locale uses a comma decimal separator and period thousands
    separator; English is the reverse."""
    s = f"{value:,.{decimals}f}"
    if lang == "de":
        s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return s


def fmt_pct(value: float, lang: str, decimals: int = 0) -> str:
    return f"{fmt_number(value * 100, lang, decimals)}%"


_WEEKDAY_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def fmt_datetime(dt: pd.Timestamp, lang: str, with_weekday: bool = True) -> str:
    """Weekday abbreviations are substituted manually rather than relying on
    strftime's locale ("%a"), since that depends on the system having the
    de_DE locale installed — not guaranteed on a deployment host (e.g.
    Streamlit Community Cloud / HF Spaces), so it could silently regress to
    English there even though it works locally."""
    if lang == "de":
        fmt = "%d.%m. %H:%M" if with_weekday else "%d.%m.%Y %H:%M"
        s = dt.strftime(fmt)
        return f"{_WEEKDAY_DE[dt.weekday()]} {s}" if with_weekday else s
    fmt = "%a %H:%M" if with_weekday else "%Y-%m-%d %H:%M"
    return dt.strftime(fmt)
