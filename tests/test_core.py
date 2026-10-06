from io import StringIO

import h3
import networkx as nx
import numpy as np
import pandas as pd
import pytest

from bioze.data import CRITERIA, derive_distances, load_boundary, load_cells, load_farms, read_supply_csv
from bioze.optimization import Scenario, solve_scenario
from bioze.paths import project_path
from bioze.routing import road_distances
from bioze.suitability import find_clusters, normalize, score_distances, select_candidates


def test_normalization_direction_constant_and_bad_values():
    assert normalize([0, 5, 10], "close").tolist() == [1, 0.5, 0]
    assert normalize([0, 5, 10], "far").tolist() == [0, 0.5, 1]
    assert normalize([7, 7], "far").tolist() == [0.5, 0.5]
    for values in [[float("nan")], [float("inf")], []]:
        with pytest.raises(ValueError):
            normalize(values)


def test_scoring_tracks_h3_ids_after_reordering():
    df = pd.DataFrame(
        {"hex9": ["a", "b", "c"], "lon": [4] * 3, "lat": [52] * 3, "farm": [0, 5, 10], "urban": [0, 5, 10]}
    )
    result = score_distances(df, {"farm": 3, "urban": 1}).set_index("hex9").score
    assert result.to_dict() == {"a": 0.75, "b": 0.5, "c": 0.25}
    reordered = score_distances(df.iloc[::-1], {"farm": 3, "urban": 1}).set_index("hex9").score
    pd.testing.assert_series_equal(result.sort_index(), reordered.sort_index())
    for weights in [{}, {"farm": 0}, {"farm": -1}, {"farm": float("nan")}]:
        with pytest.raises(ValueError):
            score_distances(df, weights)
    with pytest.raises(ValueError):
        score_distances(pd.concat([df, df.iloc[:1]]), {"farm": 1})


def test_supply_csv_rejects_missing_unknown_duplicate_and_nonfinite():
    assert read_supply_csv(StringIO("farm_id,tonnes_per_year\na,3\nb,4\n"), ["a", "b"]) == {"a": 3, "b": 4}
    for text in ["a,3", "a,3\na,4", "a,3\nx,4", "a,inf\nb,4", "a,-1\nb,4", "a,0\nb,0"]:
        with pytest.raises(ValueError):
            read_supply_csv(StringIO("farm_id,tonnes_per_year\n" + text), ["a", "b"])


def test_directed_routes_preserve_farm_ids_and_skip_disconnections():
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    graph.add_node(1, x=4.4, y=52)
    graph.add_node(2, x=4.5, y=52)
    graph.add_node(3, x=4.6, y=52)
    graph.add_edge(1, 2, length=1200)
    farms = pd.DataFrame({"lon": [4.4, 4.4, 4.6], "lat": [52] * 3}, index=["farm-A", "farm-B", "unreachable"])
    sites = pd.DataFrame({"lon": [4.5], "lat": [52]}, index=["site"])
    assert road_distances(farms, sites, graph, max_snap_m=10) == {("site", "farm-A"): 1.2, ("site", "farm-B"): 1.2}
    assert road_distances(sites, farms, graph, max_snap_m=10) == {}


def test_solver_capacity_flows_and_costs_agree_with_known_solution():
    scenario = Scenario(target=1, capacity=5, capex=100, annual_opex=10, transport_eur_tonne_km=2, years=2)
    result = solve_scenario(["s1", "s2"], {"f": 8}, {("s1", "f"): 1, ("s2", "f"): 3}, scenario)
    assert result["status"] == "optimal"
    assert set(result["active_sites"]) == {"s1", "s2"}
    assigned = result["allocations"].set_index("site_id").tonnes_per_year
    assert assigned.to_dict() == {"s1": 5, "s2": 3}
    assert result["processed"] == pytest.approx(8)
    assert result["mean_km"] == pytest.approx(14 / 8)
    assert result["costs"]["Transport"] == pytest.approx(56)
    assert result["total_cost"] == pytest.approx(296)
    assert result["total_cost"] == pytest.approx(sum(result["costs"].values()))
    assert result["utilization"].utilization_pct.max() <= 100 + 1e-6


def test_solver_zero_infeasible_and_invalid_scenarios():
    result = solve_scenario(["s"], {"f": 5}, {("s", "f"): 2}, Scenario(target=0))
    assert result["total_cost"] == 0 and result["processed"] == 0 and result["active_sites"] == []
    for routes, scenario in [({}, Scenario(target=1)), ({("s", "f"): 1}, Scenario(target=1, capacity=1))]:
        with pytest.raises(ValueError, match="niet haalbaar"):
            solve_scenario(["s"], {"f": 5}, routes, scenario)
    for scenario in [Scenario(target=2), Scenario(capacity=0), Scenario(capex=float("inf"))]:
        with pytest.raises(ValueError):
            solve_scenario(["s"], {"f": 5}, {("s", "f"): 1}, scenario)


def test_real_pzh_data_and_cluster_pipeline():
    cells = load_cells()
    farms = load_farms()
    df = derive_distances()
    assert len(df) == 37142 and df.hex9.is_unique
    assert len(farms) == 14
    assert farms.geometry.within(load_boundary().geometry.union_all()).all()
    assert np.isfinite(df[list(CRITERIA)].to_numpy()).all()
    assert df[list(CRITERIA)].min().min() >= 0
    assert set(df.hex9) == set(cells.hex9)
    scores = score_distances(df, {k: 1 for k in CRITERIA})
    clustered = find_clusters(scores)
    sites = select_candidates(clustered)
    assert 0 < len(sites) <= 25
    assert sites.hex9.isin(clustered.loc[clustered.high_high, "hex9"]).all()
    assert all(h3.is_valid_cell(cell) for cell in sites.hex9)
    assert project_path("osm_network", "extracts", "G.graphml").is_file()
    repeated = find_clusters(scores.iloc[::-1])
    pd.testing.assert_frame_equal(clustered, repeated)


def test_constant_scores_do_not_produce_clusters():
    df = pd.DataFrame({"hex9": [h3.latlng_to_cell(52, 4.4, 9)], "lon": [4.4], "lat": [52], "score": [0.5]})
    result = find_clusters(df)
    assert not result.high_high.any()
    assert select_candidates(result).empty
