# Slutrapport – Prompt 2

Implementerad och verifierad 2026-09-09. **Marknadsbaseline är aktiv. Model v2 slår inte marknaden över hela walk-forward-perioden.** Nyhetskedjan är separat och ändrar inga 1/X/2-sannolikheter.

## Model Intelligence

23 741 historiska matcher, varav 23 740 med användbara marknadssannolikheter. Sex walk-forward-perioder, 2020/21–2025/26, omfattar 8 904 testmatcher. V1 är samma modellfamilj och inställningsgrid som Prompt 1, omtränad för respektive period. V2 är den valda residualkandidaten `promotion_75`, inte aktiv deployment.

| Modell | Log Loss ↓ | Brier ↓ | Accuracy | Macro ECE ↓ |
|---|---|---|---|---|
| Marknad | 1.011519 | 0.605626 | 50.30% | 0.014143 |
| Model v1 | 1.013304 | 0.606486 | 50.55% | 0.016374 |
| Model v2 | 1.011606 | 0.605667 | 50.33% | 0.012132 |

V2 ger marginellt sämre Log Loss och Brier men lägre sammanlagd ECE. Det räcker inte för deployment. Variantvalet använder 2020/21–2024/25; kandidatscoren på dessa perioder är urvalsresultat. Inga konfidensintervall eller statistiskt säkerställda vinster påstås.

### Resultat per liga

#### Premier League – 2280 matcher

| Modell | Log Loss ↓ | Brier ↓ | Accuracy | Macro ECE ↓ |
|---|---|---|---|---|
| Marknad | 0.966840 | 0.574370 | 54.69% | 0.023860 |
| Model v1 | 0.970703 | 0.575939 | 54.34% | 0.027596 |
| Model v2 | 0.966987 | 0.574303 | 54.61% | 0.024230 |

#### Championship – 3312 matcher

| Modell | Log Loss ↓ | Brier ↓ | Accuracy | Macro ECE ↓ |
|---|---|---|---|---|
| Marknad | 1.035830 | 0.622958 | 47.31% | 0.018993 |
| Model v1 | 1.037903 | 0.624457 | 48.13% | 0.021465 |
| Model v2 | 1.036190 | 0.623246 | 47.34% | 0.016869 |

#### League One – 3312 matcher

| Modell | Log Loss ↓ | Brier ↓ | Accuracy | Macro ECE ↓ |
|---|---|---|---|---|
| Marknad | 1.017965 | 0.609812 | 50.27% | 0.023071 |
| Model v1 | 1.018032 | 0.609545 | 50.36% | 0.019602 |
| Model v2 | 1.017738 | 0.609679 | 50.36% | 0.019796 |

V2 försämrar Log Loss i Premier League och Championship. League One förbättras mycket svagt i både Log Loss och Brier; det motiverar ingen separat ligamodell.

### Säsonger och audit

| Säsong | Marknad LL | V1 LL | V2 LL | Δ V2–marknad |
|---|---|---|---|---|
| 2020-21 | 1.032114 | 1.035965 | 1.032979 | +0.000865 |
| 2021-22 | 0.996190 | 0.995833 | 0.995677 | -0.000513 |
| 2022-23 | 1.014300 | 1.016696 | 1.015095 | +0.000795 |
| 2023-24 | 0.991909 | 0.992580 | 0.991929 | +0.000020 |
| 2024-25 | 1.007737 | 1.009336 | 1.007492 | -0.000245 |
| 2025-26 | 1.026863 | 1.029413 | 1.026465 | -0.000398 |

Audit 2025/26, 1 484 matcher (utesluten från v2-urval; redan observerad i Prompt 1):

| Modell | Log Loss ↓ | Brier ↓ | Accuracy | Macro ECE ↓ |
|---|---|---|---|---|
| Marknad | 1.026863 | 0.617063 | 48.79% | 0.015191 |
| Model v1 | 1.029413 | 0.618530 | 48.45% | 0.023918 |
| Model v2 | 1.026465 | 0.616816 | 48.52% | 0.016866 |

V2 förbättras svagt under audit men försämrar ECE och kan inte räddas av en enskild säsong. Den aktiva marknaden ändras därför inte.

### Ablation och modellval

Development 2020/21–2024/25, samma 7 420 matcher för samtliga varianter. Negativ delta betyder förbättring.

