# Prompt 4 — deploymentklar leverans

Verifierad 9 september 2026, med senaste datakontroll **21:55:49 UTC / 23:55:49 Europe/Stockholm**. Användaren har valt att konfigurera hosting och secrets själv. Leveransen innehåller produktionskod, workflows och instruktioner; **ingen publik frontend, backend eller molndatabas har provisionerats här**. Arbetskatalogen saknar Git-repository/remote.

## Resultat

| Område | Levererat och verifierat |
|---|---|
| Marknad | The Odds API v4, säkra eventträffar, bookmakerobservationer, konsensus A/B, kvalitet, cache och märkta fallbacks |
| Lagring | Postgres 17, två migrationer, råbytes i DB, append-only snapshots, exakta inputreferenser och export |
| Insamling | Fristående CLI, adaptiv policy, resultat, predictions och optimizer; GitHub Actions schema + manuell start |
| Frontend | GitHub Pages production build, konfigurerad HTTPS-API, repository-prefix och hash-routing |
| Backend | Minimal Python 3.13-container, icke-root, healthcheck, runtimevalidering och exakta CORS-origins |
| UI | Tre huvudflikar, rekommenderat system/budget först, förklaringar och teknisk information på begäran |

Aktiv modell är fortfarande **market**. Alla 13 kontrollerade `model`-vektorer är identiska med respektive `market`. Optimizer-objective och vikter är oförändrade. News crawling, extraction, scoring, features och sannolikhetspåverkan har inte utvecklats. Lokala ML-artefaktens SHA-256 är fortsatt `76ec6f68eac56fcc693374d7813935ac7c798aa621ff94b09e8e955442d805ec`.

## Faktiskt liveunderlag

Omgång **4970**, spelstopp **12 september 2026 kl. 15:59 Stockholm**:

- 13/13 verkliga matcher och giltiga Svenska Folket-observationer.
- 26/26 lagreferenser mappade, 13/13 inom modellens ligatäckning.
- 13/13 observerade Svenska Spel-odds, uttryckligen `svenska_spel_odds`.
- **0 verkliga bookmakerobservationer, 0 konsensussnapshots.** `ODDS_API_KEY` saknas i denna miljö.

Per match, källa, bookmakerantal och sannolikheter finns i [verification-v4.json](verification-v4.json). Dessa sannolikheter är marknadsbaseline från Svenska Spel-fallback; de ska inte beskrivas som uppmätt bookmakerkonsensus. Providerfunktion och A/B-beräkning testas med isolerade testfixtures. Verklig bookmakerverifiering återstår efter nyckelkonfiguration.

Vid budget 256 kr, rekommenderad profil:

```text
2 | 1 | 1 | 1 | 1 | 1X2 | 1X2 | 2 | 1X2 | 1 | 1X2 | 1 | 1X2
```

243 rader, 243 kr, åtta spikar, inga halvgarderingar och fem helgarderingar. Beräknad chans att täcka 13 rätt: **0,96015 %**, cirka 1 på 104 under modellens oberoendeantagande. Detta är inte verifierad lönsamhet och ingen kupong har lämnats in.

## Verklig collection utan webbläsare

Senaste körningen gjordes som CLI i den färdiga runtimecontainern, direkt mot Svenska Spels publika GET-flöde och lokal test-Postgres:

| Fält | Observerat värde |
|---|---|
| Run ID | `e302e6c9d79a410198df7110b8ed4b0a` |
| Start | 2026-09-09T21:54:56.610182Z |
| Slut | 2026-09-09T21:54:58.224874Z |
| Tid | 1,615 sekunder |
| Omgång | 4970 |
| Crowd | Sparad |
| Market | Ej konfigurerad bookmakerprovider; 13 märkta Svenska Spel-fallbacks |
| Prediction | 13 nya, med exakta inputreferenser |
| Optimizer | Ett nytt system, 256 kr / optimal |
| Snapshot-set/system-ID | `3c2be2a417a745f597eadb8c7d190408` |
| Resultat | Inga nya hämtningar behövdes; arkiverade stängda omgångar hade redan komplett facit |
| Status/fel | `partial`: oddsnyckel saknas, övrigt sparat |

