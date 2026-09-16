# Stryktipset Predictor

**Prompt 4: deploymentklart.** Live bookmakerprovider med konsensus A/B, persistent Postgres, automatisk insamling, containerbackend och GitHub Pages-workflows är implementerade. Startsidan visar rekommenderat system, budget och 13 lättlästa matchkort; förklaringar och tekniskt underlag öppnas vid behov.

Användaren konfigurerar hosting och secrets. Ingen publik URL har provisionerats här. Utan `ODDS_API_KEY` visas riktiga Svenska Spel-odds som **märkt fallback**, inte bookmakerkonsensus. Aktiv policy är oförändrad: `market`, `P_model = P_market`.

**Lansera:** följ [de åtta deploymentstegen](docs/deployment.md). Se [launch checklist](docs/launch-checklist.md), [Prompt 4-rapporten](docs/implementation-report-v4.md) och [marknadsdefinition/provenance](docs/market-consensus.md). För produktion används `backend/requirements-runtime.lock.txt`; full utveckling/träning använder låsfilen nedan. Efter ett manuellt produktionsbygge återställ lokal frontend med `node scripts/configure-production.mjs --development` från `frontend`.

Svenska Spels aktuella kupong → riktiga folkstreck och observerade odds → aktiv marknadsbaseline → systemoptimizer → Angular. Football-Data och tidigare market/v1/v2-utvärdering finns kvar; tidsstämplade kuponger, prognoser, system, facit och utdelning bygger nu ett verkligt Stryktipsarkiv.

Gränssnittet följer [projektets UI/UX-specifikation](stryktipset-ui-ux-spec.md). Startvyn visar den optimala raden, tre faktiska insikter och 13 matcher. **DEMO DATA** betyder att matcher, odds och streck är exempel; sannolikheterna räknas av API:t. **Aktiv modell är marknadsbaseline**, eftersom v2 inte förbättrade Log Loss/Brier över walk-forward-perioden. Nyheter påverkar ännu inte sannolikheterna.

Se [slutrapport Prompt 3](docs/implementation-report-v3.md) för verifierad livekupong och historiktäckning samt [providerdokumentationen](docs/svenska-spel-provider.md) för schema, tidsgränser och drift. [Prompt 2](docs/implementation-report-v2.md) med modellresultat och nyhetsprovenance, [metod och nyhetsarkitektur](docs/model-news-v2.md) och [Prompt 1](docs/implementation-report.md) finns kvar som tidigare underlag.

## Setup

Testad med Python 3.13, Node 22.23 och Angular 21. Exakta dependency-versioner finns i `backend/requirements.lock.txt` och `frontend/package-lock.json`. SQLite skapas automatiskt lokalt. Grundappen och RSS-läget kräver ingen API-nyckel eller användarinloggning.