| Variant | Log Loss | Δ LL | Δ Brier | Vinnande säsonger / 5 |
|---|---|---|---|---|
| market | 1.008450 | +0.000000 | +0.000000 | 0 |
| elo | 1.008678 | +0.000228 | +0.000056 | 3 |
| form | 1.009193 | +0.000743 | +0.000366 | 3 |
| venue | 1.008831 | +0.000381 | +0.000183 | 3 |
| full | 1.008676 | +0.000226 | +0.000120 | 2 |
| league_interactions | 1.008716 | +0.000266 | +0.000137 | 1 |
| season_085 | 1.008675 | +0.000225 | +0.000122 | 2 |
| season_065 | 1.008677 | +0.000227 | +0.000125 | 2 |
| promotion_75 | 1.008634 | +0.000184 | +0.000098 | 2 |
| temperature | 1.008795 | +0.000345 | +0.000249 | 2 |

`elo` = marknad + Elo. `form` lägger till rullande form; `venue` lägger till hemma/borta; `full` lägger till vila. `league_interactions` testar ligaspecifika korrektioner; `season_085/065` säsongsregression; `promotion_75` regression 0,85 och divisionsjustering; `temperature` separat temporal kalibrering.

Ingen featuregrupp eller experimentvariant gav tillräcklig förbättring på development. Den bästa residualkandidaten vann endast 2 av 5 säsonger. All historik kan visas i UI, men inga Elo/form/vila- eller övergångskorrektioner används i den aktiva modellen. Samtliga sex perioders ablation finns även maskinläsbart.

### Avvikelse från marknaden

Bucket = största absoluta skillnaden mellan modellens och marknadens tre sannolikheter.

| Modell | Avvikelse | N | Marknad LL | Modell LL | Δ LL |
|---|---|---|---|---|---|
| v1 | 0-2pp | 2242 | 1.021427 | 1.022128 | +0.000701 |
| v1 | 2-5pp | 5061 | 1.013899 | 1.014198 | +0.000298 |
| v1 | 5-8pp | 1416 | 0.990413 | 0.995246 | +0.004833 |
| v1 | 8+pp | 185 | 0.987867 | 1.020126 | +0.032259 |
| v2 | 0-2pp | 8144 | 1.011719 | 1.011567 | -0.000151 |
| v2 | 2-5pp | 736 | 1.006477 | 1.005899 | -0.000578 |
| v2 | 5-8pp | 20 | 1.121815 | 1.152504 | +0.030689 |
| v2 | 8+pp | 4 | 0.981220 | 1.435931 | +0.454711 |

Större avvikelse innebär inte automatiskt mer information. Tomma eller små buckets ger inget stöd för stora korrektioner. Aktiv baseline avviker exakt 0 procentenheter.

### Matchtyper

| Bucket | N | Marknad LL | V1 LL | V2 LL | Δ V2 Brier |
|---|---|---|---|---|---|
| favourite_<40 | 2004 | 1.090011 | 1.090270 | 1.090175 | +0.000133 |
| favourite_40-50 | 3534 | 1.062854 | 1.065671 | 1.063235 | +0.000186 |
| favourite_50-60 | 2059 | 0.982256 | 0.980976 | 0.981245 | -0.000676 |
| favourite_60-70 | 877 | 0.869886 | 0.874679 | 0.871079 | +0.000905 |
| favourite_70+ | 430 | 0.652799 | 0.661754 | 0.653107 | +0.000080 |
| very_even | 2367 | 1.087658 | 1.088775 | 1.088128 | +0.000331 |
| moderately_even | 3485 | 1.057124 | 1.058933 | 1.057114 | -0.000060 |
| clear_favourite | 2339 | 0.953659 | 0.954492 | 0.953196 | -0.000264 |
| heavy_favourite | 713 | 0.725654 | 0.732662 | 0.726752 | +0.000566 |
| home_favourite | 5991 | 0.999647 | 1.001340 | 1.000049 | +0.000278 |
| away_favourite | 2913 | 1.035936 | 1.037909 | 1.035374 | -0.000447 |
| draw_heavy | 477 | 1.090176 | 1.093709 | 1.091214 | +0.000602 |
| early_season | 2503 | 1.015853 | 1.017059 | 1.016240 | +0.000238 |
| mid_season | 3850 | 1.015851 | 1.017539 | 1.015854 | +0.000030 |
| late_season | 2551 | 1.000728 | 1.003227 | 1.000648 | -0.000136 |

Balans använder skillnaden mellan marknadens två största sannolikheter: <10, 10–25, 25–45 och ≥45 procentenheter. Draw-heavy betyder kryss ≥30 %. Early/mid/late är juli–oktober, november–februari respektive mars–juni; COVID-förskjutna spelscheman justeras inte. Buckets överlappar mellan olika diagnostikdimensioner.

