"""Directed road distances with explicit snapping limits and unreachable pairs."""

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
import streamlit as st
from scipy.spatial import cKDTree

from bioze.paths import project_path


@st.cache_resource(show_spinner=False)
def load_road_graph():
    graph = ox.load_graphml(project_path("osm_network", "extracts", "G.graphml"))
    if not graph.graph.get("crs"):
        raise ValueError("Het wegennet heeft geen coördinatenstelsel.")
    for _, _, edge in graph.edges(data=True):
        length = float(edge["length"])
        if not np.isfinite(length) or length < 0:
            raise ValueError("Het wegennet bevat ongeldige afstanden.")
    return graph


def snap_points(frame, graph, max_snap_m=5000):
    points = gpd.GeoSeries(gpd.points_from_xy(frame.lon, frame.lat), index=frame.index, crs=4326)
    points = points.to_crs(graph.graph["crs"])
    nodes = list(graph.nodes)
    coordinates = np.array([[float(graph.nodes[n]["x"]), float(graph.nodes[n]["y"])] for n in nodes])
    # The supplied network uses EPSG:3857. Check snap distance in RD New, not Web Mercator.
    metric_nodes = gpd.GeoSeries(
        gpd.points_from_xy(coordinates[:, 0], coordinates[:, 1]), crs=graph.graph["crs"]
    ).to_crs(28992)
    points = points.to_crs(28992)
    distance, positions = cKDTree(np.column_stack([metric_nodes.x, metric_nodes.y])).query(
        np.column_stack([points.x, points.y])
    )
    return {i: nodes[int(p)] for i, p, d in zip(frame.index, positions, distance, strict=True) if d <= max_snap_m}


def road_distances(farms, sites, graph, max_snap_m=5000):
    sources = snap_points(farms, graph, max_snap_m)
    destinations = snap_points(sites, graph, max_snap_m)
    distances = {}
    # Reuse one Dijkstra traversal for all farms sharing a snapped origin.
    for source_node in set(sources.values()):
        lengths = nx.single_source_dijkstra_path_length(graph, source_node, weight="length")
        for farm in (i for i, n in sources.items() if n == source_node):
            for site, destination in destinations.items():
                if destination in lengths:
                    distances[site, farm] = lengths[destination] / 1000
    return distances


def calculate_distances(farms, sites):
    # Hash only the small coordinate tables, never GeoDataFrame geometry internals.
    return _cached_distances(
        pd.DataFrame(farms[["farm_id", "lon", "lat"]]),
        pd.DataFrame(sites[["site_id", "lon", "lat"]]),
    )


@st.cache_data(show_spinner=False)
def _cached_distances(farms, sites):
    return road_distances(farms.set_index("farm_id"), sites.set_index("site_id"), load_road_graph())


def distance_table(distances):
    return pd.DataFrame(
        [{"site_id": site, "farm_id": farm, "road_km": value} for (site, farm), value in distances.items()],
        columns=["site_id", "farm_id", "road_km"],
    )
