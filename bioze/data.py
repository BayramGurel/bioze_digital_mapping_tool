"""Load and derive distances from the original South-Holland source layers."""

import json

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import streamlit as st
from shapely import STRtree

from bioze.paths import project_path

CRITERIA = {
    "farm": ("Landbouwlocaties", "close", "Nabij de aanwezige landbouwlocaties"),
    "road": ("Wegennet", "close", "Nabij het geselecteerde OSM-wegennet"),
    "industry": ("Industrie en voorzieningen", "close", "Nabij CORINE-klasse 121"),
    "urban": ("Woongebieden", "far", "Verder van CORINE-klassen 111 en 112"),
    "nature": ("Bos en semi-natuur", "far", "Verder van CORINE-klassen 3xx; geen Natura 2000-toets"),
    "water": ("Water", "far", "Verder van CORINE-klassen 5xx"),
}
CORINE_PATH = project_path(
    "standalone",
    "corine_data_landcover",
    "extracts",
    "South-Holland",
    "U2018_CLC2018_V2020_20u1.gpkg",
)


@st.cache_data(show_spinner=False)
def load_boundary():
    return gpd.read_file(project_path("data", "pzh.geojson")).to_crs(4326)


@st.cache_data(show_spinner=False)
def boundary_geojson():
    boundary = load_boundary().to_crs(28992)
    boundary.geometry = boundary.geometry.simplify(100, preserve_topology=True)
    return json.loads(boundary.to_crs(4326).to_json())


@st.cache_data(show_spinner=False)
def map_context():
    """Lightweight real road and water context for the tile-free map."""
    roads = gpd.read_file(project_path("osm_network", "extracts", "G_e.shp")).to_crs(28992)
    roads.geometry = roads.geometry.simplify(60, preserve_topology=True)
    cover = gpd.read_file(CORINE_PATH).to_crs(28992)
    water = cover.loc[cover.Code_18.astype(int).between(500, 599), ["geometry"]].copy()
    water.geometry = water.geometry.simplify(75, preserve_topology=True)
    water.geometry = water.geometry.intersection(load_boundary().to_crs(28992).geometry.union_all())
    water = water.loc[~water.geometry.is_empty]
    return json.loads(roads[["geometry"]].to_crs(4326).to_json()), json.loads(water.to_crs(4326).to_json())


@st.cache_data(show_spinner=False)
def load_cells():
    cells = gpd.read_file(project_path("app_data", "h3_pzh_polygons.shp")).to_crs(4326)
    if cells.hex9.duplicated().any() or not cells.hex9.map(h3.is_valid_cell).all():
        raise ValueError("Het H3-grid bevat ongeldige of dubbele cel-ID's.")
    # Derive centers from H3, never use x/y columns of a projected shapefile as lon/lat.
    coordinates = cells.hex9.map(h3.cell_to_latlng)
    cells["lat"] = coordinates.map(lambda p: p[0])
    cells["lon"] = coordinates.map(lambda p: p[1])
    return cells.sort_values("hex9").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_farms():
    farms = gpd.read_file(project_path("farm", "pzh_farms.shp")).to_crs(4326)
    farms = farms.loc[farms.geometry.within(load_boundary().geometry.union_all())].copy()
    farms["farm_id"] = farms["id"].astype(str)
    if farms.farm_id.duplicated().any():
        raise ValueError("Landbouwlocaties hebben geen unieke identificatie.")
    farms["lon"], farms["lat"] = farms.geometry.x, farms.geometry.y
    return farms.reset_index(drop=True)


def nearest_distances(points, geometries):
    """Nearest distance in the input CRS units. No artificial fill for missing data."""
    valid = [g for g in geometries if g is not None and not g.is_empty]
    if not valid:
        raise ValueError("De bronlaag bevat geen bruikbare geometrie.")
    _, distances = STRtree(valid).query_nearest(points, return_distance=True, all_matches=False)
    if len(distances) != len(points):
        raise ValueError("Niet voor elke cel kon een afstand worden bepaald.")
    return distances


@st.cache_data(show_spinner=False)
def derive_distances():
    """Euclidean distances in metres, in the Dutch RD New projection (EPSG:28992)."""
    cells = load_cells()
    points = gpd.GeoSeries(gpd.points_from_xy(cells.lon, cells.lat), crs=4326).to_crs(28992)
    farms = load_farms().to_crs(28992)
    roads = gpd.read_file(project_path("osm_network", "extracts", "G_e.shp")).to_crs(28992)
    cover = gpd.read_file(CORINE_PATH).to_crs(28992)
    codes = cover["Code_18"].astype(int)
    layers = {
        "farm": farms.geometry,
        "road": roads.geometry,
        "industry": cover.loc[codes == 121].geometry,
        "urban": cover.loc[codes.isin([111, 112])].geometry,
        "nature": cover.loc[codes.between(300, 399)].geometry,
        "water": cover.loc[codes.between(500, 599)].geometry,
    }
    result = cells[["hex9", "lon", "lat"]].copy()
    for key, geometries in layers.items():
        result[key] = np.round(nearest_distances(points.to_numpy(), geometries), 2)
    return result


def read_supply_csv(file, farm_ids):
    """Validate explicit annual supplies; reject mismatches and incomplete coverage."""
    df = pd.read_csv(file, dtype={"farm_id": str})
    if not {"farm_id", "tonnes_per_year"}.issubset(df):
        raise ValueError("Gebruik de kolommen farm_id en tonnes_per_year.")
    if df.farm_id.duplicated().any() or set(df.farm_id) != set(farm_ids):
        raise ValueError("Het bestand moet elke landbouwlocatie precies één keer bevatten.")
    quantities = pd.to_numeric(df.tonnes_per_year, errors="coerce")
    if not np.isfinite(quantities).all() or (quantities < 0).any() or quantities.sum() <= 0:
        raise ValueError("Volumes moeten eindig en niet-negatief zijn, met een positief totaal.")
    return dict(zip(df.farm_id, quantities, strict=True))
