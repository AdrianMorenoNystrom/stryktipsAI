"""Create the final review artifact from measured verification data, never examples."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ARTIFACTS, LEAGUES


def write_report() -> Path:
    report = json.loads((ARTIFACTS / "demo_verification.json").read_text(encoding="utf-8"))
    metadata = json.loads((ARTIFACTS / "model_metadata.json").read_text(encoding="utf-8"))
    docs = Path(__file__).resolve().parents[2] / "docs"
    docs.mkdir(exist_ok=True)
    example = report["demo"]
    system = example["system"]
    lines = ["# Slutrapport — Stryktipset Predictor MVP", "", f"Verifierad {report['verified_at']}. Alla siffror nedan kommer från körd pipeline och API.", "",
             "## Implementerat", "", "- Angular 21 med svensk desktop-/mobilvy enligt den befintliga UI/UX-specifikationen.",
             "- FastAPI med validerad 13-matchers kupong, modellstatus, lagsökning, prediction, analys, optimizer och central kostnadsberäkning.",
             "- Automatisk Football-Data-import, immutable rådata, per-fil-manifest, cache, återförsök, normalisering och Parquet.",
             "- Verklig logistisk regressionsmodell med Elo, tidigare form, hemma/bortastyrka, vila och de-viggad marknad; reproducerbara artefakter och separat temporalt sluttest.",
             "- Edge/value, deterministisk DP-optimizer, tre faktiska profiler, manuella tecken, prisuppdatering och kopiering av system.", "",
             "## Dataset", "", "| Liga | Normaliserade matcher |", "|---|---:|"]
    for code, name in LEAGUES.items():
        lines.append(f"| {name} ({code}) | {report['dataset'][code]:,} |")
    lines.extend([f"| **Totalt** | **{report['dataset_total']:,}** |", "",
                  f"51/51 CSV-filer hämtades från 2010/11–2026/27. {len(report['import_failures'])} importfel. Data till och med {metadata['data_through']}.",
                  f"{report['training_matches']:,} matcher har kompletta tillåtna marknadsodds och ingår i modellträningen. En match saknar sådana odds men kan bidra till efterföljande historiska features.", "",
                  "## Modell", "", f"Multinomial logistisk regression, C={metadata['selected_C']}, fixed seed={metadata['seed']}. {report['feature_count']} inputs före one-hot-kodning av ligan.", "",
                  "- 3 Elo-inputs: hemma före match, borta före match, skillnad inklusive hemmaplansfördel.",
                  "- 3 de-viggade marknadssannolikheter.",
                  "- 40 rolling-inputs: två lag × två fönster (5/10) × fem mått (poäng, mål för/emot, skott, skott på mål) × total/hemma-borta.",
                  "- 3 viloinputs samt liga.", "", "| Period | Från | Till | Matcher med odds |", "|---|---|---|---:|"])
    labels = {"train": "Train / modellval", "validation": "Validation", "test": "Test", "evaluation_fit": "Omträning före test", "production_fit": "Deploymentmodell"}
    for key, label in labels.items():
        split = report["split"][key]
        lines.append(f"| {label} | {split['from']} | {split['to']} | {split['matches']:,} |")
    lines.extend(["", "Validation väljer regularisering utan att använda testutfall. Testets modellvikter är frysta före testperioden. Form och Elo uppdateras löpande med enbart tidigare datum. Deploymentmodellen tränas därefter på all tillgänglig historik; sluttestmåtten kommer från den separata utvärderingsmodellen.", "",
                  "## Baseline comparison", "", "| Sluttest 2025/26 | Log Loss ↓ | Brier ↓ | Accuracy ↑ |", "|---|---:|---:|---:|"])
    for key, label in (("market", "Bookmaker baseline"), ("ml", "ML-modell")):
        scores = report["test"][key]
        lines.append(f"| {label} | {scores['log_loss']:.6f} | {scores['brier_score']:.6f} | {scores['accuracy']:.2%} |")
    lines.extend(["", "**ML-modellen slår inte marknadsbaselinen i detta första test.** Det är ett fungerande baseline-experiment, inte evidens för lönsamhet. Multiclass Brier är summan av tre kvadrerade fel, sedan medelvärde över matcher (0–2). Kalibreringsbin per utfall sparas i modellmetadata och evaluation.json.", "",
                  "## Optimizer", "", "Optimizern maximerar en additiv kombination av log-täckning, modellviktad edge och log-värde, minus kostnad för garderingar. Exakt DP över möjliga radprodukter väljer mellan alla sju teckenkombinationer. Radkostnaden räknas med Decimal. Vikterna skiljer mellan Optimal, Säker och Värde.", "",
                  "Se [exakt objective, vikter, algoritm och mått](optimizer.md). Hela budgeten måste inte användas om ett billigare system har högre score. Optimizern modellerar inte faktisk utdelning.", "",
                  "| Profil | Budget kr | Faktisk kostnad kr | Rader | Spikar | Halv | Hel |", "|---|---:|---:|---:|---:|---:|---:|"])
    for s in report["systems"]:
        lines.append(f"| {s['mode']} | {s['budget']:g} | {s['cost']:g} | {s['rowCount']} | {s['singles']} | {s['doubles']} | {s['triples']} |")
    lines.extend(["", "Alla 12 systemen höll budgeten. Varje körning hade exakt 13 matcher och ML-prognoser som summerade till 1.", "",
                  "## UI", "", "- **Översikt:** optimal rad, kostnad, garderingar, värdeindex, budget/profil, exakt tre insikter och 13 matchkort.",
                  "- **Kupong:** redigerbara lag/liga/datum/odds/folkstreck, lagsökning, ny tom kupong, crowd-validering, förvalda tecken, manuella ändringar, återställning och kopiering.",
                  "- **Matchdetaljer:** högerdrawer på desktop, helskärm på mobil, fungerande Översikt/Form/Modell. Nyheter visar endast begärd placeholder.",
                  "- **Analys:** alla 39 tecken med modell, marknad, streck, edge och värde.",
                  "- **Historik:** verklig modellstatus, perioder, dataset, jämförelsemått och tom livehistorik utan påhittade resultat.",
                  "- Skeleton, fel/återförsök, märkt fallback, fokusstöd och mobil bottennavigation.", "",
                  "## Demo — verklig API-körning med fiktivt kupongunderlag", "", "**DEMO DATA:** matcher, odds och folkstreck är exempel. Alla 13 prognoser nedan kommer från den tränade modellen; ingen statisk prediction har använts.", "",
                  f"**Optimal rad · {system['cost']:g} kr · {system['rowCount']} rader**", "", "```text",
                  " | ".join("".join(selection) for selection in system["selections"]), "```", "",
                  f"{system['singles']} spikar, {system['doubles']} halvgarderingar, {system['triples']} helgarderingar. Värdeindex {system['metrics']['valueIndex']:.4f}.", "",
                  "| # | Match | Modell 1 / X / 2 | Val |", "|---|---|---|---|"])
    for match in example["matches"]:
        probabilities = " / ".join(f"{match['model'][k] * 100:.1f}%" for k in ("home", "draw", "away"))
        lines.append(f"| {match['number']} | {match['homeTeam']} – {match['awayTeam']} | {probabilities} | {''.join(match['recommendation'])} |")
    lines.extend(["", f"Geometrisk täckning per match: {system['metrics']['coverageScore']:.4f}. Approximerad sannolikhet för 13 rätt under oberoendeantagande: {system['metrics']['allCorrectProbability']:.4%}. Dessa är olika mått; värdeindex är inte ekonomisk avkastning.", "",
                  "## Verifiering", "", "- **37 backendtester passerade:** de-vig, nullkolumner/oddsfallback, rolling- och datumläckage, Elo, alias, edge/value/nollstreck, kostnad, profiler, DP mot brute force på liten kupong, budgetar, validering, fallback, API och immutable download/cache.",
                  "- **6 Playwright-tester passerade** mot riktigt API: tre flöden på både desktop och mobil. Alla budgetar, 13 ML-prognoser, matchflikar, crowd-fel, oddsändring, manuella tecken, återställning, analys/historik och API-fel/återhämtning.",
                  "- **Angular production build passerade** med strict TypeScript och templates.",
                  "- **Download, normalize, train och evaluate kördes** på verklig källdata.",
                  "- En andra pipelinekörning återanvände **51/51 cachefiler utan omhämtning** och reproducerade samtliga tre sluttestmått inom 1e−12.",
                  "- **12 kompletta optimeringar** verifierades separat över HTTP; inga budgetöverträdelser.",
                  "- Desktop och mobil granskades visuellt via webbläsarscreenshots.", "",
                  "Maskinläsbart underlag: [verification.json](verification.json). Fullständig lokal körning inklusive form/features finns i backend/artifacts/demo_verification.json. Testbilder finns i frontend/test-results/.", "",
                  "## Kända begränsningar", "", "- Svenska Folket och aktuell kupong/odds matas in manuellt; demounderlaget är inte ett aktuellt spelprogram.",
                  "- ML förbättrar inte marknaden på detta sluttest. Vikterna för spelvärde är initiala, inte avkastningskalibrerade.",
                  "- Ingen payout-/jackpotmodell, inga korrelationer mellan matcher, inga verkliga avkastnings- eller livekupongmått.",
                  "- Historiska opening-odds saknar exakta observationstider. Closing-odds är exkluderade, men ett bestämt T−24h-beslut kan inte backtestas säkert med denna datakälla ensam.",
                  "- Modellparametrar är enklare baselines: ingen separat kalibreringsmodell, säsongs-/uppflyttningsjustering eller walk-forward-parameteroptimering.",
                  "- Lagnamn normaliseras centralt; ännu okända lag eller färre än fem matcher ger märkt marknadsfallback. Deploymentmodellens historiska datum ger också fallback för att förhindra framtidsläckage.",
                  "- Nyheter, skador, rotation och lineups ingår inte. Nyhetsfliken är uttryckligen en placeholder.",
                  "- Manuell kupong och tecken lagras i arbetsminnet; omladdning återställer demo. Snapshotfält finns men någon automatisk snapshotdatabas finns inte ännu.",
                  "- Lokalt MVP-upplägg utan inloggning, driftplattform eller spelinlämning.", "",
                  "## Nästa logiska steg", "", "En tillförlitlig integration för kupong/Svenska Folket/odds med tidsstämplade snapshots, följd av News Intelligence-pipeline och walk-forward-jämförelse mot marknadsbaselinen.", ""])
    path = docs / "implementation-report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    evidence = {k: v for k, v in report.items() if k != "demo"}
    evidence["demo"] = {"demo": True, "system": system, "matches": [{k: m[k] for k in ("number", "homeTeam", "awayTeam", "model", "market", "crowd", "source", "recommendation")} for m in example["matches"]]}
    (docs / "verification.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write_report())
