import streamlit as st

from bioze.data import CRITERIA, derive_distances, load_farms
from bioze.suitability import score_distances
from bioze.ui import footer, header, legend, setup, show_map

setup("Overzicht")
header(
    "Decision support / Zuid-Holland",
    "Ruimte voor een betere afweging.",
    "Verken geschikte gebieden voor biogasvergisters. Combineer ruimtelijke criteria en vergelijk locaties, capaciteit en transport in één samenhangende workflow.",
)
with st.spinner("Ruimtelijke bronlagen voorbereiden…"):
    distances = derive_distances()
    farms = load_farms()
    preview = score_distances(distances, {key: 1 for key in CRITERIA})
metrics = st.columns(3)
metrics[0].metric("Gebied", "Zuid-Holland")
metrics[1].metric("Ruimtelijke criteria", len(CRITERIA))
metrics[2].metric("Analysecellen · H3 resolutie 9", f"{len(distances):,}".replace(",", "."))
left, right = st.columns([1.85, 1], gap="large")
with left:
    st.subheader("Het landschap als vertrekpunt")
    show_map(scores=preview, height=450)
    legend()
    st.caption("Kaart: gemiddelde scores op H3-resolutie 8. Analyse en export blijven op resolutie 9.")
    st.caption("Voorbeeld: gelijke weging van zes nabijheidscriteria. Een relatieve score is geen vergunningstoets.")
with right:
    st.subheader("Van analyse naar scenario")
    st.markdown(
        '<div class="bioze-card"><div class="bioze-step">01 / GESCHIKTHEID</div><h3>Weeg wat ertoe doet</h3><p>Kies criteria, pas gewichten aan en herken clusters van relatief geschikte gebieden.</p></div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_Fase_1_Geschiktheidsanalyse.py", label="Open geschiktheidsanalyse", width="stretch")
    st.markdown(
        '<div class="bioze-card"><div class="bioze-step">02 / BELEIDSVERKENNING</div><h3>Vergelijk de mogelijkheden</h3><p>Verken kandidaatlocaties met een capaciteitsmodel en afstanden over het aanwezige wegennet.</p></div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/2_Fase_2_Beleidsverkenner.py", label="Open beleidsverkenner", width="stretch")
    st.caption(
        f"{len(farms)} landbouwlocaties binnen de provinciegrens. Mestvolumes zijn scenarioaannames of eigen invoer; er zijn geen gemeten volumes meegeleverd."
    )
with st.expander("Bronnen en reikwijdte"):
    st.write(
        "Deze versie gebruikt de meegeleverde provinciegrens, het H3-grid, landbouwlocaties, het OSM-wegennet en CORINE Land Cover 2018. De scores zijn afgeleid van afstanden in meters, zonder nieuwe onderzoeksdata te verzinnen."
    )
    st.write(
        "Bos en semi-natuur is een landgebruiksindicator. Beschermde natuur, veiligheidsafstanden, netcapaciteit en vergunningen zijn aanvullende toetsen. Gasinlaten zijn niet opgenomen omdat de aanwezige gasinlaatlaag bij Twente hoort."
    )
    st.write(
        "BIOZE is oorspronkelijk ontwikkeld door Wen-Yu Chen, Johannes Flacke en Pirouz Nourian, Universiteit Twente / ITC, voor Interreg North Sea BIOZE. De Zuid-Hollandaanpassing is van Bayram Gurel."
    )
footer()
