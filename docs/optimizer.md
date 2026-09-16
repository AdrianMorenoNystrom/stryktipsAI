# Optimizer v1

”Optimal rad” är det system som maximerar nedanstående heuristik inom budgeten. Det är inte en exakt förväntad utbetalning. Modellsannolikhet, streck och rekommendation är separata begrepp.

## Matchpoäng

För match `i`, vald delmängd `S` av `{1, X, 2}`, modellprocent `p_j` och normaliserade folkstreck `q_j`:

```text
P(S) = sum(p_j for j in S)
E(S) = sum(p_j * (p_j - q_j) for j in S) / P(S)
V(S) = sum(p_j * log(p_j / max(q_j, 0.005)) for j in S) / P(S)

score(S) = a * log(P(S)) + b * E(S) + c * V(S) - d * log(|S|)
objective(system) = sum(score(S_i) for i in 1..13)
```

Sannolikhetstäckningen belönar garderingar. Modellviktad edge och log-värde premierar tecken med lägre folkstreck än prognosen. Att använda modellvikter gör att ett ytterst osannolikt tecken inte får dominera en gardering enbart på grund av låga streck. Kostnadstermen gör ytterligare tecken mindre attraktiva om de tillför för lite. Budgeten är dessutom en hård gräns.

| Profil | a: täckning | b: edge | c: log-värde | d: kostnad |
|---|---:|---:|---:|---:|
| Optimal | 1.00 | 0.65 | 0.30 | 0.04 |
| Säker | 1.40 | 0.10 | 0.04 | 0.04 |
| Värde | 0.80 | 1.20 | 0.70 | 0.04 |

Vikterna finns i `app/config.py`, objective i `app/services/objective.py`. De är initiala produktval, inte ekonomiskt kalibrerade koefficienter. Profilen Säker ökar sannolikhetsvikten; det innebär ingen garanti om lägre faktisk spelrisk.

Nollstreck golvas vid 0,5% enbart i värdeberäkningen, vilket flaggas i matchanalysen. Rå edge använder den faktiska normaliserade streckfördelningen. Numeriskt skydd mot `log(0)` använder 1e−12.

## Exakt dynamisk programmering för denna objective

Varje match har sju alternativ: `1`, `X`, `2`, `1X`, `12`, `X2`, `1X2`. DP-tillståndet är antal behandlade matcher och exakt radantal. Endast radantal av formen `2^d * 3^t`, där `d+t <= 13`, kan uppstå: högst 105 kombinationer av d/t totalt. Detta gör sökningen liten.

För varje tillstånd provas nästa matchs sju alternativ. Tillstånd över `floor(budget / costPerRow)` kastas bort. För samma radantal behålls systemet med högst additiv poäng. Detta är exakt för objective-funktionen, eftersom framtida bidrag beror på återstående matcher och radantal, inte hur ett tidigare tillstånd nåddes. Det kräver inte brute force över `7^13` system.

Ordning och tie-break är fasta. Skillnader under numerisk tolerans hanteras deterministiskt; vid lika slutpoäng väljs det större radantalet. Samma input, modell och konfiguration ger samma system.

Budgeten måste räcka till minst en rad. Antalet rader är produkten av antalet tecken i varje match. Kostnad beräknas centralt som `Decimal(rowCount) * Decimal(costPerRow)`. Optimizern kan lämna pengar oanvända när ett billigare system har högre score eller när en viss kombination av garderingar inte kan nå exakt budget. Manuell redigering får överstiga budgeten, men UI:t visar då en tydlig varning.

## Returnerade mått

| Mått | Definition | Tolkning |
|---|---|---|
| `coverageScore` | Geometriskt medelvärde av de 13 matchernas täckta modellmassor | Genomsnittlig täckning per match |
| `allCorrectProbability` | Produkten av täckta modellmassor | Approximerad sannolikhet för 13 rätt, under oberoendeantagande |
| `riskScore` | `1 - coverageScore` | Heuristiskt jämförelsemått, inte sannolikheten att förlora pengar |
| `valueIndex` | Geometriskt medelvärde av `P(S_i) / max(Q(S_i), .005)` | Genomsnittlig relativ täckning mot folket, inte avkastning |

`coverageScore` är alltså inte sannolikheten för 13 rätt. Vinstnivåer för 10/11/12/13 rätt, jackpot, poolstorlek, andra spelares system och beroenden mellan matcher ingår inte. Separata modulgränser gör det möjligt att senare ersätta objective med en verifierad payoutmodell.
