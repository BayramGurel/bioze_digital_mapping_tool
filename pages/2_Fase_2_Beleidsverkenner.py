import json
from dataclasses import asdict

import pandas as pd
import plotly.express as px
import streamlit as st

from bioze.data import load_farms, read_supply_csv
from bioze.optimization import Scenario, solve_scenario
from bioze.routing import calculate_distances, distance_table
from bioze.ui import footer, header, note, setup, show_map

setup("Beleidsverkenner")
header(
    "Fase 02 / Locatiescenario",
    "Van kansrijk gebied naar een scenario.",
    "Verken welke vergisterlocaties een gekozen hoeveelheid mest kunnen verwerken. Het model weegt investering, exploitatie en transport over het wegennet af.",
)
sites = st.session_state.get("candidates")
if sites is None or sites.empty:
    st.info("Bereken eerst clusters en kandidaatlocaties in de geschiktheidsanalyse.")
    st.page_link("pages/1_Fase_1_Geschiktheidsanalyse.py", label="Naar de geschiktheidsanalyse")
    footer()
    st.stop()
farms = load_farms()
with st.sidebar:
    st.subheader("Scenario instellen")
    with st.expander("Kandidaatlocaties aanpassen"):
        chosen = st.multiselect("Kandidaatlocaties", sites.site_id.tolist(), default=sites.site_id.tolist())
    st.caption(f"{len(chosen)} kandidaten in dit scenario")
    target = st.slider("Te verwerken aandeel (%)", 0, 100, 50, step=5)
    mode = st.radio("Herkomst mestvolumes", ["Scenarioaanname", "Eigen CSV"])
    supply = None
    if mode == "Scenarioaanname":
        amount = st.number_input("Ton per landbouwlocatie per jaar", min_value=1, value=2500, step=100)
        st.caption("Hypothetische, gelijke volumes. Dit zijn geen gemeten bedrijfsgegevens.")
        acknowledged = st.checkbox("Gebruik deze scenarioaanname")
        if acknowledged:
            supply = {i: float(amount) for i in farms.farm_id}
    else:
        uploaded = st.file_uploader("Mestvolumes per locatie", type=["csv"])
        if uploaded is not None:
            try:
                supply = read_supply_csv(uploaded, farms.farm_id)
            except (ValueError, pd.errors.ParserError) as exc:
                st.error(str(exc))
        st.download_button(
            "Download invoersjabloon",
            pd.DataFrame({"farm_id": farms.farm_id, "tonnes_per_year": [None] * len(farms)}).to_csv(index=False),
            "bioze_mestvolumes.csv",
            "text/csv",
        )
    with st.expander("Capaciteit en kosten"):
        capacity = st.number_input("Capaciteit per vergister (ton/jaar)", min_value=1, value=119547, step=1000)
        capex = st.number_input("Investering per vergister (€)", min_value=0, value=6089160, step=100000)
        opex = st.number_input("Exploitatie per vergister (€/jaar)", min_value=0, value=1047200, step=10000)
        rate = st.number_input("Transport (€/ton/km)", min_value=0.0, value=0.69, step=0.05)
        years = st.number_input("Looptijd (jaar)", min_value=1, max_value=50, value=12)
        st.caption(
            "Startwaarden uit het oude prototype, toegepast als wijzigbare aannames. De transporteenheid is nu expliciet €/ton/km; valideer deze in een praktijkscenario."
        )
    basemap = st.toggle("Online achtergrondkaart", value=False)
    run = st.button("Bereken scenario", type="primary", disabled=supply is None or not chosen, width="stretch")
selected_sites = sites.loc[sites.site_id.isin(chosen)].copy()
scenario = Scenario(
    target=target / 100, capacity=capacity, capex=capex, annual_opex=opex, transport_eur_tonne_km=rate, years=years
)
signature = json.dumps(
    {
        "sites": selected_sites[["site_id", "hex9"]].values.tolist(),
        "supply": supply,
        "scenario": asdict(scenario),
        "source": mode,
    },
    sort_keys=True,
)
if st.session_state.get("policy_signature") != signature:
    st.session_state.pop("policy_result", None)
if run:
    try:
        with st.spinner("Wegafstanden berekenen en scenario optimaliseren…"):
            distances = calculate_distances(farms, selected_sites)
            result = solve_scenario(chosen, supply, distances, scenario)
            st.session_state.policy_result = result
            st.session_state.policy_signature = signature
            st.session_state.policy_distances = distances
    except (ValueError, RuntimeError, OSError) as exc:
        st.error(str(exc))
