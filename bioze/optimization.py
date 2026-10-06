"""Capacitated facility location: tonnes/year and undiscounted lifetime euros."""

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Scenario:
    target: float = 0.5
    capacity: float = 119547
    capex: float = 6089160
    annual_opex: float = 1047200
    transport_eur_tonne_km: float = 0.69
    years: int = 12
    time_limit: int = 30

    def validate(self):
        if not 0 <= self.target <= 1:
            raise ValueError("De doelstelling moet tussen 0 en 100% liggen.")
        fields = [self.capacity, self.capex, self.annual_opex, self.transport_eur_tonne_km, self.years, self.time_limit]
        if not all(math.isfinite(v) for v in fields) or any(v < 0 for v in fields):
            raise ValueError("Gebruik eindige, niet-negatieve scenarioaannames.")
        if self.capacity <= 0 or self.years <= 0 or self.time_limit <= 0:
            raise ValueError("Capaciteit, looptijd en rekentijd moeten positief zijn.")


def solve_scenario(site_ids, supply, distances, scenario):
    scenario.validate()
    site_ids = list(site_ids)
    if len(site_ids) != len(set(site_ids)) or not site_ids:
        raise ValueError("Selecteer minstens één unieke kandidaatlocatie.")
    if not supply or not all(math.isfinite(v) and v >= 0 for v in supply.values()) or sum(supply.values()) <= 0:
        raise ValueError("Gebruik geldige volumes met een positief totaal.")
    if any(not math.isfinite(d) or d < 0 for d in distances.values()):
        raise ValueError("Transportafstanden moeten eindig en niet-negatief zijn.")
    target = sum(supply.values()) * scenario.target
    routes = {(i, j): d for (i, j), d in distances.items() if i in site_ids and j in supply}
    reachable_supply = sum(supply[j] for j in supply if any(farm == j for _, farm in routes))
    if target > min(reachable_supply, len(site_ids) * scenario.capacity) + 1e-6:
        raise ValueError("De doelstelling is niet haalbaar met deze capaciteit en bereikbare landbouwlocaties.")
    try:
        from pyscipopt import Model, quicksum
    except (ImportError, OSError) as exc:
        raise RuntimeError("De optimalisatiesolver ontbreekt. Installeer requirements-solver.txt.") from exc
    model = Model("BIOZE_CFLP")
    model.hideOutput()
    model.setRealParam("limits/time", float(scenario.time_limit))
    model.setIntParam("randomization/randomseedshift", 42)
    flows = {pair: model.addVar(lb=0, vtype="C", name=f"flow_{k}") for k, pair in enumerate(routes)}
    opened = {i: model.addVar(vtype="B", name=f"open_{i}") for i in site_ids}
    for i in site_ids:
        model.addCons(quicksum(x for (site, _), x in flows.items() if site == i) <= scenario.capacity * opened[i])
    for j, amount in supply.items():
        model.addCons(quicksum(x for (_, farm), x in flows.items() if farm == j) <= amount)
    model.addCons(quicksum(flows.values()) == target)
    fixed_cost = scenario.capex + scenario.annual_opex * scenario.years
    model.setObjective(
        quicksum(fixed_cost * y for y in opened.values())
        + quicksum(routes[pair] * scenario.transport_eur_tonne_km * scenario.years * x for pair, x in flows.items()),
        "minimize",
    )
    model.optimize()
    status = str(model.getStatus())
    if model.getNSols() == 0:
        raise RuntimeError(f"Er is geen haalbare oplossing gevonden binnen de rekentijd ({status}).")
    solution = model.getBestSol()
    active = [i for i, variable in opened.items() if model.getSolVal(solution, variable) > 0.5]
    records = []
    for pair, variable in flows.items():
        volume = model.getSolVal(solution, variable)
        if volume > 1e-6:
            records.append({"site_id": pair[0], "farm_id": pair[1], "tonnes_per_year": volume, "road_km": routes[pair]})
    allocations = pd.DataFrame(records, columns=["site_id", "farm_id", "tonnes_per_year", "road_km"])
    transported = float(allocations.tonnes_per_year.sum())
    tonne_km = float((allocations.tonnes_per_year * allocations.road_km).sum())
    costs = {
        "Investering": len(active) * scenario.capex,
        "Exploitatie": len(active) * scenario.annual_opex * scenario.years,
        "Transport": tonne_km * scenario.transport_eur_tonne_km * scenario.years,
    }
    objective = float(model.getSolObjVal(solution))
    if not math.isclose(sum(costs.values()), objective, rel_tol=1e-7, abs_tol=0.01):
        raise RuntimeError("De kostencontrole van de oplossing is mislukt.")
    utilization = (
        allocations.groupby("site_id")
        .tonnes_per_year.sum()
        .reindex(active, fill_value=0)
        .rename("tonnes_per_year")
        .reset_index()
    )
    utilization["utilization_pct"] = utilization.tonnes_per_year / scenario.capacity * 100
    return {
        "status": status,
        "gap": float(model.getGap()),
        "active_sites": active,
        "allocations": allocations,
        "utilization": utilization,
        "costs": costs,
        "total_cost": objective,
        "processed": transported,
        "mean_km": tonne_km / transported if transported else 0,
        "reachable_supply": reachable_supply,
    }
