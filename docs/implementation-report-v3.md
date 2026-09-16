# Prompt 3 – verklig Stryktipsdata

Implementation och verklig read-only-verifiering genomförd **9 september 2026**. Appen laddar nu aktuell Svenska Spel-kupong automatiskt och använder observerade folkstreck och separata odds genom befintlig prediction-/optimizerkedja. Resultat och utdelning går till ett separat historiskt arkiv. Ingen kupong har lämnats in.

## Verifierad aktuell omgång

| Kontroll | Faktiskt resultat |
|---|---|
| Omgång | **4970**, öppen |
| Datum och spelstopp | 2026-09-12 kl. **15:59 Europe/Stockholm** |
| Senaste hämtning i rapporten | 2026-09-09 **22:40:45.339** svensk tid, 20:40:45.339 UTC |
| Matchantal | **13 / 13** |
| Riktiga Svenska Folket-streck | **13 / 13** |
| Separata observerade marknadsodds | **13 / 13**, inga saknade odds i denna kupong |
| Mappade lagreferenser | **26 / 26**, inga unmapped |
| Tränad ligatäckning | **13 / 13**, E0 och E1 |
| Aktiv modell | **market**, metadata version 2.0 |
| Sannolikhetskontroll | Samtliga 13 P_model exakt lika med de-vig marknadsbaseline |
| Nyheter/streckrörelser i P_model | Ingen påverkan |

Källa: observerade offentliga svar från `https://api.spela.svenskaspel.se/draw/1/stryktipset/draws`. Dessa bytes är lokalt arkiverade och kopplade till varje input. [verification-v3.json](verification-v3.json) innehåller hela den kompakta verifieringen, lag, odds, crowd, modell och rekommenderade tecken. Exakt fältmappning och begränsningar finns i [providerdokumentationen](svenska-spel-provider.md).

### Faktiskt live-system

Analys registrerad 2026-09-09 omkring 22:43 svensk tid. Profil **Optimal**, budget **256 kr**:

```text
2 | 1 | 1 | 1 | 1 | 1X2 | 1X2 | 2 | 1X2 | 1 | 1X2 | 1 | 1X2
```

| Mått | Värde |
|---|---:|
| Rader / kostnad | **243 / 243 kr** |
| Spikar | **8** |
| Halvgarderingar | **0** |
| Helgarderingar | **5** |
| Budgetutnyttjande | **94,92 %** |
| Skattad sannolikhet att systemet täcker 13 rätt | **0,96015 %**, cirka 1 på 104 |
| Value index | **1,02630** |

Sannolikheten beräknas med befintlig modell och antagandet om oberoende matchutfall. Det är en modellskattning för systemets täckning, inte observerad vinstfrekvens eller garanti om utbetalning. Radkostnaden följer 1 kr/rad och 3⁵ = 243 rader. Optimizerobjektivet och dess vikter har inte ändrats.

## Observerade snapshots

Aktuell omgång har **tre** verkliga hämtningar, med 13 crowd-observationer vardera:

| Hämtad UTC | Registrerad UTC |
|---|---|
| 20:12:37.951982 | 20:12:38.291672 |
| 20:13:54.115744 | 20:13:54.254309 |
| 20:40:45.339499 | 20:40:45.697919 |

Samtliga är från 2026-09-09. **Ingen streckrörelse observerades** mellan dessa hämtningar: 0 procentenheter för samtliga tecken. UI visar observationerna och verkliga differenser; det finns ingen konstruerad trend.

Vid verifieringsgränsen **20:43:54 UTC** innehöll arkivet:

| Entity | Antal |
|---|---:|
| Unika omgångar | 17 |
| Unika matcher | 221 |
| Kupongobservationer | 19 |
| Crowd-snapshots, matchrader | 247 |
| Market-snapshots, matchrader | 65 |
| Prediction-snapshots, matchrader | 247 |
| Optimizer-snapshots | 19 |
| Resultatobservationer | 16 |
| Matchresultat | 208 |
| Utdelningsposter | 64 |
| Provider-requestposter | 35 |

Senare UI-analyser kan öka prediction-/systemantalet; siffrorna ovan hör till den sparade verifieringens tidpunkt. JSONL-export av samma gräns har körts och dess manifest kontrollerats. Oförändrade råbytes lagras innehållsadresserat, medan varje riktig request får sin egen ledgerpost. Exakt upprepad ingest är idempotent.

En policy för återkommande snapshots finns i `DrawConfig`, inklusive en minuts intervall sista fem minuterna. CLI kan köras av valfri scheduler. **Ingen permanent scheduler har installerats**; utan schemalagd worker sker uppdateringar när appen kontrollerar aktuell kupong. Fortlöpande insamling med stängd webbläsare kräver schemalagd körning enligt README.

## Historisk tillgänglighet och facit

Importerade avslutade intervall: **4267–4270** och **4958–4969**, sammanlagt **16 omgångar**. Alla har 13 matcher, observerad historisk crowd, 13 facit och utdelningsnivåerna 13–10. Upprepad import av 4267 och 4969 återanvände cache och bevarade samtliga databasantal, inklusive raw-requestantal.

| Fält | Äldsta lyckade observerade draw | Datum | Lokalt antal draws med fältet |
|---|---:|---|---:|
| Draw metadata | 4267 | 2013-01-12 | 17 |
| Matcher | 4267 | 2013-01-12 | 17 |
| Crowd | 4267 | 2013-01-12 | 17 |
| Resultat | 4267 | 2013-01-12 | 16 |
| Payout | 4267 | 2013-01-12 | 16 |

