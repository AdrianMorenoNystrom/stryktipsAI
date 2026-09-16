# Model Intelligence v2 och News Foundation

## Modell och tidsgränser

`ml/correction.py` använder `softmax(log(P_market) + Wz + b)`. Marknadens koefficient är fixerad till 1. Standardiserade historiska features ger bara en regulariserad korrigering. Nollkorrigering ger exakt marknaden. Medelvärdesimputation, skalning och vikter lärs endast på respektive träningsperiod. L2-penalty omfattar även intercept; grid är 0,01 / 0,1 / 1. `ml/v2_config.py` centraliserar experiment och urvalsgränser.

Sex walk-forward-testperioder är 2020/21–2025/26. Varje periods hyperparametrar väljs med föregående säsong som validation, därefter refit på all tidigare data. Temperature scaling använder separat tidigare calibration-säsong och refittar inte dess grundmodell på calibration-data. Vikter är frysta under test; Elo/form uppdateras med redan avslutade matcher. Alla matcher samma datum får features innan något av dagens resultat används. Utfallsordning är alltid 1/X/2.

Arkitekturen väljs på development-perioderna 2020/21–2024/25. Auditsäsongen 2025/26 är exkluderad från v2-urvalet. Den var redan analyserad i Prompt 1 och är därför ingen helt ny blind studie. Sammanlagda v2-resultat inkluderar perioder som användes för variantval och är inte oberoende bekräftelse. Slumpmässig split används aldrig.

Deployment kräver minst 0,0005 lägre Log Loss, ingen försämring av Brier, högst 0,002 försämrad macro ECE samt bättre Log Loss i minst 60 % av development-säsongerna. Ingen variant klarade detta. Marknadsbaseline är därför aktiv; v2-kandidaten finns separat för granskning. En förbättring i en enstaka liga eller auditsäsong är otillräcklig för byte.

Ablation lägger successivt till Elo, form, hemma/borta och vila. League interactions, säsongsregression 0,85/0,65, divisionsjustering 75 Elo-poäng och temperature scaling testas också. Övergångar bevarar lagets historik och drar vid testad uppflyttning av 75 poäng relativt ny liganivå; nedflyttning har motsatt tecken. Detta är experimentparametrar, inte etablerade styrkeskillnader. Inga av dessa tillägg används i aktiv marknadsbaseline.

Log Loss och Brier prioriteras. Brier summerar klassernas kvadrerade fel (0–2). Kalibreringen har 20 disjunkta 5-procentenhetsbin per klass; ECE är medelvärdet av tre klassvisa, antalviktade absoluta kalibreringsfel. ECE beror på binindelning och stickprovsstorlek och är ingen bevisad förbättring i sig.

`evaluation_v2.json` och `walk_forward_predictions.parquet` innehåller ligor, säsonger, favoritstyrka, balans, hemma-/bortafavorit, krysstung marknad, säsongsfas, avvikelse från marknaden och samtliga ablationer. Avvikelse definieras som största absoluta klasskillnad. Tomma buckets saknar scores. `model_metadata.json` skiljer aktiv evaluation från arkiverade `legacyV1`-värden. `training_matches` för marknadsbaseline beskriver historikunderlaget; baseline har inga inlärda vikter.

Football-Data saknar exakt observationstid för historiska icke-closing-odds. Resultaten verifierar inte ett specifikt T−24h-beslut. Prediktions-API:t är inte ett historiskt backtest; de sparade walk-forward-prognoserna används för sådana analyser.

## Separat nyhetskedja

`app/news` äger konfiguration, providers, extraktion, SQLite-lagring, events och API. `ml` och sannolikhetstjänsterna läser inga nyhetssignaler. Kuponganalys sparar manuella odds/streck men en lagringsstörning blockerar inte prognosen. Ingen nyhetsfeature, sentimentvariabel, spelarvikt eller sannolikhetsjustering ingår.

Providers är Brave News, Tavily News och ett begränsat RSS-alternativ (BBC/Sky samt BBC-flöden för kupongens lag). Brave/Tavily kräver `NEWS_API_KEY`. Tom `NEWS_PROVIDER` ger läsbar status utan nätverksanrop. RSS kräver inga nycklar men motsvarar inte full webbsökning. Två centrala frågor per unikt lag plus en per match ger 65 frågor för 26 lag. RSS hämtar varje flöde högst en gång per jobb; frågor återanvänder dessa svar. Cache är 1 timme, intervall 1 sekund, högst tre försök med backoff vid 429/5xx/anslutningsfel. Misslyckade delkällor flaggas samtidigt som användbara resultat behålls.

Standardfönstret är de senaste sju dagarna vid insamling inför en framtida match. Matchdatum saknar kickoffklockslag: UTC-dygnets början är en konservativ stoppgräns, så ingen insamling matchdagen används som pre-match-signal. Publiceringstid och hämtningstid lagras separat. Okänd eller enbart datumangiven publiceringstid sparas, men ger ingen aktiv signal. Material äldre än fönstret extraheras inte.

### Rådata, identifiering och historik

- `data/news/raw/<sha256>.raw`: oförändrade HTTP-svar, innehållsadresserade och aldrig överskrivna.
- `articles`: kanonisk URL-identitet; trackingparametrar och fragment tas bort.
- `article_versions`: versionshash av URL, innehåll och publiceringstid; koppling till raw, query, källa, upptäckta lag och hämtningstid.
- `extractions`: append-only resultat per artikelversion och extractorversion. En ny extractorversion kan bearbeta samma rådata igen.
- `events` och `observations`: grupperad händelse respektive oföränderliga belägg/statusobservationer. Tillgänglighetsuppgifter om samma identifierade spelare och match grupperas. Anonyma laguppgifter kräver titellikhet ≥0,82 inom 72 timmar.
- `players`: lagbunden identitet, namn och alias. J. Smith/J Smith/John Smith kan förenas; kända olika fullständiga namn förenas inte. `player_importance` lämnas null.
- `snapshots`: oförändrad lista över då aktiva signaler per match och tid.
- `coupon_snapshots`: manuella odds och Svenska Folket lagras vid förändrat kuponginnehåll, med faktisk registreringstid.

