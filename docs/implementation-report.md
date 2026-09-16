# Slutrapport — Stryktipset Predictor MVP

Verifierad 2026-09-09T18:48:59.876929+00:00. Alla siffror nedan kommer från körd pipeline och API.

## Implementerat

- Angular 21 med svensk desktop-/mobilvy enligt den befintliga UI/UX-specifikationen.
- FastAPI med validerad 13-matchers kupong, modellstatus, lagsökning, prediction, analys, optimizer och central kostnadsberäkning.
- Automatisk Football-Data-import, immutable rådata, per-fil-manifest, cache, återförsök, normalisering och Parquet.
- Verklig logistisk regressionsmodell med Elo, tidigare form, hemma/bortastyrka, vila och de-viggad marknad; reproducerbara artefakter och separat temporalt sluttest.
- Edge/value, deterministisk DP-optimizer, tre faktiska profiler, manuella tecken, prisuppdatering och kopiering av system.

## Dataset

| Liga | Normaliserade matcher |
|---|---:|
| Premier League (E0) | 6,110 |
| Championship (E1) | 8,892 |
| League One (E2) | 8,739 |
| **Totalt** | **23,741** |

51/51 CSV-filer hämtades från 2010/11–2026/27. 0 importfel. Data till och med 2026-09-07.
23,740 matcher har kompletta tillåtna marknadsodds och ingår i modellträningen. En match saknar sådana odds men kan bidra till efterföljande historiska features.

## Modell

Multinomial logistisk regression, C=0.1, fixed seed=42. 50 inputs före one-hot-kodning av ligan.

- 3 Elo-inputs: hemma före match, borta före match, skillnad inklusive hemmaplansfördel.
- 3 de-viggade marknadssannolikheter.
- 40 rolling-inputs: två lag × två fönster (5/10) × fem mått (poäng, mål för/emot, skott, skott på mål) × total/hemma-borta.
- 3 viloinputs samt liga.

| Period | Från | Till | Matcher med odds |
|---|---|---|---:|
| Train / modellval | 2010-08-06 | 2024-05-19 | 20,623 |
| Validation | 2024-08-09 | 2025-05-25 | 1,484 |
| Test | 2025-08-01 | 2026-05-24 | 1,484 |
| Omträning före test | 2010-08-06 | 2025-05-25 | 22,107 |
| Deploymentmodell | 2010-08-06 | 2026-09-07 | 23,740 |

Validation väljer regularisering utan att använda testutfall. Testets modellvikter är frysta före testperioden. Form och Elo uppdateras löpande med enbart tidigare datum. Deploymentmodellen tränas därefter på all tillgänglig historik; sluttestmåtten kommer från den separata utvärderingsmodellen.

## Baseline comparison

| Sluttest 2025/26 | Log Loss ↓ | Brier ↓ | Accuracy ↑ |
|---|---:|---:|---:|
| Bookmaker baseline | 1.026863 | 0.617063 | 48.79% |
| ML-modell | 1.029413 | 0.618530 | 48.45% |

**ML-modellen slår inte marknadsbaselinen i detta första test.** Det är ett fungerande baseline-experiment, inte evidens för lönsamhet. Multiclass Brier är summan av tre kvadrerade fel, sedan medelvärde över matcher (0–2). Kalibreringsbin per utfall sparas i modellmetadata och evaluation.json.

## Optimizer

Optimizern maximerar en additiv kombination av log-täckning, modellviktad edge och log-värde, minus kostnad för garderingar. Exakt DP över möjliga radprodukter väljer mellan alla sju teckenkombinationer. Radkostnaden räknas med Decimal. Vikterna skiljer mellan Optimal, Säker och Värde.

Se [exakt objective, vikter, algoritm och mått](optimizer.md). Hela budgeten måste inte användas om ett billigare system har högre score. Optimizern modellerar inte faktisk utdelning.

| Profil | Budget kr | Faktisk kostnad kr | Rader | Spikar | Halv | Hel |
|---|---:|---:|---:|---:|---:|---:|
| optimal | 64 | 64 | 64 | 7 | 6 | 0 |
| optimal | 128 | 128 | 128 | 6 | 7 | 0 |
| optimal | 256 | 256 | 256 | 5 | 8 | 0 |
| optimal | 512 | 512 | 512 | 4 | 9 | 0 |
| safe | 64 | 64 | 64 | 7 | 6 | 0 |
| safe | 128 | 128 | 128 | 6 | 7 | 0 |
| safe | 256 | 256 | 256 | 5 | 8 | 0 |
| safe | 512 | 486 | 486 | 7 | 1 | 5 |
| value | 64 | 64 | 64 | 7 | 6 | 0 |
| value | 128 | 108 | 108 | 8 | 2 | 3 |
| value | 256 | 243 | 243 | 8 | 0 | 5 |
| value | 512 | 486 | 486 | 7 | 1 | 5 |

Alla 12 systemen höll budgeten. Varje körning hade exakt 13 matcher och ML-prognoser som summerade till 1.

## UI