4266 och flera äldre testade ID:n svarade 404. Stickprov 4300, 4400, 4500 och 4900 fungerade också. **Sammanhängande täckning från 2013 har inte verifierats**, och misslyckade stickprov bevisar inte att alla äldre draws saknas.

Historiska crowd-observationer hämtades först idag. Äldre källtider var ibland sentinelår 0001; nyare historiska källtider låg efter spelstopp. Därför finns **0 historiska kompletta pre-close-batcher** och **0 avslutade draws med egna sparade pre-close-system**. Vi har inte skapat historiska forecasts, kopierat referensstreck till påhittade tidpunkter eller använt resultat som modellfeatures.

Exempel på verklig utdelning, omgång **4969, 2026-09-05**:

| Rätt | SEK per vinnande rad | Antal vinnare |
|---|---:|---:|
| 13 | 764 705 | 17 |
| 12 | 6 227 | 491 |
| 11 | 383 | 6 372 |
| 10 | 98 | 51 783 |

Resultatendpointen är singular `/draws/{number}/result`. Facitets event-ID:n kontrolleras mot arkiverad kupong, 1/X/2 kontrolleras mot mål där tillämpligt och belopp hanterar decimalcomma. Saknade värden blir null. Arkivet kan visa slutdata efterhand med tydlig tidsmarkering; före-stopp-vyn visar att förhandsobservation saknas.

## Diagnostik med riktig crowd

De tolv villkoren är **fyra budgetar × tre profiler på en enda verklig omgång**. Upprepade analyser räknas endast en gång per omgång/budget/profil. De är inte tolv oberoende historiska omgångar.

| Tecken | Antal av 156 matchval |
|---|---:|
| 1 | 72 |
| X | 0 |
| 2 | 17 |
| 1X | 0 |
| 12 | 24 |
| X2 | 6 |
| 1X2 | 37 |

Genomsnittlig krysstäckning är **27,56 % av matcherna**, och budgetutnyttjandet **92,68 %**. [Maskinrapporten](optimizer-real-crowd-v3.json) visar varje budget/profil, exakt snapshot-ID, rad, kostnad och skattad täckningssannolikhet. Datasetet är fortfarande för litet för prestationsslutsatser; inga påståenden om lönsamhet eller faktisk optimizerförbättring görs. Prompt 2:s syntetiska diagnostik ligger kvar separat.

## API och gränssnitt

Aktuell kupong laddas automatiskt med LIVE DATA, draw-selector, spelstopp, freshness, health och mapping. Saknas aktuell livekupong finns tydlig demo-fallback. Saknas enskilda odds kan de kompletteras manuellt med eget källmärke, utan att crowd ändras. Ofullständiga kuponger presenteras inte som färdiga system.

Matchdetaljer visar sparad streckhistorik. Analys visar största faktiskt observerade rörelser. Avancerad systemvy visar teckenändringar mot förra jämförbara analysen. Historik visar tidigare draws, faktisk tidsgräns, tillgänglig crowd/market/sparad prediction, system och separat facit/utdelning. Tidigare market/v1/v2-modelldiagnostik finns kvar.

Viktiga API-routes är `/api/coupon/current`, `/api/coupon/current/refresh`, `/api/coupon/current/analyze`, `/api/stryktipset/status`, `/api/stryktipset/draws` och `/api/stryktipset/draws/{number}`. Fullt kontrakt finns på lokala `/docs`. Gamla manuella current-routen heter nu `/api/coupon/manual/current`.

Skärmbilder från det verkliga lokala API:t: [desktop](screenshots/live-v3-desktop.png), [mobil](screenshots/live-v3-mobile.png), [crowd-historik](screenshots/live-v3-crowd.png), [historiskt facit/utdelning](screenshots/live-v3-archive.png).

## Verifiering och kvarvarande begränsningar

**93 backendtester**, **16 Playwright-tester** för desktop/mobil och godkänt Angular-produktionsbygge. Backend har två befintliga deprecation-varningar från testklientens beroenden. Externa anrop är mockade i automatiska tester; separat read-only-körning använde riktig provider och hela lokala analyskedjan. Verklig UI-inspektion gav inga JavaScriptfel eller horisontellt överflöde på mobil.

Tester omfattar verkliga current/specific/legacy/result-fixtures, exakt 13 matcher, schema drift, saknade/ogiltiga fält, lagmappning, odds/crowd-separation, källfel med cache, HTTP-retries, immutable snapshots, pre-close-val 15:55 framför 16:05, nekad framtida observation, ofullständig senaste batch, fixturebyte, klientmanipulerad liveinput, oförändrad P_model vid crowdändring, resultat/payout och automatisk UI-fallback.

Källan är odokumenterad. Oddsen är observerade från kupongflödet och utgör inte bookmakerkonsensus. Fler riktiga förhandsobservationer och avslutade omgångar behöver samlas innan optimizer-backtest kan säga något om faktisk prestation. Kontinuerlig worker och backup behöver konfigureras vid drift. Aktuell kupong och dess odds kan ändras efter rapportens hämtningstid.

News extraction, scoring, crawling, LLM-inställningar och sannolikhetskorrigeringar har inte utökats. Den enda arkitekturanpassningen där är återanvänd arkivbas, tydligare manuell current-route och koppling av serververifierad livekupong till befintligt kupongarkiv. Aktiv market-policy, tidigare modellartefakt och optimizerobjektiv är bevarade.
