"""
Interactive territory map viewer.

Usage:
    streamlit run src/streamlit_app.py

Assumes the pipeline has produced data/territory_assignments.csv.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pandas as pd
import pydeck as pdk
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "territory_assignments.csv"


@st.cache_data(show_spinner=False)
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["owner_status_fallback"] = df["owner_status"].fillna("PROSPECTIVE")
    df["status_display"] = df["owner_status_fallback"].apply(
        lambda s: "ACTIVE" if s == "ACTIVE" else "PROSPECTIVE"
    )
    df["deal_count"] = df["deal_count"].fillna(0)
    df["city_lower"] = df["city"].str.lower()
    df["zip_str"] = df["zip"].astype(str)
    return df


def filter_data(df: pd.DataFrame, query: str, mode: str) -> pd.DataFrame:
    filtered = df
    if mode == "Active only":
        filtered = filtered[filtered["status_display"] == "ACTIVE"]
    elif mode == "Prospective only":
        filtered = filtered[filtered["status_display"] == "PROSPECTIVE"]

    q = query.strip().lower()
    if q:
        filtered = filtered[
            filtered["zip_str"].str.startswith(q) | filtered["city_lower"].str.contains(q)
        ]
    return filtered


def initial_view(df: pd.DataFrame) -> Tuple[float, float]:
    if df.empty:
        return 39.5, -98.35  # US centroid fallback
    return df["lat"].mean(), df["lng"].mean()


def build_layers(df: pd.DataFrame):
    active = df[df["status_display"] == "ACTIVE"]
    prospective = df[df["status_display"] == "PROSPECTIVE"]

    layers = []
    if not active.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=active,
                get_position="[lng, lat]",
                get_radius=4000,
                get_fill_color="[0, 99, 247, 160]",
                pickable=True,
                radius_min_pixels=3,
                radius_max_pixels=20,
            )
        )
    if not prospective.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=prospective,
                get_position="[lng, lat]",
                get_radius=3500,
                get_fill_color="[128, 128, 128, 140]",
                pickable=True,
                radius_min_pixels=2,
                radius_max_pixels=16,
            )
        )
    if not df.empty:
        layers.append(
            pdk.Layer(
                "HeatmapLayer",
                data=df,
                get_position="[lng, lat]",
                get_weight="deal_count",
                radius_pixels=40,
            )
        )
    return layers


def main() -> None:
    st.set_page_config(page_title="Territory Map", layout="wide")
    st.title("Territory Map Viewer")
    st.caption("Reactive ZIP-level map with active and prospective ownership.")

    if not DATA_PATH.exists():
        st.error(f"Missing data file: {DATA_PATH}. Run the pipeline first.")
        return

    df = load_data(DATA_PATH)

    col1, col2 = st.columns([2, 1])
    with col1:
        query = st.text_input("Filter by ZIP or city (live search)", "")
    with col2:
        mode = st.radio(
            "Show",
            ["All", "Active only", "Prospective only"],
            horizontal=True,
        )

    filtered = filter_data(df, query, mode)
    lat, lng = initial_view(filtered)

    st.write(f"{len(filtered):,} ZIPs displayed.")

    tooltip = {
        "html": """
            <b>ZIP:</b> {zip}<br/>
            <b>City:</b> {city}, {state_id}<br/>
            <b>Status:</b> {status_display}<br/>
            <b>Owner:</b> {owner_name} ({owner_email})<br/>
            <b>Prospective:</b> {prospective_owner_name} ({prospective_owner_email})<br/>
            <b>Deal Count:</b> {deal_count}<br/>
            <b>Reason:</b> {inference_reason}
        """,
        "style": {"backgroundColor": "steelblue", "color": "white"},
    }

    deck = pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v10",
        initial_view_state=pdk.ViewState(
            latitude=lat,
            longitude=lng,
            zoom=4,
            min_zoom=2,
            max_zoom=15,
        ),
        layers=build_layers(filtered),
        tooltip=tooltip,
    )
    st.pydeck_chart(deck, use_container_width=True)


if __name__ == "__main__":
    main()
