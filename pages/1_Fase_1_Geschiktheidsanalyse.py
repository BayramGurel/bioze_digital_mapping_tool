import pandas as pd
import streamlit as st

from bioze.data import CRITERIA, derive_distances
from bioze.suitability import find_clusters, score_distances, select_candidates
from bioze.ui import footer, header, legend, note, setup, show_map

setup("Geschiktheidsanalyse")
header(
    "Fase 01 / Ruimtelijke afweging",
    "Waar liggen de mogelijkheden?",
    "Combineer nabijheid tot infrastructuur en landbouw met afstand tot woongebieden, water en semi-natuur. Onderzoek de kaart en selecteer kandidaten uit ruimtelijke clusters.",
)
with st.sidebar:
    st.subheader("Criteria en gewichten")
    selected = st.multiselect(
        "Criteria",
        list(CRITERIA),
        default=st.session_state.get("saved_criteria", list(CRITERIA)),
        format_func=lambda key: CRITERIA[key][0],
    )
    previous_weights = st.session_state.get("saved_weights", {})
    weights = {
        key: st.slider(CRITERIA[key][0], 0, 5, previous_weights.get(key, 1), key=f"weight_{key}", help=CRITERIA[key][2])
        for key in selected
    }
    st.session_state.saved_criteria = selected
    st.session_state.saved_weights = weights
    st.caption("0 = geen bijdrage · 5 = zwaarste bijdrage")
    st.divider()
    basemap = st.toggle(
        "Online achtergrondkaart",
        value=False,
        help="CARTO / OpenStreetMap; internet vereist. De analysekaart werkt ook zonder kaarttegels.",
    )
fingerprint = tuple(sorted(weights.items()))
if st.session_state.get("analysis_fingerprint") != fingerprint:
    for key in ["clustered", "candidates", "analysis_scores", "policy_result", "policy_signature"]:
        st.session_state.pop(key, None)
    st.session_state.analysis_fingerprint = fingerprint
if not weights or sum(weights.values()) == 0:
    st.info("Selecteer minstens één criterium met een gewicht groter dan nul.")
    st.stop()
with st.spinner("Afstanden en relatieve scores berekenen…"):
    distances = derive_distances()
    scores = score_distances(distances, weights)
st.session_state.analysis_scores = scores
cols = st.columns(4)
cols[0].metric("Analysecellen", f"{len(scores):,}".replace(",", "."))
cols[1].metric("Actieve criteria", sum(w > 0 for w in weights.values()))
cols[2].metric("Gemiddelde score", f"{scores.score.mean():.2f}")
cols[3].metric("Kandidaatlocaties", len(st.session_state.get("candidates", [])))
map_tab, criteria_tab, result_tab = st.tabs(["Geschiktheidskaart", "Criteria vergelijken", "Clusters en export"])
with map_tab:
    st.subheader("Relatieve geschiktheid")
    show_map(scores=scores, sites=st.session_state.get("candidates"), basemap=basemap, height=545)
    legend()
    st.caption("Kaart: gemiddelde scores op H3-resolutie 8. Analyse en export blijven op resolutie 9.")
    note(
        "De score loopt van 0 tot 1 binnen dit studiegebied. Een hoge score is een startpunt voor onderzoek; een locatie is daarmee nog niet planologisch of technisch geschikt."
    )
with criteria_tab:
    chosen = st.selectbox("Bekijk één criterium", selected, format_func=lambda k: CRITERIA[k][0])
    st.caption(CRITERIA[chosen][2] + ". Min-maxnormalisatie op basis van afstand in meters.")
    show_map(scores=score_distances(distances, {chosen: 1}), basemap=basemap, height=480)
    legend()
    st.caption("Kaart: gemiddelde scores op H3-resolutie 8. Analyse en export blijven op resolutie 9.")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Criterium": CRITERIA[k][0],
                    "Voorkeur": "Dichtbij" if CRITERIA[k][1] == "close" else "Verder weg",
                    "Gewicht": v,
                    "Aandeel (%)": round(100 * v / sum(weights.values()), 1),
                }
                for k, v in weights.items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )
with result_tab:
    st.subheader("Van scores naar kandidaatlocaties")
    st.write(
        "Local Moran’s I selecteert high-highclusters: relatief hoge scores met hoge scores in de aangrenzende H3-cellen. We gebruiken 999 permutaties, seed 42 en p < 0,01. Dit is een verkennende toets zonder correctie voor meervoudig toetsen."
    )
    st.caption(
        "Shortlist: maximaal 25 locaties, eerst de hoogst scorende cel per cluster, daarna aanvullende cellen; minimaal 3 km onderlinge afstand. De optimalisatie is beperkt tot deze shortlist."
    )
    if st.button("Bereken clusters en kandidaten", type="primary"):
        with st.spinner("Ruimtelijke clusters toetsen…"):
            clustered = find_clusters(scores)
            st.session_state.clustered = clustered
            st.session_state.candidates = select_candidates(clustered)
            st.session_state.pop("policy_result", None)
        st.rerun()
    if "clustered" in st.session_state:
        clustered = st.session_state.clustered
        candidates = st.session_state.candidates
        st.caption(f"{int(clustered.high_high.sum()):,} high-highcellen · {len(candidates)} kandidaatlocaties")
        if candidates.empty:
            st.info("Deze gewichten leveren geen significante high-highclusters op. Pas de weging aan.")
        else:
            st.dataframe(candidates[["site_id", "hex9", "score", "lon", "lat"]], hide_index=True, width="stretch")
            st.download_button(
                "Download kandidaatlocaties", candidates.to_csv(index=False), "bioze_kandidaten.csv", "text/csv"
            )
            st.page_link("pages/2_Fase_2_Beleidsverkenner.py", label="Verder naar de beleidsverkenner")
    st.download_button(
        "Download scores en bronafstanden",
        scores.merge(distances, on=["hex9", "lon", "lat"]).to_csv(index=False),
        "bioze_geschiktheid.csv",
        "text/csv",
    )
with st.expander("Rekenmethode en bronnen"):
    st.write(
        "Afstanden worden berekend vanaf H3-celcentra in RD New (EPSG:28992). Elk criterium wordt naar 0–1 genormaliseerd; daarna volgt het gewogen gemiddelde. Bij een constante bronwaarde is de score neutraal: 0,5. Het H3-ID bepaalt steeds de koppeling."
    )
    st.write(
        "Landgebruik: CORINE 2018; industrie/voorzieningen 121, woongebieden 111/112, bos/semi-natuur 3xx, water 5xx. De CORINE-bron is relatief grof en vervangt geen detailonderzoek. Landbouw: alleen de meegeleverde locaties binnen de provinciegrens. Wegen: aanwezig OSM-extract, geen volledig actueel fijnmazig wegennet."
    )
footer()
