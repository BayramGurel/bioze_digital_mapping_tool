"""Legacy CFLP adapter; active app uses bioze.optimization with explicit units."""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

CAPEX = 6089160
OPEX_12_YR = 1047200 * 12
LARGE_CAPACITY = 119547
LARGE_CAPEX = CAPEX + OPEX_12_YR


def assign_capacity_capex(sites):
    return {i: LARGE_CAPACITY for i in sites}, {i: LARGE_CAPEX for i in sites}


def flp_scip(sites, farms, d, M, f, C, p):
    from pyscipopt import Model, quicksum

    if not 0 <= p <= 1:
        raise ValueError("Target must be between zero and one.")
    if any(not np.isfinite(v) or v < 0 for values in [d, M, f, C] for v in values.values()):
        raise ValueError("Model values must be finite and nonnegative.")
    model = Model("legacy_flp")
    model.hideOutput()
    x = {(i, j): model.addVar(lb=0, vtype="C") for i in sites for j in farms if (i, j) in C}
    y = {i: model.addVar(vtype="B") for i in sites}
    for i in sites:
        model.addCons(quicksum(v for (site, _), v in x.items() if site == i) <= d[i] * y[i])
    for j in farms:
        model.addCons(quicksum(v for (_, farm), v in x.items() if farm == j) <= M[j])
    target = sum(M[j] for j in farms) * p
    model.addCons(quicksum(x.values()) == target)
    model.setObjective(
        quicksum(f[i] * y[i] for i in sites) + quicksum(C[pair] * v for pair, v in x.items()), "minimize"
    )
    model.data = x, y, f
    return model, target


def flp_get_result(model, sites, farms, d, C):
    if model.getNSols() == 0:
        raise RuntimeError("No feasible solution available.")
    x, y, fixed = model.data
    solution = model.getBestSol()
    active = [i for i in sites if model.getSolVal(solution, y[i]) > 0.5]
    flows = {pair: model.getSolVal(solution, v) for pair, v in x.items() if model.getSolVal(solution, v) > 1e-6}
    assignments = {i: [j for (site, j) in flows if site == i] for i in active}
    utilization = pd.DataFrame(
        {"utilization_pct": [sum(v for (site, _), v in flows.items() if site == i) / d[i] * 100 for i in sites]},
        index=sites,
    )
    costs = pd.DataFrame(
        {
            "Category": ["Fixed costs", "Transport costs"],
            "Value": [sum(fixed[i] for i in active), sum(C[pair] * value for pair, value in flows.items())],
        }
    )
    return costs, assignments, utilization


def store_data_to_pickle(data, folder_path, file_name):
    path = Path(folder_path) / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        pickle.dump(data, file)


def load_data_from_pickle(folder_path, file_name):
    with (Path(folder_path) / file_name).open("rb") as file:
        return pickle.load(file)
