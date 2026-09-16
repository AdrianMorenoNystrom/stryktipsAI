# Svenska Spel: publik kupong- och resultatprovider

Prompt 4 kompletterar denna integration med Postgres, bookmakerkonsensus och GitHub Actions. Se [deployment](deployment.md) och [market consensus](market-consensus.md) för produktionsdrift. Lokal SQLite och de äldre Svenska Spel-skripten finns kvar för development.

Verifierad med verkliga HTTP-svar den 9 september 2026. Integrationen använder endast publika GET-anrop. Ingen inloggning, kontoåtkomst, kuponginlämning eller betalning ingår. Ingen API-nyckel behövdes vid verifieringen. Det externa flödet är odokumenterat och kan ändras eller sluta fungera.

## Endpoints och parser

Bas: `https://api.spela.svenskaspel.se/draw/1/stryktipset`.

| GET-sökväg | Observerad wrapper | Användning |
|---|---|---|
| `/draws` | `draws: [...]` | Tillgängliga aktuella omgångar |
| `/draws/{drawNumber}` | `draw: {...}` | Specifik aktuell eller historisk omgång |
| `/draws/{drawNumber}/result` | `result: {...}` | Facit och utdelning |

`CouponProvider` och `SvenskaSpelProvider` finns i `backend/app/stryktipset/provider.py`. Endast `parser.py` känner till källans fältstruktur. Servicen använder interna `Draw`/`DrawResult` och bygger befintlig strikt `Coupon` först när analysens nödvändiga inputs finns. Den befintliga prediction-servicen, analysfunktionen och optimizern återanvänds.

| Svenska Spel-fält | Internt fält/tolkning |
|---|---|
| `drawNumber` | `draw_number`, stabil omgångsidentitet |
| `productName`, `productId` | Validera Stryktipset och produkt 1 |
| `drawState` | `source_status` och normaliserad status; okända värden ger schemafel |
| `regOpenTime`, `regCloseTime` | `sales_open_at`, `sales_close_at`; draw_date från spelstopp i Europe/Stockholm |
| `rowPrice` | Observerat radpris, exempel `"1,00"` → 1 SEK; avvikelse från appens pris blockerar analys |
| `drawEvents[].eventNumber` | Matchnummer 1–13, exakt en av varje |
| `drawEvents[].match.matchId` | `provider_event_id`; lokal crowdidentitet `ss:{draw}:{number}` |
| `match.participants[].type` + `.name` | Välj home/away efter typ och använd fullständigt namn |
| `match.matchStart` | `kickoff_at`, annars null och ingen liveanalys |
| `match.league.name`, `.country.isoCode` | Tävling och konservativ ENG-mappning till E0/E1/E2 |
| `match.sportEventStatus`, `drawEvents[].cancelled` | Matchstatus; startad/inställd match blockerar ny analys |
| `drawEvents[].svenskaFolket.one/x/two` | Observerad crowd 1/X/2, procent normaliseras till 0–1 |
| `drawEvents[].svenskaFolket.date` | `crowd.source_updated_at`; år före 2000 betraktas som saknad källtid |
| `drawEvents[].odds.one/x/two` | Separat observerad decimaloddstrippel; marginaljusterad marknadsbaseline |
| `result.events[].eventNumber`, `.matchId` | Koppling till arkiverad omgång och providerhändelse |
| `result.events[].outcome`, `.outcomeScore.home/away` | Officiellt 1/X/2 och mål; kontrolleras mot varandra när matchen inte är inställd |
| `result.distribution[].name` | Utdelningsnivå, exempel `13 rätt` |
| `result.distribution[].winners`, `.amount` | Antal vinnare och SEK per vinnande rad; saknat värde förblir null |

`eventDescription` och förkortade deltagarnamn används inte för lagidentitet. `refOne`, `refDate`, `startOdds` och `favouriteOdds` används inte för att rekonstruera äldre observationer. Svenska Folket används aldrig som odds. Liveoddsen är den separata oddstrippel som faktiskt observerats i kupongflödet, **inte ett bookmakerkonsensus**. Saknade odds kräver explicit manuell oddsinput, vars källa och registreringstid sparas separat.

Crowd accepterar 99–101 procent totalt och normaliserar summan; 33/33/33 är giltigt. Negativa tal, NaN, oändlighet, booleska värden och orimliga summor avvisas. Saknade/ogiltiga enskilda streck eller odds visas som saknade och blockerar komplett liveanalys. Annat matchantal än 13, saknade lag eller okänt response-schema ger tydligt provider/schemafel och bevarar tidigare giltig kupong.

## Lag, tävling och aktiv modell

