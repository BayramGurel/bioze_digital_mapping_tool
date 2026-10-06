# Validatie · 6 oktober 2026

## Herstelde fouten

- De zeven oorspronkelijke mockcriteriabestanden hadden slechts **drie gezamenlijke H3-cellen**, terwijl scores op rijvolgorde werden gecombineerd. De app gebruikt nu één H3-geïndexeerde afstandstabel, afgeleid van de aanwezige Zuid-Hollandse bronlagen.
- De oudere `*_v2.csv`-afstanden bleken Twentecellen te bevatten. De hoofdapp combineert deze niet met Zuid-Holland.
- Het Fase-2-scherm gebruikte niet-bestaande kaartmethodes, een andere boerderijregio en onjuiste model-ID's. De nieuwe keten gebruikt dezelfde Zuid-Hollandkandidaten en landbouwlocaties als Fase 1.
- Het GraphML-pad is relatief aan de projectlocatie. Graph-node IDs worden opnieuw en consequent bepaald; oude `closest_os`-velden met losse OSM-IDs of stringlijsten worden niet vertrouwd.
- De oude transportkostentabel vermenigvuldigde niet met de toegewezen hoeveelheid en volgde daardoor de solverdoelfunctie niet. Kosten volgen nu jaarlijkse flow × afstand × tarief × jaren.
- Niet-haalbare scenario's, ontbrekende solver, onbereikbare OD-paren en ontbrekende CBS-outputs hebben expliciete afhandeling.
- Verouderde kandidaten/scenarioresultaten verdwijnen bij gewijzigde of lege criteria. Gewichten blijven tussen pagina's beschikbaar.
- Plotly-configuratiewaarschuwingen zijn uit de resultatenweergave verwijderd.
- Browserproblemen met H3-rendering zijn opgelost door exacte polygonen via Python te berekenen. Voor overzichtsrendering worden scores naar resolutie 8 gemiddeld; geen wijziging van analyse of export.

## Uitgevoerde controles

Python 3.12, Linux:

- `pip check`: geen conflicten.
- Ruff lint en formatting: geslaagd voor actieve code, pagina's, tests en adapters.
- Python syntaxcompiler: alle aanwezige Pythonbestanden geslaagd.
- Pytest: **11 tests geslaagd**, inclusief echte brondata, algebraïsch controleerbare solveruitkomst en Streamlit-overgang van analyse naar optimalisatie.
- App gestart met Streamlit; Home, Fase 1, Fase 2, CBS-melding en resultaten visueel bekeken.
- Browsercontrole met Chromium/Playwright. De agent-browser-daemon kon in deze runtime niet starten, daarom is de controle rechtstreeks met Playwright uitgevoerd.
- Desktop 1920×1080; aanvullende controles op 1366×768 en 1024×768, zonder horizontale pagina-overflow; KPI-typografie past zich op kleinere breedtes aan. De kaart gebruikt lokale geometrie; externe CARTO-tegels zijn door het omgevingsnetwerk geblokkeerd en konden hier niet volledig worden gevalideerd.

## Gecontroleerd standaardscenario

Zes criteria, gelijke weging; seed 42, 999 Local Moran-permutaties, p < 0,01; 25 kandidaten. De 14 landbouwlocaties hebben in dit voorbeeld **elk een expliciete hypothetische aanname van 2.500 ton/jaar**. Geen gemeten mestproductie.

Bij een doel van 50%, capaciteit 119.547 ton/jaar, investering € 6.089.160, jaarlijkse exploitatie € 1.047.200, transport € 0,69/ton/km en looptijd 12 jaar:

- 17.500 ton/jaar verwerkt;
- één geopende vergister, kandidaat V25;
- gewogen gemiddelde wegafstand circa 25,26 km;
- investering € 6.089.160;
- exploitatie over de looptijd € 12.566.400;
- transport over de looptijd circa € 3.660.732,62;
- totale solverdoelfunctie circa € 22.316.292,62;
- status `optimal`, gap 0.

Dit is een echt berekend scenario binnen de gekozen shortlist en aannames. Het zegt niets over actuele provinciale volumes, toekomstige tarieven of feitelijke uitvoerbaarheid.

## Niet volledig gevalideerd

Windowsinstallatie, CBS-module met echte ontbrekende outputs, online kaarttegels en actuele externe bronnen. Legacy-notebooks zijn behouden als archief en syntaxcontrole is geen bewijs dat hun oude runtimeomgeving werkt. Gasinlaten, volledige bedrijfsdekking, mestvolumes, actuele kosten, beschermd-natuurbeleid en vergunningstoetsen ontbreken.

De kaartvereenvoudiging naar resolutie 8 halveerde in deze omgeving de totale duur van de applicatie-/rekentest-suite van circa 56 naar circa 28 seconden. Dit is een lokale testmeting, geen benchmark voor alle machines.
