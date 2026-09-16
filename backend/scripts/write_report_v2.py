"""Generate the review report from actual artifacts, without training or news requests."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ARTIFACTS
from app.news.config import NewsConfig
from app.news.repository import NewsRepository, now_utc

DOCS = Path(__file__).resolve().parents[2] / "docs"
MODELS = {"market":"Marknad", "v1":"Model v1", "v2":"Model v2"}


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers),
                      *["| " + " | ".join(map(str, row)) + " |" for row in rows]]) + "\n"


def score_rows(scores):
    return [[label, f"{scores[m]['log_loss']:.6f}", f"{scores[m]['brier_score']:.6f}",
             f"{scores[m]['accuracy']:.2%}", f"{scores[m]['ece']:.6f}"] for m, label in MODELS.items()]


def write_report():
    evaluation = json.loads((ARTIFACTS / "evaluation_v2.json").read_text())
    optimizer = json.loads((ARTIFACTS / "optimizer_diagnostics.json").read_text())
    verification = json.loads((ARTIFACTS / "demo_verification_v2.json").read_text(encoding="utf-8"))
    config = NewsConfig()
    news = json.loads((config.root / "latest_report.json").read_text(encoding="utf-8"))
    repo = NewsRepository(config.root)
    with repo.connection() as con:
        example = json.loads(con.execute("SELECT payload FROM observations ORDER BY recorded_at LIMIT 1").fetchone()[0])
    source = repo.article_sources([example["article_version_id"]], now_utc())[0]
    header = ["Modell", "Log Loss ↓", "Brier ↓", "Accuracy", "Macro ECE ↓"]
    sections = ["# Slutrapport – Prompt 2\n",
        "Implementerad och verifierad 2026-09-09. **Marknadsbaseline är aktiv. Model v2 slår inte marknaden över hela walk-forward-perioden.** Nyhetskedjan är separat och ändrar inga 1/X/2-sannolikheter.\n",
        "## Model Intelligence\n",
        "23 741 historiska matcher, varav 23 740 med användbara marknadssannolikheter. Sex walk-forward-perioder, 2020/21–2025/26, omfattar 8 904 testmatcher. V1 är samma modellfamilj och inställningsgrid som Prompt 1, omtränad för respektive period. V2 är den valda residualkandidaten `promotion_75`, inte aktiv deployment.\n",
        table(header, score_rows(evaluation["overall"])),
        "V2 ger marginellt sämre Log Loss och Brier men lägre sammanlagd ECE. Det räcker inte för deployment. Variantvalet använder 2020/21–2024/25; kandidatscoren på dessa perioder är urvalsresultat. Inga konfidensintervall eller statistiskt säkerställda vinster påstås.\n",
        "### Resultat per liga\n"]
    for league, label in {"E0":"Premier League", "E1":"Championship", "E2":"League One"}.items():
        scores = evaluation["byLeague"][league]
        sections += [f"#### {label} – {scores['market']['matches']} matcher\n", table(header, score_rows(scores))]
    sections += ["V2 försämrar Log Loss i Premier League och Championship. League One förbättras mycket svagt i både Log Loss och Brier; det motiverar ingen separat ligamodell.\n",
        "### Säsonger och audit\n",
        table(["Säsong", "Marknad LL", "V1 LL", "V2 LL", "Δ V2–marknad"],
            [[season, *[f"{scores[m]['log_loss']:.6f}" for m in MODELS], f"{scores['v2']['log_loss']-scores['market']['log_loss']:+.6f}"] for season, scores in evaluation["bySeason"].items()]),
        "Audit 2025/26, 1 484 matcher (utesluten från v2-urval; redan observerad i Prompt 1):\n", table(header, score_rows(evaluation["audit"])),
        "V2 förbättras svagt under audit men försämrar ECE och kan inte räddas av en enskild säsong. Den aktiva marknaden ändras därför inte.\n",
        "### Ablation och modellval\n",
        "Development 2020/21–2024/25, samma 7 420 matcher för samtliga varianter. Negativ delta betyder förbättring.\n",
        table(["Variant", "Log Loss", "Δ LL", "Δ Brier", "Vinnande säsonger / 5"],
            [[name, f"{s['log_loss']:.6f}", f"{s['delta_log_loss']:+.6f}", f"{s['delta_brier']:+.6f}", s['winning_seasons']] for name, s in evaluation["developmentAblation"].items()]),
        "`elo` = marknad + Elo. `form` lägger till rullande form; `venue` lägger till hemma/borta; `full` lägger till vila. `league_interactions` testar ligaspecifika korrektioner; `season_085/065` säsongsregression; `promotion_75` regression 0,85 och divisionsjustering; `temperature` separat temporal kalibrering.\n",
        "Ingen featuregrupp eller experimentvariant gav tillräcklig förbättring på development. Den bästa residualkandidaten vann endast 2 av 5 säsonger. All historik kan visas i UI, men inga Elo/form/vila- eller övergångskorrektioner används i den aktiva modellen. Samtliga sex perioders ablation finns även maskinläsbart.\n",
        "### Avvikelse från marknaden\n",
        "Bucket = största absoluta skillnaden mellan modellens och marknadens tre sannolikheter.\n"]
    rows = []
    for model in ("v1", "v2"):
        for bucket, value in evaluation["disagreement"][model].items():
            if value["matches"]:
                scores = value["scores"]
                rows.append([model, bucket, value['matches'], f"{scores['market']['log_loss']:.6f}", f"{scores[model]['log_loss']:.6f}", f"{value['delta_log_loss']:+.6f}"])
            else:
                rows.append([model, bucket, 0, "–", "–", "–"])
    sections += [table(["Modell", "Avvikelse", "N", "Marknad LL", "Modell LL", "Δ LL"], rows),
        "Större avvikelse innebär inte automatiskt mer information. Tomma eller små buckets ger inget stöd för stora korrektioner. Aktiv baseline avviker exakt 0 procentenheter.\n",
        "### Matchtyper\n",
        table(["Bucket", "N", "Marknad LL", "V1 LL", "V2 LL", "Δ V2 Brier"],
            [[name, scores['market']['matches'], *[f"{scores[m]['log_loss']:.6f}" for m in MODELS], f"{scores['v2']['brier_score']-scores['market']['brier_score']:+.6f}"] for name, scores in evaluation["byMarketBucket"].items() if scores['market']]),
        "Balans använder skillnaden mellan marknadens två största sannolikheter: <10, 10–25, 25–45 och ≥45 procentenheter. Draw-heavy betyder kryss ≥30 %. Early/mid/late är juli–oktober, november–februari respektive mars–juni; COVID-förskjutna spelscheman justeras inte. Buckets överlappar mellan olika diagnostikdimensioner.\n",
        "### Kalibrering per klass\n",
        "20 bin om 5 procentenheter, separat för 1/X/2. Tabellen visar klassvis ECE; alla bin med antal, predikterad andel och observerad frekvens finns i evaluation-v2.json och i Historik-vyn.\n",
        table(["Modell", "ECE 1", "ECE X", "ECE 2"], [[label, *[f"{v:.6f}" for v in evaluation['overall'][m]['class_ece']]] for m,label in MODELS.items()]),
        "## Optimizerdiagnostik\n",
        f"{optimizer['total_coupons_per_scenario']} icke-överlappande block med 13 historiska testmatcher. Tre scenarier × tre profiler × fyra budgetar = 24 624 optimeringar. Matcher i ett block kan ligga på flera datum. **Svenska Folket är simulerat** som normaliserad marknad upphöjd till 1,0 / 1,3 / 0,8 (marknadslik / favoritbetonad / skrällbetonad). Det är beteendediagnostik, inget payout-backtest. Objective är oförändrat.\n"]
    for scenario in optimizer["scenario_exponents"]:
        results = [r for r in optimizer['results'] if r['scenario'] == scenario]
        sections += [f"### {scenario}\n", table(["Profil", "Budget", "Spikar", "Halva", "Hela", "Utnyttjat", "1X / 12 / X2", "Matcher med X"],
            [[r['mode'], r['budget'], f"{r['average_singles']:.2f}", f"{r['average_doubles']:.2f}", f"{r['average_triples']:.2f}", f"{r['budget_utilization']:.1%}", " / ".join(f"{r['double_distribution'][s]:.1%}" for s in ('1X','12','X2')), f"{r['draw_coverage_fraction']:.1%}"] for r in results])]
    totals = {sign:sum(r['combinations'][sign] for r in optimizer['results']) for sign in ('1','X','2','1X','12','X2','1X2')}
    sections += ["### Alla teckenkombinationer\n", table(["Tecken", "Antal", "Andel av alla val"], [[s,n,f"{n/sum(totals.values()):.2%}"] for s,n in totals.items()]),
        "12 dominerar bland halvgarderingarna i flera scenarier. När både hemma- och bortaseger är mer sannolika än kryss ger 12 störst täckt sannolikhet bland halvgarderingarna. Dessutom påverkar helgarderingar och budgetens multiplikativa steg hela lösningen: få halvgarderingar kan ge en extrem procentfördelning. Exempelvis i marknadslik Optimal/256 är 95,3 % av endast 127 halvgarderingar 12, samtidigt som 3 340 helgarderingar täcker kryss. Genomsnittlig marknadssannolikhet för kryss är 26,13 %. Andelen matcher där X ingår är inte samma storhet som denna utfallssannolikhet. Fördelningen motiverar inte ensam ändrat objective.\n",
        "## News Intelligence – verklig insamling\n",
        f"Körning {news['checked_at']}, provider `{news['provider']}`, extractor `{news['extractor']}`. Kupong `{news['coupon_id']}` har verkliga lagnamn men **fiktiva DEMO-matcher/odds/streck**, inte verifierad aktuell Stryktipsomgång. Artiklarna är verkligt hämtade.\n",
        table(["Mått", "Antal"], [["Genererade queries",news['queries']], ["Artikelträffar i unika råsvar",news['articles_fetched']], ["Unika artiklar (URL)",news['unique_articles']], ["Deduplicerade träffar",news['articles_deduplicated']], ["Aktiva events / signals",sum(news['signals_by_type'].values())], ["Matcher med signals",news['matches_with_signals']], ["Uppdaterade matcher",news['matches_updated']], ["Cacheträffar",news['cached_queries']], ["HTTP-anrop i denna körning",news['provider_requests']]]),
        "Insamlingen gjorde 28 verkliga RSS-anrop i den föregående hämtningen (2 globala + 26 lagflöden). Ovanstående körning återanvände cachen för extraktion. Artikelräknaren räknar inte om samma råsvar för varje query. Databasen innehåller 219 artikelversioner för 218 URL:er över körningarna.\n",
        "### Granskningsbart exempel: Bolton–Reading, demomatch 12\n",
        f"En artikelversion → ett event → en `{example['type']}`-signal för Reading. Källa: [{source['publisher']}: {source['title']}]({source['url']}).\n",
        f"> {example['evidence']}\n",
        f"Publicerad {source['published_at']}; hämtad {source['retrieved_at']}; signal registrerad {example['recorded_at']}. Spelaren är anonym i underlaget och `player_id` är null. Inget påstående görs om ordinarieplats eller hur mycket återkomsten påverkar matchen. Status är Rapporterad, inte officiellt bekräftad. Källan är BBC Radio Berkshire via BBC:s Reading-flöde och gäller en ljudsida; extraktionen använder endast den tillgängliga RSS-texten.\n",
        f"Event-ID `{example['event_id']}`, artikelversion `{example['article_version_id']}`. Rådata `{source['raw_path']}`. Full provenance finns i [news-verification-v2.json](news-verification-v2.json).\n",
        "### Datakvalitet\n",
        table(["Mått", "Utfall"], [["Signals per typ",json.dumps(news['signals_by_type'])], ["Source tiers",json.dumps(news['source_tier_distribution'])], ["Events med flera källor",f"{news['multi_source_event_fraction']:.1%}"], ["Extraktionsfel",news['extraction_failures']], ["Artiklar utan konkreta extraherade signals",news['articles_irrelevant']], ["Artiklar utanför sju dagar",news['articles_outside_window']], ["Okänd publiceringstid",news['articles_missing_timestamp']], ["Misslyckade anrop",len(news['failed_requests'])]]),
        "145 artiklar gav inga konkreta regelbaserade signaler; det betyder inte att alla saknar relevant information för en mänsklig läsare. Alla 218 källartiklar är tier 2, och enda eventet saknar oberoende bekräftelse. Den begränsade täckningen är inte tillräcklig för slutsatser om nyheters prognosvärde.\n",
        "Brave/Tavily och strict LLM-extraktion är implementerade och testade med mockade kontrakt/fel, men inte verifierade med betalda live-anrop eftersom credentials saknas. RSS/rules är det verkligt körda alternativet. Paywalls, saknad fulltext, ljudmaterial, tvetydiga spelarnamn, gamla uppgifter och saknade lokala EFL-källor begränsar datakvaliteten. Inga historiska nyhetsutfall har konstruerats.\n",
        "## Verifiering och UI\n",
        "59 backendtester och 8 Playwright-tester (desktop/mobil) godkända; produktionsbygget lyckades. Två deprecation-varningar kommer från FastAPI/Starlette-testberoenden. Tester täcker temporal ordning, calibration utan framtida mål, reproducerbarhet, sannolikhetssummor, dedupe, källprioritet, oföränderliga snapshots, oddsrevertering, partiella fel, API-fel och LLM-refusal/ogiltig output. Externa nyhetsanrop är mockade i testsuiten.\n",
        "Riktigt API verifierat för 3 profiler × 4 budgetar och samtliga 13 matcher. Aktiv marknad ger exakt samma sannolikheter som oddsbaselinen. Automatiserade tester verifierar att news-update inte ändrar prediktioner och att sparade källor/signaler finns kvar efter uppdateringsfel.\n",
        f"Demokupongens Optimal/256 använder {verification['demo']['system']['cost']} kr. Systemets 13-rättssannolikhet visas tillsammans med ungefärlig 1-på-n och antagandet om oberoende matcher. Detta är en modelluppskattning, inte en utbetalningsprognos.\n",
        "Historik visar marknad/v1/v2, aktiv modell, ligor, säsonger, ablation, marknadsbuckets, avvikelser och kalibreringsbin. Matchens Nyheter-flik visar grupperade signals, status, tidsstämplar, belägg och originallänkar. Modell- och nyhetsvyerna förklarar att nyheter ännu inte påverkar sannolikheterna.\n",
        "## Levererade underlag och nästa steg\n",
        "[Teknisk metod, datamodell och begränsningar](model-news-v2.md). [README och körkommandon](../README.md). [Full maskinläsbar evaluation](evaluation-v2.json). [Optimizerdiagnostik](optimizer-diagnostics-v2.json). [API-verifiering](verification-v2.json). Modellvikter och walk-forward-Parquet ligger i backend/artifacts; råa nyheter, SQLite och exporter i backend/data/news.\n",
        "Prompt 3 kan använda match-/lag-/spelarnycklar, signaltyp, källa, publicerings- och registreringstid samt snapshots. `news_signals.parquet` och `news_snapshots.parquet` är exporterade. Inga news-aware features, godtyckliga spelarvikter eller tränade nyhetskorrektioner har införts. Nästa steg kräver mer tidsstämplad data och separat utvärdering.\n"]
    DOCS.mkdir(exist_ok=True)
    (DOCS / "implementation-report-v2.md").write_text("\n".join(sections), encoding="utf-8")
    for filename, value in [("evaluation-v2.json",evaluation), ("optimizer-diagnostics-v2.json",optimizer),
            ("verification-v2.json",{k:v for k,v in verification.items() if k != 'evaluation'}),
            ("news-verification-v2.json",{"run":news,"example":{"observation":example,"article":source}, "live_llm_verified":False,"outcomes_joined":False})]:
        (DOCS / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    print(DOCS / "implementation-report-v2.md")


if __name__ == "__main__":
    write_report()