Det centrala `backend/app/team_aliases.json`-lagret och kända lag i Football-Data återanvänds utan osäker fuzzy matching. Okända namn behålls som källnamn med null canonical-ID och synlig diagnostik. Alias läggs till via `scripts/add_team_alias.py` eller `POST /api/teams/aliases`; canonical-namn kan inte omdirigeras till ett annat lag. Nästa riktiga hämtning använder aliaset. Gamla snapshots skrivs inte om.

E0/E1/E2 är tränad ligatäckning. Övriga tävlingar markeras `No trained league coverage` och får endast dokumenterad de-vig marknadsfallback om riktiga odds finns. Aktiv deploymentmodell är fortsatt `market`, modellmetadata version 2.0. Crowd movement och nyheter korrigerar inte P_model. Snapshoten sparar modellens artefakthash och exakta inputs.

## Val av aktuell omgång, cache och health

Servicen väljer öppna omgångar med framtida spelstopp och passerad eventuell öppningstid. Om ingen finns väljs närmast kommande omgång. Inom gruppen väljs tidigaste spelstopp, därefter omgångsnummer. Ordningen i källans array påverkar inte valet. Framtida stängda/slutförda draws blir inte aktuella. UI kan välja bland relevanta omgångar.

Angular anropar bara vårt API. `GET /api/coupon/current` returnerar ett envelope med `draw`, eventuell analysklar `coupon`, `analysis_ready`, `issues`, `stale`, `health`, tillgängliga omgångar och mappingdiagnostik. `POST /api/coupon/current/refresh` gör kontrollerad refresh. `POST /api/coupon/current/analyze` accepterar omgång, budget och profil; servern läser egna tidsstämplade inputs. Även befintlig `/api/coupon/analyze` med liveidentitet läser serverns observerade data, så klientredigerade streck kan inte uppträda som providerdata.

`Healthy/Degraded/Unavailable`, senaste lyckade anrop och felorsak sparas. Historiska 404-fel försämrar inte status för aktuell endpoint. Vid fel med cache visas tydligt märkt gammal data. Saknas aktuell kupong används tydligt märkt demo; manuell kupong finns kvar. Tidigare manuellt sparad current-kupong finns nu under `/api/coupon/manual/current`.

HTTP har timeout 20 s, högst tre försök, minst en sekund mellan anrop inom en providerinstans och begränsad backoff för 429/5xx/anslutningsfel. UI-refresh begränsas till minst 60 s mellan försök; automatisk återhämtning efter fel väntar 300 s. En processlokal ingest-lock och databaslås skyddar hämtning/lagring. Produktion använder PostgreSQL advisory locks mellan backend och insamlare; SQLite använder en lokal lease. Se deploymentguidens krav på direktanslutning/session pooling.

## Snapshot-policy och drift

Inställningarna ligger i `DrawConfig`, inte i business services. `STRYKTIPS_LIVE_ENABLED=false` stänger av hämtning; `STRYKTIPS_LIVE_DIR` flyttar arkivet. `.env` laddas inte automatiskt.

| Tid till spelstopp | Default |
|---|---|
| Mer än 48 timmar | 6 timmar |
| 24–48 timmar | 2 timmar |
| 6–24 timmar | 1 timme |
| Sista 6 timmarna | 30 minuter |
| Sista 30 minuterna före stopp | 5 minuter |

Produktion använder nu `scripts/collect_live_data.py` i GitHub Actions, inklusive bookmakerdata, prognoser, system och resultat. Aktivera workflow enligt deploymentguiden. För enbart lokal Svenska Spel-insamling kan det äldre `scripts/update_stryktipset.py --due` köras med cron, Windows Task Scheduler eller valfri worker enligt exemplen nedan. Ingen Windows-scheduler installeras automatiskt. Ett exakt snapshot vid stopp kan inte garanteras.

Exempel cron, med absoluta projektsökvägar anpassade till installationen:

```cron
* * * * * cd /srv/stryktipsAI/backend && ../.venv/bin/python scripts/update_stryktipset.py --due >> data/stryktipset/scheduler.log 2>&1
15 * * * * cd /srv/stryktipsAI/backend && ../.venv/bin/python scripts/update_stryktipset_results.py >> data/stryktipset/results.log 2>&1
```

Windows Task Scheduler: program `C:\stryktipsAI\.venv\Scripts\python.exe`, argument `C:\stryktipsAI\backend\scripts\update_stryktipset.py --due`, startkatalog `C:\stryktipsAI\backend`, upprepning varje minut. Använd dold körning och förhindra parallella instanser.

## Lagring, tidsgränser och exporter