En tidigare verklig insamlingskörning, `6d683cf2f29044c286ca021564b1e380`, tog 4,709 sekunder och sparade också 13 predictions samt ett system. Båda run-posterna finns i verifieringsfilen. Detta är lokala CLI-körningar, **inte körningar i GitHub Actions**; workflow_dispatch kräver användarens repository och secrets.

## Databas och export

Det befintliga SQLitearkivet migrerades till en isolerad Postgres 17 med bevarade snapshot-ID:n och observationstider. Rådata ligger som hashad bytea i `provider_raw_blobs`, inte på backendcontainerns filsystem. Testdatabasen är lokal och ska inte betraktas som vald permanent molnhost.

| Tabell/innehåll | Antal |
|---|---:|
| Omgångar | 17 |
| Matcher | 221 |
| Kupongobservationer | 21 |
| Crowd snapshots | 273 |
| Svenska Spel-/manuella market snapshots | 91 |
| Bookmaker consensus snapshots | 0 |
| Bookmaker observations | 0 |
| Prediction snapshots | 520 |
| Optimizer snapshots | 40 |
| Resultatobservationer | 16 |
| Matchfacit | 208 |
| Payout-rader | 64 |
| Svenska Spel raw-ledger / raw blobs | 37 / 37 |
| Odds API requests | 0 |
| Collection runs | 2 |

Historiskt urval är omgångar 4267–4270 och 4958–4969, plus aktuell 4970. Detta är **inte sammanhängande historisk täckning**. Tidigaste observerade omgången är från 12 januari 2013. Äldre slutstreck hämtades efter spelstopp och har inte bakdaterats eller använts till fabricerade förhandsprognoser.

Migrationerna kan köras igen utan att radera data. Efter omstart av backendcontainern kontrollerades samma databasantal och exakt samma system-ID. Råbytesens hash verifierades. Export `backend/exports/launch-final-v4/manifest.json` skapades 21:55:51 UTC med schemaversion 2, 17 omgångar, 221 matcher och totalt 924 rader i snapshot-tabellerna. Stora JSONL-filer och rådata är exkluderade från Git/Docker-buildkontext. Full backup/restore och initial SQLiteimport dokumenteras i [deploymentguiden](deployment.md).

## Tester och produktionsbygge

- **110 backendtester godkända**, inklusive riktig Postgres med unika testscheman, migrationers omkörning, råbytes, lås, providerfel, konsensus, tidsgränser, deduplicerad analys och produktionsskydd.
- Ren checkout simulerad utan lokala träningsartefakter eller Football-Data-filer: **109 godkända, ett avsiktligt hoppat artefakttest**. Ingen modellträning eller stor lokal datamängd krävs för CI.
- **16 Playwrighttester godkända**, desktop och mobil: budget, drawer, egen kupong, validering, API-fel/återhämtning, liveetiketter, stale, historik och oförändrad nyhetspåverkan.
- Produktionsbuild: **397,84 kB initial JavaScript/CSS**, uppskattad överföring 105,44 kB. Analys och historik laddas separat; ingen ny tung chart dependency.
- Produktionsartefakten testades under `/stryktips-test/` med hash-routing på desktop 1440×1050 och mobil 390×844. 13 matchval, omladdad `#/history`, ingen horisontell overflow, inga JavaScript-fel och ingen demofallback vid saknad data verifierades.
- Pages-kontrollen kördes både med inspelade testresponser för CI och via lokal testproxy mot verklig produktionscontainer/Postgres. Testproxyn anpassade CORS för sin tillfälliga localhost-port och kontrollerade API:ts konfigurerade origin separat. Detta bevisar inte publik DNS/TLS/hosting. Se [pages-verification-v4.json](pages-verification-v4.json).
- Alla tre GitHub-workflows passerade `actionlint`. CI kör Postgrestester samt Pages-build och routingtest. Faktiskt GitHub-jobb har inte körts.
- Dockerimage byggd och API startat: `/health`, aktuell kupong, analys och lagsökning gav 200. Produktionsdemo gav 404 och delad aliasändring utan token 403.
- 148 käll-/konfigurations-/dokumentfiler kontrollerades för vanliga nyckel/token/private-key-mönster utan träff. Det finns ingen Git-historik att granska i denna arbetskatalog; detta är inte en garanti mot alla slags hemligheter.