- **Översikt:** optimal rad, kostnad, garderingar, värdeindex, budget/profil, exakt tre insikter och 13 matchkort.
- **Kupong:** redigerbara lag/liga/datum/odds/folkstreck, lagsökning, ny tom kupong, crowd-validering, förvalda tecken, manuella ändringar, återställning och kopiering.
- **Matchdetaljer:** högerdrawer på desktop, helskärm på mobil, fungerande Översikt/Form/Modell. Nyheter visar endast begärd placeholder.
- **Analys:** alla 39 tecken med modell, marknad, streck, edge och värde.
- **Historik:** verklig modellstatus, perioder, dataset, jämförelsemått och tom livehistorik utan påhittade resultat.
- Skeleton, fel/återförsök, märkt fallback, fokusstöd och mobil bottennavigation.

## Demo — verklig API-körning med fiktivt kupongunderlag

**DEMO DATA:** matcher, odds och folkstreck är exempel. Alla 13 prognoser nedan kommer från den tränade modellen; ingen statisk prediction har använts.

**Optimal rad · 256 kr · 256 rader**

```text
1 | 12 | 2 | 12 | 1 | 12 | 12 | 12 | 1 | 12 | 1X | 1 | 1X
```

5 spikar, 8 halvgarderingar, 0 helgarderingar. Värdeindex 1.0070.

| # | Match | Modell 1 / X / 2 | Val |
|---|---|---|---|
| 1 | Arsenal – Everton | 64.9% / 22.1% / 13.0% | 1 |
| 2 | Fulham – Brighton | 38.6% / 24.0% / 37.4% | 12 |
| 3 | Leeds – Chelsea | 19.4% / 24.5% / 56.1% | 2 |
| 4 | Coventry – Burnley | 39.4% / 26.9% / 33.7% | 12 |
| 5 | Liverpool – Newcastle | 63.8% / 20.6% / 15.6% | 1 |
| 6 | Manchester United – Aston Villa | 45.3% / 25.9% / 28.8% | 12 |
| 7 | West Ham – Crystal Palace | 37.0% / 24.9% / 38.0% | 12 |
| 8 | Norwich – Watford | 42.5% / 25.4% / 32.1% | 12 |
| 9 | West Brom – QPR | 52.6% / 28.5% / 18.9% | 1 |
| 10 | Preston – Stoke | 32.0% / 25.8% / 42.2% | 12 |
| 11 | Sheffield United – Blackburn | 50.4% / 27.2% / 22.5% | 1X |
| 12 | Bolton – Reading | 51.6% / 26.1% / 22.4% | 1 |
| 13 | Sunderland – Hull | 43.5% / 31.1% / 25.5% | 1X |

Geometrisk täckning per match: 0.6766. Approximerad sannolikhet för 13 rätt under oberoendeantagande: 0.6224%. Dessa är olika mått; värdeindex är inte ekonomisk avkastning.

## Verifiering

- **37 backendtester passerade:** de-vig, nullkolumner/oddsfallback, rolling- och datumläckage, Elo, alias, edge/value/nollstreck, kostnad, profiler, DP mot brute force på liten kupong, budgetar, validering, fallback, API och immutable download/cache.
- **6 Playwright-tester passerade** mot riktigt API: tre flöden på både desktop och mobil. Alla budgetar, 13 ML-prognoser, matchflikar, crowd-fel, oddsändring, manuella tecken, återställning, analys/historik och API-fel/återhämtning.
- **Angular production build passerade** med strict TypeScript och templates.
- **Download, normalize, train och evaluate kördes** på verklig källdata.
- En andra pipelinekörning återanvände **51/51 cachefiler utan omhämtning** och reproducerade samtliga tre sluttestmått inom 1e−12.
- **12 kompletta optimeringar** verifierades separat över HTTP; inga budgetöverträdelser.
- Desktop och mobil granskades visuellt via webbläsarscreenshots.

Maskinläsbart underlag: [verification.json](verification.json). Fullständig lokal körning inklusive form/features finns i backend/artifacts/demo_verification.json. Testbilder finns i frontend/test-results/.

## Kända begränsningar

- Svenska Folket och aktuell kupong/odds matas in manuellt; demounderlaget är inte ett aktuellt spelprogram.
- ML förbättrar inte marknaden på detta sluttest. Vikterna för spelvärde är initiala, inte avkastningskalibrerade.
- Ingen payout-/jackpotmodell, inga korrelationer mellan matcher, inga verkliga avkastnings- eller livekupongmått.
- Historiska opening-odds saknar exakta observationstider. Closing-odds är exkluderade, men ett bestämt T−24h-beslut kan inte backtestas säkert med denna datakälla ensam.
- Modellparametrar är enklare baselines: ingen separat kalibreringsmodell, säsongs-/uppflyttningsjustering eller walk-forward-parameteroptimering.
- Lagnamn normaliseras centralt; ännu okända lag eller färre än fem matcher ger märkt marknadsfallback. Deploymentmodellens historiska datum ger också fallback för att förhindra framtidsläckage.
- Nyheter, skador, rotation och lineups ingår inte. Nyhetsfliken är uttryckligen en placeholder.
- Manuell kupong och tecken lagras i arbetsminnet; omladdning återställer demo. Snapshotfält finns men någon automatisk snapshotdatabas finns inte ännu.
- Lokalt MVP-upplägg utan inloggning, driftplattform eller spelinlämning.

## Nästa logiska steg

En tillförlitlig integration för kupong/Svenska Folket/odds med tidsstämplade snapshots, följd av News Intelligence-pipeline och walk-forward-jämförelse mot marknadsbaselinen.