Från projektroten, PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
cd frontend
npm.cmd ci
cd ..
```

macOS/Linux: skapa samma `.venv` och använd `.venv/bin/python` i stället för `.venv\Scripts\python.exe`; använd `npm` i stället för `npm.cmd`.

## Data och träning

Kör hela pipelinen från `backend`:

```powershell
cd backend
..\.venv\Scripts\python.exe scripts/bootstrap_ml.py
```

Eller kör stegen separat från samma katalog:

```powershell
..\.venv\Scripts\python.exe scripts/download_football_data.py
..\.venv\Scripts\python.exe scripts/normalize_football_data.py
..\.venv\Scripts\python.exe ml/train_v2.py
```

Importören hämtar E0, E1 och E2 från 2010/11 till aktuell säsong hos [Football-Data](https://football-data.co.uk/englandm.php). Adressen utan `www` används eftersom `www` gav HTTP 503 vid verifieringen.

Urval och uppdatering:

```powershell
..\.venv\Scripts\python.exe scripts/download_football_data.py --start 2018 --end 2025 --leagues E0 E1
..\.venv\Scripts\python.exe scripts/download_football_data.py --refresh
```

`--end 2025` betyder säsongen 2025/26. Avslutade säsonger återanvänds ur cache om hämtningen gjordes efter säsongsslutet; aktuell säsong kontrolleras högst en gång per dygn. `--refresh` kontrollerar även cachade filer. En ändrad CSV sparas som en ny fil med innehållshash. Redan sparad rådata skrivs aldrig över. `raw/manifest.json` pekar på senaste versionen och sparar SHA-256, källa och hämtningstid. Fel i en fil stoppar inte övriga filer; 429/5xx och anslutningsfel har begränsade återförsök.

Normaliseringen hanterar saknade kolumner som null, normaliserar lagnamn, tar bort ofullständiga matcher och deduplicerar stabila match-ID:n. Marknadsodds prioriteras per rad: Avg → BbAv → B365 → PS. Closing-data lagras separat och används aldrig som ersättning för opening-data. Alla identifierade 1X2-oddskolumner sparas även i normaliserad form; original-CSV:n innehåller samtliga råkolumner.

Filer efter körning:

```text
backend/data/football_data/raw/<säsong>/E0.csv
backend/data/football_data/raw/manifest.json
backend/data/football_data/download_report.json
backend/data/football_data/processed/matches.parquet
backend/data/football_data/processed/features.parquet
backend/data/football_data/processed/normalization_report.json
backend/artifacts/model.joblib
backend/artifacts/model_metadata.json
backend/artifacts/model_v2_candidate.joblib
backend/artifacts/model_v2_candidate_metadata.json
backend/artifacts/walk_forward_predictions.parquet
backend/artifacts/evaluation_v2.json
backend/artifacts/experiment_manifest.json
backend/artifacts/v1/
```

## Backend

I en terminal, från `backend`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API-dokumentation: http://127.0.0.1:8000/docs. En ny modell läses automatiskt när modellfilen uppdateras; API:t behöver inte startas om efter träning.

## Frontend

I en andra terminal, från `frontend`:

```powershell
npm.cmd start
```

Öppna http://127.0.0.1:4200. Angular vidarebefordrar `/api` till port 8000. Backend och frontend binds till localhost. Produktionsbygget skapas med `npm.cmd run build`; vid egen driftsättning behöver webbservern stödja SPA-routes och vidarebefordra `/api` till FastAPI.

Windows-genväg efter installation: `./start-dev.ps1` från projektroten startar de två lokala servrarna i bakgrunden och visar deras process-ID:n. Loggar skrivs till `.logs/`.

## MVP-flöde

1. Hämta och träna historiken med `bootstrap_ml.py`.
2. Starta API och Angular. Översikten hämtar aktuell livekupong och analyserar den när alla 13 matcher har giltiga streck och odds. Saknas aktuell kupong visas tydligt märkt demo.
3. Öppna **Kupong → Redigera matcher, odds och streck**. Behåll/redigera demokupongen eller välj **Ny tom kupong** för en egen kupong.
4. Ange 13 matcher, liga, datum, alla tre odds och Svenska Folkets procent. Summan måste vara 100 ±1 procentenhet; API:t normaliserar avrundningsskillnaden.
5. Klicka **Analysera och generera system**. Budget och profil kan sedan ändras direkt.
6. Öppna en match för sannolikheter, edge, värdeindex, senaste fem matcher och modellinputs.
7. Ändra valda tecken manuellt på kupongsidan. Pris och kombinationer räknas om av API:t. **Återställ modellens val** tar bort dina teckenändringar.
8. **Kopiera system** kopierar lag och tecken till urklipp. Ingen spelinlämning sker.

Manuella tecken finns i webbläsarens arbetsminne; omladdning försöker ladda aktuell livekupong. Livekupongers odds och Svenska Folket sparas med registreringstid i SQLite lokalt eller Postgres i produktion. Historiksidan visar både verkligt Stryktipsarkiv med separat facit/utdelning och tidigare temporal modellutvärdering.

## Model v2 och läckageskydd

V2 lär en regulariserad korrigering: `softmax(log(P_market) + correction(features))`. Marknaden förblir ankaret. Jämförelser omfattar marknaden, v1-logistisk regression och nio v2-varianter: successiv Elo/form/hemma-borta/vila-ablation, ligainteraktioner, säsongsregression, divisionsjustering och temperature scaling. Endast tidigare data används för imputation, skalning, hyperparametrar och calibration. Se [detaljerad metod](docs/model-news-v2.md).

Sex testperioder täcker 2020/21–2025/26. Föregående säsong används för validation inom varje fold. Modellvariant väljs på 2020/21–2024/25, medan 2025/26 hålls utanför v2-urvalet som audit. Deployment kräver förbättrad Log Loss, Brier och stabilitet över säsonger samt acceptabel kalibrering. Ingen kandidat klarade kraven. V2-kandidaten sparas separat; aktiv baseline har inga inlärda korrektioner. V1-artefakter arkiveras i `artifacts/v1`. De äldre `ml/train.py`/`ml/evaluate.py` avser v1 och ska bara köras om v1 uttryckligen önskas som deployment (`bootstrap_ml.py --legacy-v1`).

Features skapas före datumets resultat och uppdateras först efter samtliga matcher den dagen. Sluttestet använder löpande tidigare resultat för form/Elo med oförändrade modellvikter. Ingen slumpmässig train/test-split används. Predict-endpointen använder marknadsfallback för datum inom deploymentmodellens träningshistorik; den är inte en historisk backtest-endpoint.

Log loss och multiclass Brier prioriteras. Brier definieras som medelvärdet av summan av kvadrerade fel för alla tre utfall (intervall 0–2). Accuracy och kalibreringsbin per klass redovisas också. Modellen behöver inte slå marknaden; den första faktiska körningen gör det inte.

Football-Data ger inte exakta observationstider för de historiska opening-oddsen. Testet representerar därför en allmän prognos före match, inte ett verifierat onsdags- eller T−24h-scenario. Closing-odds är exkluderade, men ett exakt historiskt beslutsklockslag kan inte verifieras med denna källa ensam.

## API

| Metod | Endpoint | Funktion |
|---|---|---|
| GET | `/api/config` | Gemensamma budgetar, radpris, ligor och toleranser |
| GET | `/api/model/status` | Modell, dataset, perioder, mått och importfel |
| GET | `/api/teams/search?q=Manchester%20Utd` | Central aliasnormalisering och lagförslag |
| GET | `/api/coupon/demo` | Exakt 13 tydligt fiktiva matcher |
| POST | `/api/predict/match` | Modell/marknad, fallbackorsak, form och features |
| POST | `/api/coupon/analyze` | Matchanalys, tre insikter och optimerat system |
| POST | `/api/coupon/optimize` | Samma verifierade flöde med vald budget/profil |
| POST | `/api/coupon/cost` | Kombinationsantal och pris för manuella val |

Matchinput:

```json
{
  "homeTeam": "Arsenal",
  "awayTeam": "Everton",
  "date": "2026-09-12",
  "league": "E0",
  "marketOdds": {"home": 1.7, "draw": 4.0, "away": 5.2}
}
```

Coupon-endpoints tar `{ "coupon": <kupong>, "budget": 256, "mode": "optimal" }`. Input-crowd anges 0–100; output-probabilities och normaliserad crowd anges 0–1. Utfallen är alltid `home`, `draw`, `away`, i teckenordning `1`, `X`, `2`. `source` anger `ml`, avsiktligt vald `market_baseline` eller `market_fallback` vid saknad modell/historik. Analysen innehåller stabilt `matchId` för nyhetskoppling.

## News Intelligence

Tom `NEWS_PROVIDER` låter appen starta med tydlig status ”inte konfigurerat”. För det verifierade alternativet utan API-nyckel, sätt detta i API-terminalen **före start**:

```powershell
$env:NEWS_PROVIDER = "rss"
$env:NEWS_EXTRACTION = "rules"
```

Välj sedan **Nyheter → Uppdatera kupongens nyheter**, eller kör från `backend`:

```powershell
..\.venv\Scripts\python.exe scripts/update_news.py --coupon CURRENT --provider rss --extraction rules
..\.venv\Scripts\python.exe scripts/export_news.py
```

`CURRENT` är senast analyserad/sparad kupong. `--coupon DEMO` eller en sökväg till kupong-JSON kan också användas. News-CLI:s flaggor gäller jobbet; API-processen behöver motsvarande miljöinställning för korrekt UI-status. `.env.example` innehåller placeholders; `.env` läses inte automatiskt.

För webbsökning: välj `NEWS_PROVIDER=brave` eller `tavily` och sätt `NEWS_API_KEY`. För strict LLM-extraktion: välj `NEWS_EXTRACTION=openai`, sätt `LLM_API_KEY` och ett `LLM_MODEL` som ditt konto stöder med Structured Outputs. Inga nycklar ska skrivas i repo eller loggar. Brave/Tavily/LLM är kontrakttestade med mocks; RSS/rules är verifierat med verklig hämtning. Rules-läget är begränsat och tydligt märkt som regelbaserat.

Lagringen i `backend/data/news` innehåller oförändrade raw-svar, SQLite-artiklar/versioner, grupperade events, signals, spelare/alias, manuella odds-/strecksnapshots och nyhetssnapshots. Exporten skriver `processed/news_signals.parquet` och `news_snapshots.parquet`, utan matchutfall. Sju dagars fönster, source tiers, queries, dedupe, confidence och gränser finns centralt i `backend/app/news/config.py`. Formel, tidsregler, API och datamodell finns i [nyhetsdokumentationen](docs/model-news-v2.md).

Schemalägg CLI-kommandot externt, exempelvis dagligen tidigt i veckan och varannan timme nära kupongstopp. I Windows Aktivitetsschemaläggaren: program `C:\stryktipsAI\.venv\Scripts\python.exe`, argument `scripts/update_news.py --coupon CURRENT --provider rss --extraction rules`, startkatalog `C:\stryktipsAI\backend`. Inget schema skapas automatiskt; samma jobb kan köras av cron. Cache och rate limiting gäller även schemalagda jobb. Kör en worker åt gången.

## Konfiguration och arkitektur

Gemensam konfiguration finns i `backend/app/config.py`: ligor, första säsong, Elo, rolling-fönster, historikgräns, crowd-tolerans, värdegolv, profiler, budgetar och radpris. Aliaser finns i `backend/app/team_aliases.json`. Miljövariabler är valfria och måste sättas i terminalen; `.env` laddas inte automatiskt:

```powershell
$env:STRYKTIPS_ROW_COST = "1"
$env:STRYKTIPS_DATA_DIR = "C:\stryktipsAI\backend\data\football_data"
$env:STRYKTIPS_ARTIFACT_DIR = "C:\stryktipsAI\backend\artifacts"
```

Radpris ska vara större än 0 och mindre än 1000. Starta om API:t efter konfigurationsändring; träna om vid ändrade feature-/Elo-parametrar. Browsern hämtar radpris och budgetar från API:t. Kostnadsberäkningen är central och görs med Decimal.

`scripts/` äger import/normalisering. `ml/` äger features, träning, utvärdering och prognoser. `app/services/` äger value, teamekvivalenser, kuponganalys och optimizer. `app/main.py` har tunna endpoints och Pydantic validerar input. Angular har separata sidor, återanvändbara komponenter och en typad store; ingen ML- eller optimizerlogik finns i browsern.

Se [optimizerbeskrivningen](docs/optimizer.md) för oförändrat objective och [v2-arkitekturen](docs/model-news-v2.md) för implementerade snapshots och News Intelligence. Den äldre [arkitekturnoteringen](docs/architecture.md) beskriver Prompt 1.

## Tester och verifiering

Backend, från `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe scripts/verify_demo.py
```

`verify_demo.py` kräver ett körande API med modellartefakt. Det testar alla tre profiler × fyra budgetar, kräver aktiv modell/baseline för samtliga 13 demomatcher och skriver `artifacts/demo_verification_v2.json`. Vid aktiv baseline kontrolleras exakt likhet med marknadens sannolikheter.

Diagnostik och reproducerbar rapport från sparade resultat:

```powershell
..\.venv\Scripts\python.exe scripts/optimizer_diagnostics.py
..\.venv\Scripts\python.exe scripts/write_report_v2.py
```

Rapportgeneratorn kräver evaluation, optimizerdiagnostik, API-verifiering och en insamlad nyhetsobservation. `write_report.py` är den historiska Prompt 1-generatorn. Senaste verifiering: 93 backendtester, 16 Playwright-tester och godkänt produktionsbygge; externa news- och Svenska Spel-anrop är mockade i automatiska tester. Separat verklig read-only-verifiering finns i Prompt 3-rapporten.

Frontend, från `frontend`, med tränat API igång:

```powershell
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Playwright startar Angular automatiskt om port 4200 är ledig. Testerna använder det riktiga API:t och omfattar desktop/mobil, crowd-validering, oddsändring, drawer, form/modell/nyheter, alla budgetar, manuella tecken, återställning och API-fel/återförsök. Screenshots finns i `frontend/test-results/`.