result = st.session_state.get("policy_result")
if result:
    metrics = st.columns(4)
    metrics[0].metric("Geopende vergisters", len(result["active_sites"]))
    metrics[1].metric("Verwerkt per jaar", f"{result['processed']:,.0f}".replace(",", ".") + " ton")
    metrics[2].metric(
        f"Totale kosten · {years} jaar", "€ " + f"{result['total_cost'] / 1e6:.2f}".replace(".", ",") + " mln"
    )
    metrics[3].metric("Gem. gewogen wegafstand", f"{result['mean_km']:.1f}".replace(".", ",") + " km")
    if result["status"] == "optimal":
        st.caption("Optimale oplossing binnen de gekozen shortlist en scenarioaannames.")
    else:
        st.warning(f"Haalbare tussenoplossing: {result['status']}; optimaliteitsafstand {result['gap']:.1%}.")
else:
    metrics = st.columns(3)
    metrics[0].metric("Kandidaatlocaties", len(selected_sites))
    metrics[1].metric("Landbouwlocaties", len(farms))
    metrics[2].metric("Verwerkingsdoel", f"{target}%")
    st.caption("Kies de invoer in het zijpaneel en bereken een scenario om de toewijzingen te bekijken.")
map_tab, results_tab, assumptions_tab = st.tabs(["Locaties en stromen", "Resultaten", "Aannames en invoer"])
with map_tab:
    show_map(sites=selected_sites, farms=farms, result=result, basemap=basemap, height=540)
    st.caption(
        "Kleine stippen: landbouwlocaties · V01, V02…: kandidaten · gekleurde vergisters: geopend · bogen: toewijzingen, geen getekende rijroutes. Afstanden worden over het gerichte wegennet berekend."
    )
    note(
        "Scenarioberekening, geen beleidsadvies. Mestvolumes en kosten zijn aannames tenzij je zelf een onderbouwde invoer hebt aangeleverd."
    )
with results_tab:
    if not result:
        st.info("Bereken een scenario om capaciteit, kosten en transportstromen te bekijken.")
    else:
        left, right = st.columns(2)
        with left:
            st.subheader("Kosten over de looptijd")
            costs = pd.DataFrame({"Categorie": result["costs"].keys(), "Euro": result["costs"].values()})
            fig = px.bar(
                costs,
                x="Categorie",
                y="Euro",
                color="Categorie",
                color_discrete_sequence=["#207c7f", "#86afa4", "#d69a62"],
            )
            fig.update_layout(
                showlegend=False, height=310, margin=dict(l=0, r=0, t=15, b=0), yaxis_title="Euro · niet verdisconteerd"
            )
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.subheader("Capaciteitsbenutting")
            fig = px.bar(
                result["utilization"],
                x="site_id",
                y="utilization_pct",
                range_y=[0, 100],
                color_discrete_sequence=["#207c7f"],
            )
            fig.update_layout(
                height=310, margin=dict(l=0, r=0, t=15, b=0), xaxis_title="Vergister", yaxis_title="Benutting (%)"
            )
            st.plotly_chart(fig, use_container_width=True)
        st.subheader("Jaarlijkse transportstromen")
        st.dataframe(
            result["allocations"].rename(
                columns={
                    "site_id": "Vergister",
                    "farm_id": "Landbouwlocatie",
                    "tonnes_per_year": "Ton/jaar",
                    "road_km": "Wegafstand (km)",
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Download transportstromen",
            result["allocations"].to_csv(index=False),
            "bioze_transportstromen.csv",
            "text/csv",
        )
        report = {
            "parameters": asdict(scenario),
            "supply_source": mode,
            "supply": supply,
            "sites": selected_sites[["site_id", "hex9"]].to_dict("records"),
            "status": result["status"],
            "gap": result["gap"],
            "costs": result["costs"],
            "processed_tonnes_per_year": result["processed"],
            "mean_road_km": result["mean_km"],
        }
        st.download_button(
            "Download scenariorapport", json.dumps(report, indent=2), "bioze_scenario.json", "application/json"
        )
        st.download_button(
            "Download wegafstanden",
            distance_table(st.session_state.policy_distances).to_csv(index=False),
            "bioze_wegafstanden.csv",
            "text/csv",
        )
with assumptions_tab:
    st.write(
        "Het capacitated facility location model verdeelt tonnen per jaar over geopende vergisters. De doelstelling wordt exact gehaald; splitsing van één bron over meerdere vergisters is toegestaan. Onbereikbare verbindingen worden niet opgenomen."
    )
    st.write(
        "Totale kosten = investering + jaarlijkse exploitatie × looptijd + som(ton/jaar × weg-km × €/ton/km × looptijd). Geen verdiscontering, retourritten, aansluittrajecten vanaf het bedrijf of opbrengsten. De kosten in de grafiek zijn gelijk aan de solverdoelfunctie."
    )
    st.write(
        "Locaties worden maximaal 5 km van een netwerkknoop gekoppeld, gemeten in RD New. Alleen gerichte, bereikbare wegverbindingen tellen mee. Het extract is grof; landbouwlocaties buiten de provincie en ontbrekende of te verre aansluitingen worden uitgesloten."
    )
    st.dataframe(farms[["farm_id", "Bedrijfsty", "lon", "lat"]], hide_index=True, width="stretch")
footer()
