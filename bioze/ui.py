import base64
import html
import json

import h3
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from bioze.data import boundary_geojson, map_context
from bioze.paths import project_path

PALETTE = np.array([[226, 240, 229], [142, 191, 180], [67, 143, 144], [18, 83, 96]])
ACCENTS = [[224, 137, 61], [76, 121, 176], [142, 94, 146], [38, 128, 112], [190, 98, 89]]


def setup(title):
    st.set_page_config(
        page_title=f"{title} · BIOZE", page_icon=str(project_path("assets", "favicon.png")), layout="wide"
    )
    st.markdown(f"<style>{project_path('assets', 'theme.css').read_text()}</style>", unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="bioze-brand">BIOZE</div>', unsafe_allow_html=True)
        st.caption("Ruimtelijke analyse · Zuid-Holland")
        st.divider()


def header(section, title, description):
    st.markdown(f'<div class="bioze-eyebrow">{html.escape(section)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="bioze-lead">{html.escape(description)}</div>', unsafe_allow_html=True)


def footer():
    st.markdown(
        '<div class="bioze-footer">BIOZE · Zuid-Holland · GIS, multicriteria-analyse en locatieoptimalisatie · Onderzoeks- en scenariotool</div>',
        unsafe_allow_html=True,
    )


def note(text):
    st.markdown(f'<div class="bioze-note">{html.escape(text)}</div>', unsafe_allow_html=True)


def legend():
    st.markdown(
        '<div class="bioze-legend"><span>Lager · 0</span><div class="bioze-ramp"></div><span>Hoger · 1</span><span>Relatieve geschiktheid</span></div>',
        unsafe_allow_html=True,
    )


def color_scores(frame):
    result = frame.copy()
    values = np.clip(result.score.to_numpy(), 0, 1) * (len(PALETTE) - 1)
    lower = np.minimum(values.astype(int), len(PALETTE) - 2)
    fraction = values - lower
    result["color"] = (
        (PALETTE[lower] * (1 - fraction[:, None]) + PALETTE[lower + 1] * fraction[:, None]).astype(int).tolist()
    )
    result["detail"] = result.score.map(lambda value: f"Relatieve score {value:.3f}")
    result["label"] = "H3-analysecel"
    return result


@st.cache_data(show_spinner=False)
def hex_polygons(ids):
    """Exact Python H3 vertices; avoids browser H3-version/rendering incompatibilities."""
    return {cell: [[lon, lat] for lat, lon in h3.cell_to_boundary(cell)] for cell in ids}


def display_scores(scores):
    """Average only for overview rendering. Scoring, clustering and exports stay at resolution 9."""
    frame = scores[["hex9", "score"]].copy()
    frame["parent"] = frame.hex9.map(lambda cell: h3.cell_to_parent(cell, 8))
    result = frame.groupby("parent").score.agg(["mean", "count"]).reset_index()
    result = result.rename(columns={"parent": "hex9", "mean": "score", "count": "n_cells"})
    centers = result.hex9.map(h3.cell_to_latlng)
    result["lat"] = centers.map(lambda point: point[0])
    result["lon"] = centers.map(lambda point: point[1])
    return pd.DataFrame(result)


def map_deck(scores=None, sites=None, farms=None, result=None, basemap=False):
    layers = [
        pdk.Layer(
            "GeoJsonLayer",
            boundary_geojson(),
            filled=True,
            stroked=True,
            get_fill_color=[231, 239, 234, 240],
            get_line_color=[126, 161, 154],
            get_line_width=90,
            line_width_min_pixels=1,
        )
    ]
    if scores is not None and not scores.empty:
        colored = color_scores(display_scores(scores))
        colored["label"] = "H3-kaartcel · resolutie 8"
        colored["detail"] = colored.apply(
            lambda row: f"Gemiddelde score {row.score:.3f} · {row.n_cells} analysecellen", axis=1
        )
        colored["polygon"] = colored.hex9.map(hex_polygons(tuple(colored.hex9)))
        layers.append(
            pdk.Layer(
                "PolygonLayer",
                colored,
                get_polygon="polygon",
                get_fill_color="color",
                filled=True,
                stroked=False,
                opacity=0.85,
                pickable=True,
            )
        )
    roads, water = map_context()
    layers.append(
        pdk.Layer(
            "GeoJsonLayer",
            water,
            filled=True,
            stroked=False,
            get_fill_color=[206, 222, 227, 210],
        )
    )
    layers.append(
        pdk.Layer(
            "GeoJsonLayer",
            roads,
            filled=False,
            stroked=True,
            get_line_color=[235, 242, 234, 130],
            get_line_width=35,
            line_width_min_pixels=0.7,
        )
    )
    if farms is not None and not farms.empty:
        sources = farms.copy()
        sources["label"] = sources.farm_id
        sources["detail"] = "Landbouwlocatie · geen gemeten mestvolume beschikbaar"
        sources["color"] = [[74, 91, 96]] * len(sources)
        if result is not None:
            assigned = result["allocations"].groupby("farm_id").tonnes_per_year.sum()
            sources["detail"] = sources.farm_id.map(lambda i: f"Toegewezen: {assigned.get(i, 0):,.0f} ton/jaar")
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                sources,
                get_position=["lon", "lat"],
                get_radius=180,
                radius_min_pixels=3,
                get_fill_color="color",
                pickable=True,
            )
        )
    if sites is not None and not sites.empty:
        candidates = sites.copy()
        active = result["active_sites"] if result else []
        colors = {i: ACCENTS[k % len(ACCENTS)] for k, i in enumerate(active)}
        candidates["color"] = candidates.site_id.map(lambda i: colors.get(i, [113, 136, 142]))
        candidates["label"] = candidates.site_id
        candidates["detail"] = candidates.site_id.map(
            lambda i: "Geopende vergister" if i in active else "Kandidaatlocatie"
        )
        if result is not None and farms is not None:
            links = (
                result["allocations"]
                .merge(farms[["farm_id", "lon", "lat"]], on="farm_id")
                .merge(sites[["site_id", "lon", "lat"]], on="site_id", suffixes=("_farm", "_site"))
            )
            links["color"] = links.site_id.map(colors)
            links["label"] = links.farm_id + " → " + links.site_id
            links["detail"] = links.apply(
                lambda r: f"{r.tonnes_per_year:,.0f} ton/jaar · {r.road_km:.1f} km over de weg", axis=1
            )
            layers.append(
                pdk.Layer(
                    "ArcLayer",
                    links,
                    get_source_position=["lon_farm", "lat_farm"],
                    get_target_position=["lon_site", "lat_site"],
                    get_source_color="color",
                    get_target_color="color",
                    get_width=2,
                    pickable=True,
                )
            )
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                candidates,
                get_position=["lon", "lat"],
                get_radius=420,
                radius_min_pixels=6,
                get_fill_color="color",
                stroked=True,
                get_line_color=[255, 255, 255],
                line_width_min_pixels=2,
                pickable=True,
            )
        )
        layers.append(
            pdk.Layer(
                "TextLayer",
                candidates,
                get_position=["lon", "lat"],
                get_text="site_id",
                get_size=12,
                get_color=[25, 58, 61],
                get_pixel_offset=[0, -15],
            )
        )
    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(longitude=4.43, latitude=51.995, zoom=8.05, pitch=0),
        map_provider="carto" if basemap else "mapbox",
        # Streamlit 1.50 expects a string style URL. An inline data URL avoids remote tiles.
        map_style="light"
        if basemap
        else "data:application/json;base64,"
        + base64.b64encode(
            json.dumps(
                {
                    "version": 8,
                    "sources": {},
                    "layers": [{"id": "background", "type": "background", "paint": {"background-color": "#e7eef0"}}],
                }
            ).encode()
        ).decode(),
        tooltip={"html": "<b>{label}</b><br/>{detail}", "style": {"backgroundColor": "#183e42", "color": "white"}},
    )


def show_map(**kwargs):
    height = kwargs.pop("height", 550)
    st.pydeck_chart(map_deck(**kwargs), height=height, use_container_width=True)