SQLite WAL återanvänder samma arkivbas som befintlig NewsRepository lokalt. Utan `DATABASE_URL` ligger Stryktipsdata i `backend/data/stryktipset/stryktipset.sqlite3`. Produktion kräver nu Postgres: snapshots, resultat och råbytes ligger i databasen, oberoende av backendens filsystem. News extraction/scoring har inte utökats.

Tabeller: `stryktipset_draws`, `stryktipset_matches`, `draw_observations`, `crowd_snapshots`, `market_snapshots`, `prediction_snapshots`, `optimizer_snapshots`, `result_observations`, `match_results`, `draw_payouts`, `provider_raw_payloads`, `provider_health`. Index omfattar omgång/match/tid och spelstopp. Draw/match-tabellerna är senaste-index; observationer och analyskörningar läggs till utan att ersätta äldre poster.

Varje erhållet HTTP-svar sparas som oförändrade bytes i innehållsadresserad `.raw`-fil, även felsvar. Request-ledgern sparar källa, HTTP-status och retrieval-tid. Identiska bytes kan dela fil, men skilda riktiga hämtningar får skilda observationer. Re-ingest av samma raw-ID/omgång ger ingen dublett. Rådata och databas behöver säkerhetskopieras tillsammans. Lokal schemaändringsundersökning finns också under `discovery/`.

Tider sparas i UTC med tidszon; UI visar lokal tid. `retrieved_at` är när svaret kom, `recorded_at` när observationen sparades och `source_updated_at` källans egen tid om giltig. As-of input kräver att samtliga tillgängliga tider är ≤ T. Äldre reparse kan aldrig ersätta nyare hämtning. Fixtureidentitet kontrolleras så att ersättningsmatcher inte ärver odds/streck från tidigare lag på samma matchnummer.

`is_pre_close_snapshot` betyder **kvalificerad observation före stopp**, inte att den var exakt vid stopp. `repo.pre_close()` väljer den senast hämtade kompletta 13-matchersbatchen vars tider samtliga ligger före spelstopp. Historisk hämtning idag kan aldrig få denna flagga för en redan avslutad omgång. Snapshotvyn stöder första, 24 h före, före spelstopp, senaste och exakt observationstid. Saknas observation vid vald tid visas frånvaro, inte bakdaterad slutdata. Resultat/utdelning visas separat med efterhandstid.

Varje lyckad liveanalys sparar 13 predictionrader och ett system i samma transaktion, med exakta input-ID:n, tidsstämplar, modellhash, budget/profil, tecken, radantal, kostnad och beräknade mått. Teckenändringar jämförs mot tidigare sparad analys med samma budget/profil. Resultat/payout hämtas aldrig in som features. Någon ny historisk prediction skapas inte efter avslutad omgång.

`scripts/export_stryktipset.py` skriver en konsekvent SQLite-lässnapshot till separata JSONL-tabeller och manifest. `scripts/diagnose_real_crowd.py` sammanställer endast faktiskt sparade pre-close-system, senaste per omgång/budget/profil. `--analyze-current` skapar tolv analyser från redan observerad aktuell kupong. Skripten gör inga externa HTTP-anrop och sammanfogar inte utfall med modellinputs.

## Historik, facit och kända gränser

Historical importer tar stigande intervall om högst 500 omgångar, begränsar anropstakten, sparar rapport efter varje omgång och återanvänder fungerande data vid omkörning. `--refresh` begär uttryckligen ny hämtning. Ett misslyckat draw stoppar inte resten. Resultat hämtas med samma provider; färdiglagrade resultat återanvänds och inte färdiga kan uppdateras med `--force`.

Lokalt har 4267–4270 och 4958–4969 importerats. Äldsta framgångsrika undersökta omgång är **4267, 2013-01-12**: metadata, 13 matcher, crowd, 13 facit och fyra utdelningsnivåer finns. 4266 och flera äldre stickprov svarade 404. Även stickprov 4300, 4400, 4500 och 4900 fungerade. Detta visar observerad tillgänglighet, inte garanterad sammanhängande täckning eller bevis på att allt äldre saknas.

Äldre crowd kan ha källtiden `0001-01-01...`; den lagras som null. Nyare historiska omgångars source-tid låg efter spelstopp. Dessa procentsiffror sparas som slutdata hämtad idag. De ger **inga** legitima historiska pre-close-samples. Payoutfält kan saknas på andra draws och visas då som saknade. Belopp är officiell utdelning per vinnande rad, ingen uppskattad avkastning för vårt system.

För maskinläsbar faktisk täckning, tider, teckenfördelning och livekörning, se [verification-v3.json](verification-v3.json), [optimizer-real-crowd-v3.json](optimizer-real-crowd-v3.json) och [slutrapporten](implementation-report-v3.md).
