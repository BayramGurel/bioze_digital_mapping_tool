# BIOZE · Zuid-Holland

Een Streamlit-app voor ruimtelijke geschiktheidsanalyse en locatieoptimalisatie van biogasvergisters. Deze versie herstelt de Zuid-Hollandworkflow en maakt de herkomst van gegevens, aannames en resultaten expliciet.

Oorspronkelijk BIOZE: **Wen-Yu Chen, Johannes Flacke en Pirouz Nourian**, Universiteit Twente / ITC, Interreg North Sea BIOZE. Zuid-Hollandaanpassing: **Bayram Gurel**, Provincie Zuid-Holland. De oorspronkelijke MIT-licentie, `CITATION.cff` en onderzoeksnotebooks zijn behouden. [Oorspronkelijk onderzoek / DOI](https://zenodo.org/doi/10.5281/zenodo.10782927).

## Installeren en starten

Getest met **Python 3.12 op Linux**. Gebruik voor reproduceerbaarheid de volledige lockfile. De commando's hieronder werken ook in PowerShell; de Windowsinstallatie zelf is in deze omgeving niet getest.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m streamlit run Home.py
```

Daarna kun je dubbelklikken op `start.bat`. Open de app op `http://localhost:8501`.

Linux/macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
./start.sh
```

Zonder solver kun je Fase 1 gebruiken met `requirements.txt`. Installeer `requirements-solver.txt` voor Fase 2. `requirements-dev.txt` bevat ook pytest en Ruff. PySCIPOpt is op Linux via een wheel geïnstalleerd; als voor je platform geen geschikte wheel bestaat, volg de [officiële installatie-instructies](https://pyscipopt.readthedocs.io/en/stable/install.html).

Start de app via `Home.py`, zodat de paginanavigatie en gedeelde sessie werken. De gegevenspaden zijn onafhankelijk van de huidige working directory. De meegeleverde bronbestanden moeten bij de code blijven.

## Workflow

1. Open **Geschiktheidsanalyse**. Kies criteria en gewichten in de sidebar.
2. Bekijk de samengestelde kaart of vergelijk één criterium. De score is relatief, tussen 0 en 1.
3. Open **Clusters en export** en klik **Bereken clusters en kandidaten**.
4. Ga door naar **Beleidsverkenner**. Selecteer kandidaten en het te verwerken aandeel.
5. Kies expliciet een gelijke, hypothetische mesthoeveelheid per landbouwlocatie, of upload een CSV met volumes. Het invoersjabloon bevat de juiste IDs en lege volumes.
6. Pas capaciteit/kosten aan en klik **Bereken scenario**. Bekijk de kaart, kosten, capaciteitsbenutting en transportstromen. Exporteer CSV's en een JSON-scenariorapport.

Bij gewijzigde criteria vervallen oude kandidaten en scenarioresultaten. Bij gewijzigde scenarioaannames verdwijnen oude resultaten, zodat een kaart niet bij verkeerde parameters wordt getoond. Gewichten worden tussen pagina's bewaard. Een browserrefresh kan de sessie resetten; exports zijn de duurzame resultaten.

## Brondata en reikwijdte

| Onderdeel | Meegeleverde bron | Gebruik |
|---|---|---|
| Provinciegrens | `data/pzh.geojson` | Gebiedsafbakening en kaart |
| H3-grid | `app_data/h3_pzh_polygons.shp` | 37.142 cellen op resolutie 9 |
| Landbouwlocaties | `farm/pzh_farms.shp` | 14 van de 24 punten liggen binnen de provinciegrens |
| Wegennet | `osm_network/extracts/G.graphml`, `G_e.shp` | Nabijheid en gerichte wegafstanden; snapshot uit 2024 |
| Landgebruik | CORINE South-Holland GeoPackage onder `standalone/corine_data_landcover/extracts/South-Holland/` | Nabijheidsindicatoren, referentiejaar 2018 |
| Gasinlaten | Alleen een Twentelaag aanwezig | Niet toegepast op Zuid-Holland |
| Jaarlijkse mestvolumes | Niet beschikbaar | Expliciete scenarioaanname of eigen CSV |
| CBS-woningoutputs | Niet meegeleverd; map in `.gitignore` | Optionele woningverkenner met uitleg bij ontbrekende bestanden |

CORINE-criteria: industrie en voorzieningen **121**, woongebieden **111/112**, bos en semi-natuur **3xx**, water **5xx**. Dit is een grove landgebruiksclassificatie, **geen beschermde-natuurlaag**. De aanwezige boerderijen zijn een kleine steekproef en geen volledig bedrijfsregister. De precieze herkomst en actualiteit van sommige meegeleverde bronnen zijn niet vastgelegd: behandel ze als onderzoeksinput.

Oude CSV's, Twentedata, rasters en pickles blijven als onderzoeksarchief aanwezig. De hoofdapp gebruikt ze niet als Zuid-Hollandmetingen. `farm/farm_pzh_new.shp` blijkt fijnstofsensordata en is daarom geen boerderijbron. Er worden geen willekeurige onderzoeksgegevens of resultaten gegenereerd.

### Fase 1

Afstanden van H3-celcentra tot de aanwezige brongeometrie worden berekend in **RD New (EPSG:28992), in meters**. Nabijheid tot landbouw, wegen en industrie levert een hogere score op; afstand tot woongebieden, water en bos/semi-natuur levert een hogere score op. Min-maxnormalisatie gebeurt binnen het studiegebied, gevolgd door een gewogen gemiddelde. Een constante reeks krijgt score 0,5. Alle koppelingen zijn gebaseerd op H3-ID's.

Local Moran's I gebruikt aangrenzende H3-cellen, 999 permutaties, seed 42 en high-highquadrant met **p < 0,01**. Geen correctie voor meervoudig toetsen: dit is verkennend, geen locatiebewijs. De shortlist bevat maximaal 25 kandidaten, met minimaal 3 km onderlinge afstand; eerst hoogst scorende clusterrepresentanten en vervolgens overige hoog scorende clustercellen. Verander deze onderbouwde keuzes in `bioze/suitability.py` als je een andere methode wilt onderzoeken.

### Fase 2

Een mixed-integer capacitated facility location model met PySCIPOpt verdeelt continue hoeveelheden ton/jaar over geopende vergisters. Een landbouwlocatie kan meerdere vergisters leveren. De doelhoeveelheid wordt exact gehaald, binnen beschikbare bronvolumes en capaciteit.

Locaties worden in RD New gekoppeld aan bestaande graph-node IDs, op maximaal 5 km. Afstanden volgen het **gerichte** OSM-netwerk. Gedeelde netwerkknooppunten behouden hun afzonderlijke bedrijfs-ID's. Ontbrekende/onbereikbare verbindingen worden uitgesloten. Aansluittrajecten tussen bron/vergister en de netwerkknoop zitten niet in de transportafstand.

```text
Kosten over looptijd = investering
                    + jaarlijkse exploitatie × jaren
                    + Σ(ton/jaar × weg-km × €/ton/km × jaren)
```

De startwaarden voor capaciteit, investering en exploitatie komen uit het oude prototype, zonder gegarandeerde actualiteit. De oude transportfactor 0,69 is nu een **expliciete €/ton/km-scenarioaanname**, geen gevalideerd transporttarief. Geen verdiscontering, retourritten, energieopbrengsten of uitstootclaims. De kostentabel wordt gecontroleerd tegen de echte solverdoelfunctie. Rekentijd: maximaal 30 seconden; een haalbare tussenoplossing wordt met status en gap gemeld, niet als bewezen optimum.

### Kaarten

De standaardkaart gebruikt een inline achtergrondstijl en lokale provincie-, water- en weggeometrie. Geen API-key of externe kaarttegels nodig. Voor een snelle overzichtskaart worden scores gemiddeld naar H3-resolutie 8; de analyse, clusterselectie en exports blijven op resolutie 9. Exacte polygonen worden met de Python H3-library berekend om browsercompatibiliteitsproblemen te voorkomen. De optionele online achtergrond gebruikt CARTO/OpenStreetMap en vereist internet. Bogen in Fase 2 tonen toewijzingen, niet de geometrie van gereden routes. Tooltips tonen de werkelijke toegewezen hoeveelheden en de berekende wegafstand.

## Architectuur

```text
Home.py / pages/             Streamlit-pagina's
bioze/data.py               Bronlagen, geprojecteerde afstanden en CSV-validatie
bioze/suitability.py        Normalisatie, weging, H3-clusters en shortlist
bioze/routing.py            Wegennet, koppeling aan knopen, OD-afstanden
bioze/optimization.py       Scenario-input, CFLP, solverstatus en resultaten
bioze/ui.py + assets/        Gedeelde kaarten, legenda en vormgeving
Scripts/utils/              Kleine legacy-adapters
old_notebooks/              Behouden onderzoeksarchief en originele legacycode
```

Geodata en afstandstabellen gebruiken `st.cache_data`; het wegennet en de buurstructuur `st.cache_resource`. OD-berekeningen cachen alleen IDs/coördinaten, niet de complexe GeoDataFrame-internals. Dijkstra wordt eenmaal per unieke oorsprong uitgevoerd. Bij bronbestandswijzigingen: herstart de app of wis de Streamlit-cache.

## Kwaliteitscontrole

```powershell
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
```

De tests dekken normalisatie, H3-scoring na hersorteren, CSV-validatie, gerichte bereikbaarheid, gedeelde netwerkknopen, capaciteit, split flows, werkelijke transportkosten, nuldoel/infeasibiliteit, de echte PZH-dataset en de volledige Streamlit-overgang. `.github/workflows/quality.yml` voert dezelfde controles uit. Notebooks/legacyarchief vallen buiten de actieve lintscope; de oude notebookomgeving is niet opnieuw opgebouwd.

## Screenshots en beperkingen

Zie `docs/SCREENSHOTS.md` voor vier geschikte schermen en `docs/VALIDATIE.md` voor uitgevoerde checks. De CBS-module werkt pas na het aanleveren van de ontbrekende outputs. Voor actuele besluitvorming zijn aanvullende, gevalideerde bedrijfsvolumes, gasinlaten, juridisch relevante grenzen, vergunningseisen en actuele kosten nodig.