### Kalibrering per klass

20 bin om 5 procentenheter, separat för 1/X/2. Tabellen visar klassvis ECE; alla bin med antal, predikterad andel och observerad frekvens finns i evaluation-v2.json och i Historik-vyn.

| Modell | ECE 1 | ECE X | ECE 2 |
|---|---|---|---|
| Marknad | 0.014023 | 0.013727 | 0.014679 |
| Model v1 | 0.014681 | 0.018039 | 0.016403 |
| Model v2 | 0.014735 | 0.009624 | 0.012038 |

## Optimizerdiagnostik

684 icke-överlappande block med 13 historiska testmatcher. Tre scenarier × tre profiler × fyra budgetar = 24 624 optimeringar. Matcher i ett block kan ligga på flera datum. **Svenska Folket är simulerat** som normaliserad marknad upphöjd till 1,0 / 1,3 / 0,8 (marknadslik / favoritbetonad / skrällbetonad). Det är beteendediagnostik, inget payout-backtest. Objective är oförändrat.

### market_like

| Profil | Budget | Spikar | Halva | Hela | Utnyttjat | 1X / 12 / X2 | Matcher med X |
|---|---|---|---|---|---|---|---|
| optimal | 64 | 8.03 | 3.42 | 1.55 | 91.9% | 9.1% / 87.5% / 3.4% | 15.2% |
| optimal | 128 | 7.52 | 3.19 | 2.29 | 88.1% | 13.8% / 81.4% / 4.8% | 22.2% |
| optimal | 256 | 7.93 | 0.19 | 4.88 | 94.9% | 3.1% / 95.3% / 1.6% | 37.6% |
| optimal | 512 | 7.00 | 1.00 | 5.00 | 94.9% | 31.1% / 57.2% / 11.7% | 41.8% |
| safe | 64 | 8.02 | 3.44 | 1.54 | 92.0% | 9.2% / 87.5% / 3.4% | 15.1% |
| safe | 128 | 7.49 | 3.27 | 2.24 | 88.3% | 13.8% / 81.4% / 4.8% | 21.9% |
| safe | 256 | 7.93 | 0.19 | 4.88 | 94.9% | 3.1% / 95.3% / 1.6% | 37.6% |
| safe | 512 | 7.00 | 1.00 | 5.00 | 94.9% | 31.1% / 57.2% / 11.7% | 41.8% |
| value | 64 | 8.05 | 3.38 | 1.57 | 91.8% | 8.8% / 87.9% / 3.4% | 15.2% |
| value | 128 | 7.55 | 3.12 | 2.33 | 87.9% | 13.8% / 81.3% / 4.9% | 22.4% |
| value | 256 | 7.93 | 0.19 | 4.88 | 94.9% | 3.1% / 95.3% / 1.6% | 37.6% |
| value | 512 | 7.00 | 1.00 | 5.00 | 94.9% | 31.1% / 57.2% / 11.7% | 41.8% |

### favourite_biased

| Profil | Budget | Spikar | Halva | Hela | Utnyttjat | 1X / 12 / X2 | Matcher med X |
|---|---|---|---|---|---|---|---|
| optimal | 64 | 7.78 | 4.04 | 1.18 | 93.9% | 10.3% / 86.0% / 3.7% | 13.4% |
| optimal | 128 | 7.28 | 3.80 | 1.92 | 90.0% | 14.3% / 80.7% / 5.0% | 20.4% |
| optimal | 256 | 7.92 | 0.23 | 4.86 | 95.0% | 3.2% / 95.5% / 1.3% | 37.4% |
| optimal | 512 | 7.00 | 1.00 | 5.00 | 94.9% | 30.7% / 57.9% / 11.4% | 41.7% |
| safe | 64 | 8.00 | 3.51 | 1.50 | 92.2% | 9.3% / 87.3% / 3.4% | 14.9% |
| safe | 128 | 7.48 | 3.30 | 2.22 | 88.4% | 13.8% / 81.4% / 4.8% | 21.8% |
| safe | 256 | 7.93 | 0.20 | 4.88 | 95.0% | 3.7% / 94.8% / 1.5% | 37.6% |
| safe | 512 | 7.00 | 1.00 | 5.00 | 94.9% | 31.1% / 57.2% / 11.7% | 41.8% |
| value | 64 | 7.34 | 5.14 | 0.51 | 97.3% | 13.5% / 81.4% / 5.1% | 11.3% |
| value | 128 | 6.74 | 5.15 | 1.11 | 94.2% | 17.0% / 76.6% / 6.4% | 17.8% |
| value | 256 | 7.85 | 0.41 | 4.74 | 95.2% | 3.6% / 95.4% / 1.1% | 36.6% |
| value | 512 | 7.00 | 1.01 | 4.99 | 94.9% | 29.8% / 60.3% / 10.0% | 41.5% |