Två dependency-deprecationvarningar kvarstår i testklienten; de gav inga testfel. Lokal frontendkonfiguration är återställd till development efter produktionsbygget.

## UI: konkret förändring

**Bort från huvudytan:** tekniska modellmått, nyhetspanel, detaljerade value/edge-tabeller, ligabadges på varje kort och alltid synliga profilreglage. Navigeringen är Kupongen, Analys och Historik.

**Förenklat:** hero visar rekommenderade tecken, faktisk kostnad, spikar/garderingar och budget. 13 kort jämför vår sannolikhet med Svenska Folket och visar aktuell oddskälla. Kopiera system och Anpassa tecken finns direkt vid systemet. Budgeten beskrivs som ett tak, inte en utlovad kostnad.

**Förklaringar:** varje match beskriver mest sannolika tecken, jämförelse med strecken och varför systemet spikar/garderar inom budget. ⓘ-förklaringar kan öppnas med tangentbord eller touch. Tre insiktskort har enkel svensk text. Modellpolicy, independence och ordlista ligger under Så fungerar sidan/Hur fungerar modellen.

**Avancerat:** drawer har Översikt, Data och Historik. Odds, bookmakerantal, kvalitet, källtider, sparade sannolikheter och crowd/market-rörelser öppnas där. Nyhetspanelen ligger under extra detaljval med oförändrad funktion. Modellutvärdering ligger under Fördjupad modellinfo och laddas först när den öppnas.

**Mobil:** systemval bryts till två rader, matchkorten till en kolumn och tre flikar finns i botten. Drawer fyller skärmen. Skärmbilder granskades visuellt: [desktop](screenshots/launch-v4-desktop.png), [mobil första vy](screenshots/launch-v4-mobile-fold.png), [mobil helsida](screenshots/launch-v4-mobile.png), [matchförklaring](screenshots/launch-v4-explanation-mobile.png) och [historik](screenshots/launch-v4-history-desktop.png). Bilderna visar verklig sparad kupong, med Svenska Spel-fallback och ärlig frånvaro av bookmakerhistorik.

## Kända begränsningar och manuella lanseringssteg

- Användaren behöver konfigurera repository, Pages, API-host, Postgres, secrets, CORS-origin och backup; se [launch checklist](launch-checklist.md).
- The Odds API-kvot och varierande bookmakerutbud begränsar uppdatering och täckning. Verkliga bookmakers är ännu inte verifierade utan nyckel.
- GitHub Actions kan försenas. Ett exakt snapshot vid spelstopp kan inte garanteras.
- Svenska Spels publika flöde är odokumenterat och kan ändras eller bli otillgängligt.
- Live-A efterliknar matematiskt Football-Data-medelodds, men bookmakerurval och tidpunkter är inte verifierat identiska. Se [kompatibilitetsrapporten](market-consensus.md).
- Optimizer är inte payout-optimerad. 13-rättschansen multiplicerar matchers täckningssannolikheter under oberoendeantagande.
- Ingen nyhetspåverkan och inget påstående om bevisad edge eller lönsamhet.

Fortsättning för ägaren är de [åtta konkreta deploymentstegen](deployment.md), därefter verklig bookmakerkontroll och publik end-to-end-kontroll.
