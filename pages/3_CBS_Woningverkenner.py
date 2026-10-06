import pandas as pd
import streamlit as st

from bioze.data import load_cells
from bioze.paths import project_path
from bioze.suitability import normalize
from bioze.ui import footer, header, legend, setup, show_map

setup("CBS-woningverkenner")
header(
    "Aanvullende module / CBS",
    "Woningdata verkennen",
    "Een aparte verkenner voor CBS-indicatoren. Deze module staat los van de biogasworkflow en levert geen vergisterlocaties op.",
)
columns = {
    "aantal_eenpersoonshuishoudens": "Eenpersoonshuishoudens",
    "aantal_huurwoningen_in_bezit_woningcorporaties": "Corporatiewoningen",
    "aantal_inwoners": "Inwoners",
    "aantal_meergezins_woningen": "Meergezinswoningen",
    "aantal_niet_bewoonde_woningen": "Niet-bewoonde woningen",
    "aantal_woningen_bouwjaar_voor_1945": "Woningen van vóór 1945",
    "aantal_woningen": "Woningen",
}
paths = {k: project_path("standalone", "CBS_100-100_house", "outputs", f"{k}_h3.csv") for k in columns}
missing = [p for p in paths.values() if not p.is_file()]
if missing:
    st.info("De CBS-outputbestanden zijn niet meegeleverd. De biogasapp werkt zonder deze optionele module.")
    st.write(
        "Genereer de zeven outputs met het meegeleverde notebook standalone/CBS_100-100_house/Data_to_h3.ipynb en plaats ze in de map outputs."
    )
    with st.expander("Benodigde bestanden"):
        st.code("\n".join(p.name for p in missing), language=None)
    footer()
    st.stop()


@st.cache_data(show_spinner=False)
def load_indicator(path):
    frame = pd.read_csv(path, dtype={"hex9": str})
    if not {"hex9", "value"}.issubset(frame) or frame.hex9.duplicated().any():
        raise ValueError("CBS-outputs moeten unieke hex9-ID's en een value-kolom bevatten.")
    return frame[["hex9", "value"]]


try:
    key = st.selectbox("Indicator", list(columns), format_func=columns.get)
    raw = load_indicator(str(paths[key]))
    data = load_cells()[["hex9", "lon", "lat"]].merge(raw, on="hex9", how="inner", validate="one_to_one")
    if data.empty:
        raise ValueError("De indicator heeft geen H3-cellen binnen het aanwezige Zuid-Hollandgrid.")
    data["score"] = normalize(pd.to_numeric(data.value), "far")
    st.caption(
        f"{len(data):,} overlappende cellen. Kleur toont de relatieve indicatorwaarde, geen geschiktheidsoordeel."
    )
    show_map(scores=data)
    legend()
    st.download_button("Download indicator", data.to_csv(index=False), "bioze_cbs_indicator.csv", "text/csv")
except (ValueError, OSError, pd.errors.ParserError) as exc:
    st.error(str(exc))
footer()