Om importen misslyckas: läs `download_report.json`, kontrollera nätet och kör importen igen. Om modellen saknas eller ett lag har färre än fem historiska matcher används marknadsfallback med en begriplig förklaring. Saknade eller ogiltiga odds och streck avvisas med 422; inga fejkade sannolikheter genereras.

## Avgränsningar

Ingen payoutmodell, kontointegration, spelinlämning eller betalning ingår. Svenska Spel-integrationen använder ett odokumenterat publikt flöde. Observerade odds i detta flöde är en enda källa; saknade odds kräver manuell input. Arkiverade historiska slutstreck är inte pre-close-observationer. Ännu finns bara en verklig omgång med sparade pre-close-system, vilket är otillräckligt för resultatutvärdering. News Intelligence och optimizerobjektivet är oförändrade; ingen lönsamhet eller news-edge har visats.

## Live Stryktipset

Appen laddar `GET /api/coupon/current` automatiskt. Backend väljer öppen omgång med närmaste spelstopp, oberoende av responsens ordning. **LIVE DATA**, omgångsnummer, spelstopp, hämtningstid, mapping och providerstatus visas. Uppdatera-knappen använder kontrollerad refresh. Saknade odds blockerar systemet tills användaren fyller i odds; folkstrecken behålls från källan. Demo och manuell kupong finns kvar som uttryckliga alternativ.