### longshot_biased

| Profil | Budget | Spikar | Halva | Hela | Utnyttjat | 1X / 12 / X2 | Matcher med X |
|---|---|---|---|---|---|---|---|
| optimal | 64 | 8.14 | 3.15 | 1.71 | 91.1% | 8.3% / 88.7% / 3.0% | 15.9% |
| optimal | 128 | 7.63 | 2.93 | 2.44 | 87.3% | 13.9% / 81.1% / 5.0% | 23.1% |
| optimal | 256 | 7.94 | 0.16 | 4.90 | 94.9% | 2.8% / 96.3% / 0.9% | 37.7% |
| optimal | 512 | 7.00 | 1.00 | 5.00 | 94.9% | 31.4% / 57.0% / 11.5% | 41.8% |
| safe | 64 | 8.03 | 3.42 | 1.55 | 91.9% | 9.1% / 87.5% / 3.4% | 15.2% |
| safe | 128 | 7.51 | 3.22 | 2.27 | 88.2% | 13.8% / 81.3% / 4.8% | 22.1% |
| safe | 256 | 7.93 | 0.19 | 4.88 | 94.9% | 3.1% / 95.3% / 1.6% | 37.6% |
| safe | 512 | 7.00 | 1.00 | 5.00 | 94.9% | 31.1% / 57.2% / 11.7% | 41.8% |
| value | 64 | 8.31 | 2.72 | 1.97 | 89.7% | 7.5% / 89.9% / 2.6% | 17.3% |
| value | 128 | 7.73 | 2.67 | 2.60 | 86.5% | 14.2% / 80.9% / 4.9% | 23.9% |
| value | 256 | 7.94 | 0.15 | 4.90 | 94.8% | 1.9% / 98.1% / 0.0% | 37.7% |
| value | 512 | 7.00 | 1.00 | 5.00 | 94.9% | 31.7% / 56.9% / 11.4% | 41.8% |

### Alla teckenkombinationer

| Tecken | Antal | Andel av alla val |
|---|---|---|
| 1 | 136204 | 42.55% |
| X | 0 | 0.00% |
| 2 | 50492 | 15.77% |
| 1X | 7132 | 2.23% |
| 12 | 40739 | 12.73% |
| X2 | 2588 | 0.81% |
| 1X2 | 82957 | 25.91% |

12 dominerar bland halvgarderingarna i flera scenarier. När både hemma- och bortaseger är mer sannolika än kryss ger 12 störst täckt sannolikhet bland halvgarderingarna. Dessutom påverkar helgarderingar och budgetens multiplikativa steg hela lösningen: få halvgarderingar kan ge en extrem procentfördelning. Exempelvis i marknadslik Optimal/256 är 95,3 % av endast 127 halvgarderingar 12, samtidigt som 3 340 helgarderingar täcker kryss. Genomsnittlig marknadssannolikhet för kryss är 26,13 %. Andelen matcher där X ingår är inte samma storhet som denna utfallssannolikhet. Fördelningen motiverar inte ensam ändrat objective.

## News Intelligence – verklig insamling

Körning 2026-09-09T19:23:47.939484+00:00, provider `rss`, extractor `rules:evidence-v2`. Kupong `demo-13` har verkliga lagnamn men **fiktiva DEMO-matcher/odds/streck**, inte verifierad aktuell Stryktipsomgång. Artiklarna är verkligt hämtade.

| Mått | Antal |
|---|---|
| Genererade queries | 65 |
| Artikelträffar i unika råsvar | 227 |
| Unika artiklar (URL) | 218 |
| Deduplicerade träffar | 9 |
| Aktiva events / signals | 1 |
| Matcher med signals | 1 |
| Uppdaterade matcher | 13 |
| Cacheträffar | 65 |
| HTTP-anrop i denna körning | 0 |

Insamlingen gjorde 28 verkliga RSS-anrop i den föregående hämtningen (2 globala + 26 lagflöden). Ovanstående körning återanvände cachen för extraktion. Artikelräknaren räknar inte om samma råsvar för varje query. Databasen innehåller 219 artikelversioner för 218 URL:er över körningarna.

### Granskningsbart exempel: Bolton–Reading, demomatch 12

