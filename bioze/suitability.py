"""H3-aligned scoring and reproducible Local Moran high-high cluster selection."""

import h3
import networkx as nx
import numpy as np
import pandas as pd
import streamlit as st
from esda import Moran_Local
from libpysal.weights import W

from bioze.data import CRITERIA


def normalize(values, direction="close"):
    values = np.asarray(values, dtype=float)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("Normalisatie vereist eindige, niet-lege waarden.")
    if direction not in {"close", "far"}:
        raise ValueError("De richting moet close of far zijn.")
    extent = np.ptp(values)
    if extent == 0:
        return np.full(values.shape, 0.5)  # no discrimination, direction-neutral
    result = (values - values.min()) / extent
    return 1 - result if direction == "close" else result


def score_distances(distances, weights):
    if distances.hex9.duplicated().any():
        raise ValueError("Scoring vereist unieke H3-ID's.")
    if not weights or set(weights) - set(CRITERIA):
        raise ValueError("Selecteer geldige criteria.")
    weight_values = np.asarray(list(weights.values()), dtype=float)
    if not np.isfinite(weight_values).all() or (weight_values < 0).any() or weight_values.sum() <= 0:
        raise ValueError("De som van de niet-negatieve gewichten moet groter dan nul zijn.")
    result = distances[["hex9", "lon", "lat"]].copy()
    arrays = []
    for key in weights:
        # Each column shares the same H3-keyed source table; no positional joins across CSVs.
        arrays.append(normalize(distances[key], CRITERIA[key][1]))
    result["score"] = np.average(arrays, axis=0, weights=weight_values)
    return result


@st.cache_resource(show_spinner=False)
def spatial_weights(cells):
    ids = tuple(cells)
    available = set(ids)
    neighbors = {cell: sorted((set(h3.grid_disk(cell, 1)) - {cell}) & available) for cell in ids}
    return W(neighbors, id_order=list(ids), silence_warnings=True)


@st.cache_data(show_spinner=False)
def find_clusters(scores, permutations=999, significance=0.01):
    if not 0 < significance < 1 or permutations < 99:
        raise ValueError("Gebruik minstens 99 permutaties en een geldige significantiedrempel.")
    result = scores.sort_values("hex9").reset_index(drop=True).copy()
    result["high_high"] = False
    result["p_value"] = 1.0
    if len(result) < 4 or np.ptp(result.score) < 1e-12:
        return result
    w = spatial_weights(tuple(result.hex9))
    lisa = Moran_Local(
        result.score.to_numpy(),
        w,
        permutations=permutations,
        seed=42,
        n_jobs=1,
        keep_simulations=False,
    )
    result["p_value"] = lisa.p_sim
    result["high_high"] = (lisa.q == 1) & (lisa.p_sim < significance)
    result.loc[result.hex9.isin(w.islands), "high_high"] = False
    return result


def select_candidates(clustered, maximum=25, min_distance_m=3000):
    """One highest-scoring representative per HH component, spatially spread thereafter."""
    import geopandas as gpd

    high = clustered.loc[clustered.high_high].set_index("hex9")
    if high.empty:
        return pd.DataFrame(columns=["hex9", "lon", "lat", "score", "site_id"])
    graph = nx.Graph()
    graph.add_nodes_from(high.index)
    ids = set(high.index)
    for cell in ids:
        graph.add_edges_from((cell, other) for other in set(h3.grid_disk(cell, 1)) & ids if other != cell)
    representatives = []
    for component in nx.connected_components(graph):
        group = high.loc[sorted(component)].sort_values(["score"], ascending=False, kind="stable")
        representatives.append(group.index[0])
    # Large contiguous clusters can contain several alternative sites; select a bounded shortlist.
    ranking = high.sort_values("score", ascending=False, kind="stable").index.tolist()
    representatives.sort(key=lambda cell: (-high.loc[cell, "score"], cell))
    points = gpd.GeoSeries(gpd.points_from_xy(high.lon, high.lat), index=high.index, crs=4326).to_crs(28992)
    chosen = []
    for cell in list(dict.fromkeys(representatives + ranking)):
        if all(points.loc[cell].distance(points.loc[other]) >= min_distance_m for other in chosen):
            chosen.append(cell)
        if len(chosen) >= maximum:
            break
    result = high.loc[chosen].reset_index()
    result["site_id"] = [f"V{i:02d}" for i in range(1, len(result) + 1)]
    return result