Från `backend`, utan API-nyckel:

```powershell
..\.venv\Scripts\python.exe scripts/update_stryktipset.py
..\.venv\Scripts\python.exe scripts/update_stryktipset.py --draw 4970
..\.venv\Scripts\python.exe scripts/update_stryktipset.py --force
..\.venv\Scripts\python.exe scripts/add_team_alias.py "Nytt leverantörsnamn" "Manchester United"
```

Sista kommandot är ett exempel: skapa bara alias när laget verkligen är identifierat. `STRYKTIPS_LIVE_ENABLED=false` stänger av extern hämtning; `STRYKTIPS_LIVE_DIR` anger annan lagringsplats.

## Svenska Folket

`drawEvents[].svenskaFolket.one/x/two` parsas som procent och normaliseras till 0–1. 99–101 procent totalt tolereras; orimliga värden blir fel/saknad data. Crowd hålls strikt separat från `drawEvents[].odds.one/x/two` och modellens sannolikheter. Källans crowd-tid sparas när den är giltig. UI skiljer observerade streck/odds, skattad modell, beräknad edge/value och saknade inputs.

## Snapshots

Varje verklig hämtning arkiverar oförändrade bytes och separata registrerings-, hämtnings- och eventuella källtider. Liveanalys sparar 13 prognoser, modellhash, exakta inputs och hela systemet. Tidigare observationer skrivs inte över. Matchdetaljer visar streckhistorik; Analys visar faktiska rörelser. Crowd movement påverkar inte modellens sannolikheter.