En artikelversion → ett event → en `PLAYER_RETURN`-signal för Reading. Källa: [bbc: Reading FC](https://bbc.co.uk/sounds/play/p0p8nzmg).

> Reading Winger back after a lengthy injury.

Publicerad 2026-09-09T07:02:00Z; hämtad 2026-09-09T19:19:23.290157Z; signal registrerad 2026-09-09T19:23:47.939484+00:00. Spelaren är anonym i underlaget och `player_id` är null. Inget påstående görs om ordinarieplats eller hur mycket återkomsten påverkar matchen. Status är Rapporterad, inte officiellt bekräftad. Källan är BBC Radio Berkshire via BBC:s Reading-flöde och gäller en ljudsida; extraktionen använder endast den tillgängliga RSS-texten.

Event-ID `616a80016f59b329b23b427b4a51cc81`, artikelversion `f6cb1355ab28aadaf201b013ae14a6c5`. Rådata `raw\d9757c37b92630869dc7e67f328564a0215f7be653d0e4abf8af20789023a4c5.raw`. Full provenance finns i [news-verification-v2.json](news-verification-v2.json).

### Datakvalitet

| Mått | Utfall |
|---|---|
| Signals per typ | {"PLAYER_RETURN": 1} |
| Source tiers | {"2": 218} |
| Events med flera källor | 0.0% |
| Extraktionsfel | 0 |
| Artiklar utan konkreta extraherade signals | 145 |
| Artiklar utanför sju dagar | 72 |
| Okänd publiceringstid | 0 |
| Misslyckade anrop | 0 |

145 artiklar gav inga konkreta regelbaserade signaler; det betyder inte att alla saknar relevant information för en mänsklig läsare. Alla 218 källartiklar är tier 2, och enda eventet saknar oberoende bekräftelse. Den begränsade täckningen är inte tillräcklig för slutsatser om nyheters prognosvärde.

Brave/Tavily och strict LLM-extraktion är implementerade och testade med mockade kontrakt/fel, men inte verifierade med betalda live-anrop eftersom credentials saknas. RSS/rules är det verkligt körda alternativet. Paywalls, saknad fulltext, ljudmaterial, tvetydiga spelarnamn, gamla uppgifter och saknade lokala EFL-källor begränsar datakvaliteten. Inga historiska nyhetsutfall har konstruerats.

## Verifiering och UI

59 backendtester och 8 Playwright-tester (desktop/mobil) godkända; produktionsbygget lyckades. Två deprecation-varningar kommer från FastAPI/Starlette-testberoenden. Tester täcker temporal ordning, calibration utan framtida mål, reproducerbarhet, sannolikhetssummor, dedupe, källprioritet, oföränderliga snapshots, oddsrevertering, partiella fel, API-fel och LLM-refusal/ogiltig output. Externa nyhetsanrop är mockade i testsuiten.

Riktigt API verifierat för 3 profiler × 4 budgetar och samtliga 13 matcher. Aktiv marknad ger exakt samma sannolikheter som oddsbaselinen. Automatiserade tester verifierar att news-update inte ändrar prediktioner och att sparade källor/signaler finns kvar efter uppdateringsfel.

Demokupongens Optimal/256 använder 243.0 kr. Systemets 13-rättssannolikhet visas tillsammans med ungefärlig 1-på-n och antagandet om oberoende matcher. Detta är en modelluppskattning, inte en utbetalningsprognos.

Historik visar marknad/v1/v2, aktiv modell, ligor, säsonger, ablation, marknadsbuckets, avvikelser och kalibreringsbin. Matchens Nyheter-flik visar grupperade signals, status, tidsstämplar, belägg och originallänkar. Modell- och nyhetsvyerna förklarar att nyheter ännu inte påverkar sannolikheterna.

## Levererade underlag och nästa steg

[Teknisk metod, datamodell och begränsningar](model-news-v2.md). [README och körkommandon](../README.md). [Full maskinläsbar evaluation](evaluation-v2.json). [Optimizerdiagnostik](optimizer-diagnostics-v2.json). [API-verifiering](verification-v2.json). Modellvikter och walk-forward-Parquet ligger i backend/artifacts; råa nyheter, SQLite och exporter i backend/data/news.

Prompt 3 kan använda match-/lag-/spelarnycklar, signaltyp, källa, publicerings- och registreringstid samt snapshots. `news_signals.parquet` och `news_snapshots.parquet` är exporterade. Inga news-aware features, godtyckliga spelarvikter eller tränade nyhetskorrektioner har införts. Nästa steg kräver mer tidsstämplad data och separat utvärdering.