As-of-frågor kräver både publicerings- och registreringstid före gränsen. Senare hittade gamla artiklar bakdateras aldrig. Snapshot-vyn returnerar senast faktiskt sparade snapshot före gränsen. Exportscriptet skriver både observationer och snapshots till Parquet, utan matchutfall. Tidigare snapshots rekonstrueras inte från dagens webbsökning. Detta möjliggör framtida backfill, men skapar inte historisk kunskap som aldrig registrerats.

### Extraktion och källvärdering

`NEWS_EXTRACTION=openai` använder Responses API med `store:false` och strict JSON Schema. `LLM_API_KEY` (alternativt `OPENAI_API_KEY`) och `LLM_MODEL` krävs. Systemprompten begränsar modellen till given artikel, förbjuder tidigare kunskap, påhittad frånvaro/lineup och matchprediktion, samt instruerar att osäkra/irrelevanta uppgifter ska ge tom lista. Varje signal måste ha ett ordagrant belägg som också identifierar laget och eventuell spelare. Pydantic avvisar främmande fält, bland annat probability deltas. Ogiltig JSON, refusal och ofullständiga svar ger extraktionsfel och inga påhittade ersättningar.

Utan LLM kan `rules` väljas uttryckligen. Det är begränsad regelbaserad extraktion av konkreta formuleringar, tydligt märkt i UI och metadata. Den stöder färre uttryck än de 17 tillåtna signaltyperna och ska förväntas missa många relevanta uppgifter. Inget live-LLM-anrop gjordes i verifieringen eftersom credentials saknades. Structured-output-kontrakt och felbeteende testas med mockade svar.

Source tiers är central domänmetadata: 1 officiell klubb/liga, 2 etablerad nationell sportredaktion, 3 lokala medier, 4 övriga. Kvalitetsvikter är 1 / 0,85 / 0,65 / 0,4. Listan behöver förvaltas och är ingen garanti för artikelns sanningshalt.

Confidence beräknas transparent:

```text
0.40 × source_quality
+ 0.25 × extraction_certainty
+ 0.20 × exp(−hours_since_selected_publication / 72)
+ 0.15 × min(independent_sources, 3) / 3
```

Identiska syndikerade texter räknas högst som en oberoende källa. Senaste officiella uppgiften inom fönstret väljs före lägre tiers; annars senaste rapporten. En senare officiell återkomst kan ersätta tidigare frånvaro utan att radera den. Motstridiga uppgifter markeras. En äldre officiell uppgift kan fortfarande väga tyngre än en nyare inofficiell; användaren behöver granska datum.

Bekräftad kräver officiell källa och explicit bekräftelsestatus. Starkt rapporterad kräver confidence ≥0,80 och minst två oberoende källor. Under 0,60 visas Osäker uppgift; annars Rapporterad. Dessa etiketter gäller källunderlag, inte uppskattad matchpåverkan. Matchrelevans är 1 / 0,8 / 0,5 för ålder under 24h / 24–72h / 3–7 dagar.

### Drift och begränsningar

CLI kan schemaläggas externt, exempelvis dagligen och varannan timme nära stopp. Affärslogiken innehåller inget hårdkodat schema. Kör en lokal process/worker: låset för samtidiga uppdateringar är processlokalt. POST till news/update tillåts bara från lokal klient med lokal Origin; detta är ingen publik administratörsautentisering.

Betalväggar och ljudartiklar ger ofta bara titel/snippet. RSS täcker inte alla officiella eller lokala Championship/League One-källor. Lagomnämnanden kan handla om gamla matcher, dam-/ungdomslag eller transfers; filter minskar men eliminerar inte felkopplingar. Initialer är tvetydiga, och anonyma spelare kan inte säkert slås samman. Confidence är en dokumenterad heuristik, inte empiriskt kalibrerad sannolikhet. Inga massiva historiska crawls eller nyhetstränade modeller har byggts.

## API-tillägg

| Metod | Endpoint | Innehåll |
|---|---|---|
| GET | `/api/news/status` | Konfiguration, counts, senaste körning; inga secrets |
| GET | `/api/matches/{matchId}/news` | Snapshot, grupperade signals och källor |
| GET | `/api/matches/{matchId}/news/signals` | Strukturerade signals |
| GET | `/api/matches/{matchId}/news/sources` | Artikelversioner och provenance |
| POST | `/api/news/update` | Lokal uppdatering, `{coupon: ...}` eller `{}` för CURRENT |
| GET | `/api/coupon/current` | Senast analyserade/sparade kupong |
| GET | `/api/coupon/{id}/snapshots` | Historiska manuella odds/streck |

Nyhets-GET accepterar `?as_of=2026-09-09T12:00:00Z`. Tidszon krävs; framtida gränser avvisas. Stabilt `matchId` kommer från analys-API:t, baserat på datum, liga och normaliserade lag. Frontend startar fortfarande med tydligt märkt DEMO DATA; CURRENT i CLI avser senaste sparade kupong, som kan vara demo.

## Referenser för adapterkontrakt

[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Brave News Search](https://api-dashboard.search.brave.com/app/documentation/news-search/get-started), [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search), [scikit-learn calibration](https://scikit-learn.org/stable/modules/calibration.html) och [SciPy L-BFGS-B](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html).