Produktionsinsamling kör `scripts/collect_live_data.py` från GitHub Actions var femte minut. Scriptet hämtar efter behov: var 6:e timme mer än 48 timmar före spelstopp, varannan timme 24–48 timmar före, varje timme 6–24 timmar före, var 30:e minut sista sex timmarna och var femte minut sista halvtimmen. Det inkluderar bookmakerodds, predictions, system och saknade resultat. Det äldre `scripts/update_stryktipset.py --due` kan fortsatt uppdatera Svenska Spel lokalt. [Deploymentguiden](docs/deployment.md) beskriver aktivering, secrets och schemats begränsningar.

```powershell
..\.venv\Scripts\python.exe scripts/export_stryktipset.py
..\.venv\Scripts\python.exe scripts/diagnose_real_crowd.py --analyze-current
..\.venv\Scripts\python.exe scripts/verify_stryktipset.py
```

Exporten skapar separata JSONL-tabeller och manifest i `data/stryktipset/exports/`. Diagnostik räknar senaste sparade system per verklig omgång/budget/profil; upprepade UI-analyser blir inte nya oberoende samples. Verifieringsscriptet kräver en redan hämtad analysklar livekupong och aktiv marketmodell.

## Historical import

```powershell
..\.venv\Scripts\python.exe scripts/import_stryktipset_history.py --from-draw 4958 --to-draw 4969
```

Importen begränsar anrop, återupptas från cache och sparar `history_import_<from>_<to>.json` med lyckade/misslyckade draws. Högst 500 omgångar per körning; `--refresh` hämtar uttryckligen igen. Metadata/matcher dedupliceras. Historiska crowdvärden hämtade idag bakdateras aldrig till tiden före spelstopp. Arkivet har snapshotväljare och visar endast prognoser som faktiskt sparats vid vald tid.

## Results

```powershell
..\.venv\Scripts\python.exe scripts/update_stryktipset_results.py
..\.venv\Scripts\python.exe scripts/update_stryktipset_results.py --draw 4969
```

Facit hämtas från `/draws/{number}/result`, med officiellt tecken, eventuella mål och utdelningsnivåer 13–10. Resultat och payout lagras separat från pre-match-inputs och används aldrig som modellfeatures. `--force` begär uppdaterad result-response för vald draw.

## Provider limitations

Formatet är odokumenterat; schemafel sparas med råsvaret och tidigare cache märks tydligt som gammal. Historiska stickprov fungerar från 2013-01-12, men sammanhängande täckning har inte verifierats. Historisk crowd kan sakna källtid och kan vara uppdaterad efter spelstopp. Ingen sådan slutdata används som förhandsprognos. [Full fältmappning, endpoints och begränsningar](docs/svenska-spel-provider.md).
